import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import ccxt.async_support as ccxt
import os
import nest_asyncio
from datetime import datetime, timedelta

# Aplica o patch para permitir loops aninhados,
# corrigindo o problema no ambiente Heroku
nest_asyncio.apply()

# --- Configurações básicas ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# LUCRO_MINIMO_PORCENTAGEM será gerenciado via comando /setlucro
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0 # Quantidade de USD para verificar liquidez
DEFAULT_FEE_PERCENTAGE = 0.1 # Taxa de negociação média por lado (0.1% é comum)

# Limite máximo de lucro bruto para validação de dados.
# Mantido em 100.0% conforme solicitado.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0 

# Período de cooldown para evitar alertas repetidos para a mesma oportunidade (em segundos).
COOLDOWN_PERIOD_FOR_ALERTS = 300 # 5 minutos
# Porcentagem de mudança no lucro líquido para re-alertar uma oportunidade existente antes do cooldown expirar
PROFIT_CHANGE_ALERT_THRESHOLD_PERCENT = 0.5 # Ex: se o lucro mudar em 0.5% ou mais, alerta novamente

# Número de varreduras consecutivas que uma oportunidade deve estar ausente
# antes de um alerta de cancelamento ser enviado.
CANCELLATION_CONFIRM_SCANS = 2 # Ex: 2 varreduras (2 minutos com intervalo de 60s)

# Exchanges confiáveis para monitorar (reduzido para as 10 maiores/mais confiáveis)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitfinex', 'bitget', 'mexc'
]

# Pares USDT (reduzido para os primeiros 60 pares para otimização)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "USDT/USDT", "BNB/USDT", "SOL/USDT", 
    "USDC/USDT", "STETH/USDT", "DOGE/USDT", "TRX/USDT", "ADA/USDT", "XLM/USDT", 
    "BCH/USDT", "SUI/USDT", "LINK/USDT", "HBAR/USDT", "AVAX/USDT", "LTC/USDT", 
    "SHIB/USDT", "UNI/USDT", "XMR/USDT", "DOT/USDT", "PEPE/USDT", "AAVE/USDT", 
    "CRO/USDT", "DAI/USDT", "ETC/USDT", "ONDO/USDT", "NEAR/USDT", "OKB/USDT", 
    "APT/USDT", "ICP/USDT", "ALGO/USDT", "ATOM/USDT", "WBTC/USDT", "TON/USDT", 
    "USDS/USDT", "ENA/USDT", "TAO/USDT", "MNT/USDT", "JITOSOL/USDT", "KAS/USDT", 
    "PENGU/USDT", "ARB/USDT", "BONK/USDT", "RENDER/USDT", "POL/USDT", "WLD/USDT", 
    "STORY/USDT", "TRUMP/USDT", "SEI/USDT", "SKY/USDT", "HYPE/USDT", "WBETH/USDT", 
    "MKR/USDT", "FIL/USDT", "OP/USDT", "IOTA/USDT" # Primeiros 60 pares
]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Mude para INFO para menos logs, DEBUG para mais detalhes
)
logger = logging.getLogger(__name__)

# Dicionário global para armazenar instâncias de exchanges (carregadas uma vez)
global_exchanges_instances = {}

# --- Funções Auxiliares para Busca Concorrente ---
async def fetch_market_data_for_exchange(exchange, pair, ex_id):
    """
    Busca dados de mercado para um par específico em uma única exchange.
    Retorna uma tupla (ex_id, market_data) ou None em caso de erro/dados inválidos.
    """
    try:
        # Verifica se o par está disponível na exchange antes de tentar buscar o order book
        if pair in exchange.markets and exchange.has['fetchOrderBook']:
            order_book = await exchange.fetch_order_book(pair, limit=100) 
            
            if order_book and order_book['bids'] and order_book['asks']:
                best_bid = order_book['bids'][0][0] # Melhor preço de compra (para quem vende)
                best_bid_volume = order_book['bids'][0][1]
                best_ask = order_book['asks'][0][0] # Melhor preço de venda (para quem compra)
                best_ask_volume = order_book['asks'][0][1]

                # Sanity check: Preços devem ser positivos e ask >= bid
                if best_bid > 0 and best_ask > 0 and best_ask >= best_bid:
                    return (ex_id, {
                        'bid': best_bid,
                        'bid_volume': best_bid_volume,
                        'ask': best_ask,
                        'ask_volume': best_ask_volume,
                        'timestamp': order_book.get('timestamp') # Inclui o timestamp original
                    })
                else:
                    logger.debug(f"Dados inválidos para {pair} em {ex_id} (preço não positivo ou ask < bid): Bid={best_bid}, Ask={best_ask}")
            else:
                logger.debug(f"Livro de ofertas vazio ou inválido para {pair} em {ex_id}")
        else:
            logger.debug(f"Par {pair} não disponível ou fetchOrderBook não suportado em {ex_id}")
    except ccxt.NetworkError as e:
        logger.warning(f"Erro de rede ao buscar {pair} em {ex_id}: {e}")
    except ccxt.ExchangeError as e:
        logger.warning(f"Erro da exchange ao buscar {pair} em {ex_id}: {e}")
    except Exception as e:
        logger.warning(f"Erro inesperado ao buscar {pair} em {ex_id}: {e}")
    return None # Retorna None se a busca falhou ou os dados são inválidos

# Função principal para checar arbitragem
async def check_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    job = context.job

    chat_id = context.bot_data.get('admin_chat_id')
    if not chat_id:
        logger.warning("Nenhum chat_id de administrador configurado. Use /start para registrar.")
        return

    lucro_minimo_porcentagem = context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
    trade_amount_usd = context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
    fee_percentage = context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE)

    # Inicializa o dicionário para rastrear as oportunidades ativas e os últimos alertas
    if 'active_opportunities' not in context.bot_data:
        context.bot_data['active_opportunities'] = {} # { (pair, buy_ex, sell_ex): { 'buy_price': float, 'sell_price': float, 'net_profit': float, 'volume': float, 'last_alert_time': datetime, 'missed_scans': int } }

    current_scan_opportunities = {} # Oportunidades válidas encontradas nesta varredura

    logger.info(f"Iniciando checagem de arbitragem. Lucro mínimo: {lucro_minimo_porcentagem}%, Volume de trade: {trade_amount_usd} USD")

    # Usa as instâncias de exchanges carregadas globalmente
    exchanges_to_scan = {ex_id: instance for ex_id, instance in global_exchanges_instances.items()}
        
    if len(exchanges_to_scan) < 2:
        logger.error("Não há exchanges suficientes carregadas globalmente para verificar arbitragem.")
        await bot.send_message(chat_id=chat_id, text="Erro: Não foi possível conectar a exchanges suficientes para checar arbitragem.")
        return

    # Itera sobre cada par para encontrar oportunidades
    for pair in PAIRS:
        market_data_tasks = []
        for ex_id, exchange in exchanges_to_scan.items():
            market_data_tasks.append(
                fetch_market_data_for_exchange(exchange, pair, ex_id)
            )
        
        results = await asyncio.gather(*market_data_tasks, return_exceptions=True)

        market_data = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Erro durante a busca concorrente de dados: {result}")
            elif result:
                ex_id, data = result
                market_data[ex_id] = data
        
        if len(market_data) < 2:
            continue

        best_buy_ex = None
        best_buy_price = float('inf')
        best_buy_volume = 0

        best_sell_ex = None
        best_sell_price = 0.0
        best_sell_volume = 0

        for ex_id, data in market_data.items():
            if data['ask'] < best_buy_price:
                best_buy_price = data['ask']
                best_buy_ex = ex_id
                best_buy_volume = data['ask_volume']

            if data['bid'] > best_sell_price:
                best_sell_price = data['bid']
                best_sell_ex = ex_id
                best_sell_volume = data['bid_volume']

        if best_buy_ex == best_sell_ex:
            logger.debug(f"Melhores preços de compra e venda são na mesma exchange para {pair}. Pulando.")
            continue

        if best_buy_price == 0:
            logger.warning(f"Preço de compra zero para {pair}. Pulando arbitragem.")
            continue

        gross_profit_percentage = ((best_sell_price - best_buy_price) / best_buy_price) * 100

        if gross_profit_percentage > MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK:
            logger.warning(f"Lucro bruto irrealista para {pair} ({gross_profit_percentage:.2f}%). "
                           f"Dados suspeitos: Comprar em {best_buy_ex}: {best_buy_price}, Vender em {best_sell_ex}: {best_sell_price}. Pulando.")
            continue

        net_profit_percentage = gross_profit_percentage - (2 * fee_percentage)

        required_buy_volume = trade_amount_usd / best_buy_price if best_buy_price > 0 else float('inf')
        required_sell_volume = trade_amount_usd / best_sell_price if best_sell_price > 0 else float('inf')

        has_sufficient_liquidity = (
            best_buy_volume >= required_buy_volume and
            best_sell_volume >= required_sell_volume
        )

        # Se a oportunidade atende aos critérios mínimos, adiciona à lista da varredura atual
        if net_profit_percentage >= lucro_minimo_porcentagem and has_sufficient_liquidity:
            opportunity_key = (pair, best_buy_ex, best_sell_ex)
            current_scan_opportunities[opportunity_key] = {
                'buy_price': best_buy_price,
                'sell_price': best_sell_price,
                'net_profit': net_profit_percentage,
                'volume': trade_amount_usd
            }
        else:
            logger.debug(f"Arbitragem para {pair} não atende aos critérios: "
                         f"Lucro Líquido: {net_profit_percentage:.2f}% (Mínimo: {lucro_minimo_porcentagem}%), "
                         f"Liquidez Suficiente: {has_sufficient_liquidity}")

    # --- Lógica de Comparação e Alerta Inteligente ---
    opportunities_to_remove_from_active = []
    # Primeiro, atualiza os contadores de 'missed_scans' e identifica cancelamentos
    for key, opp_data in context.bot_data['active_opportunities'].items():
        if key not in current_scan_opportunities:
            # Oportunidade não encontrada nesta varredura, incrementa o contador
            opp_data['missed_scans'] = opp_data.get('missed_scans', 0) + 1
            if opp_data['missed_scans'] >= CANCELLATION_CONFIRM_SCANS:
                # Oportunidade realmente cancelada após N varreduras
                pair, buy_ex, sell_ex = key
                msg = (f"❌ Oportunidade para {pair} (CANCELADA)!\n"
                       f"Anteriormente: Compre em {buy_ex}: {opp_data['buy_price']:.8f}, Venda em {sell_ex}: {opp_data['sell_price']:.8f}\n"
                       f"Lucro Líquido Anterior: {opp_data['net_profit']:.2f}%\n"
                       f"Volume: ${opp_data['volume']:.2f}"
                )
                logger.info(msg)
                await bot.send_message(chat_id=chat_id, text=msg)
                opportunities_to_remove_from_active.append(key)
        else:
            # Oportunidade encontrada novamente, reseta o contador
            opp_data['missed_scans'] = 0
    
    # Remove as oportunidades canceladas do dicionário de ativos
    for key in opportunities_to_remove_from_active:
        del context.bot_data['active_opportunities'][key]

    # Verifica novas oportunidades ou oportunidades com mudanças significativas
    for key, current_opp_data in current_scan_opportunities.items():
        pair, buy_ex, sell_ex = key
        last_opp_data = context.bot_data['active_opportunities'].get(key)
        current_time_dt = datetime.now()

        should_alert = False
        if last_opp_data is None: # Nova oportunidade
            should_alert = True
        else:
            # Oportunidade existente: verifica mudança no lucro ou cooldown
            profit_diff = abs(current_opp_data['net_profit'] - last_opp_data['net_profit'])
            time_since_last_alert = (current_time_dt - last_opp_data['last_alert_time']).total_seconds()

            if profit_diff >= PROFIT_CHANGE_ALERT_THRESHOLD_PERCENT:
                should_alert = True # Lucro mudou significativamente
            elif time_since_last_alert >= COOLDOWN_PERIOD_FOR_ALERTS:
                should_alert = True # Cooldown expirou, mesmo que o lucro não tenha mudado muito

        if should_alert:
            msg = (f"💰 Arbitragem para {pair} ({current_time_dt.strftime('%H:%M:%S')})!\n"
                   f"Compre em {buy_ex}: {current_opp_data['buy_price']:.8f}\n"
                   f"Venda em {sell_ex}: {current_opp_data['sell_price']:.8f}\n"
                   f"Lucro Líquido: {current_opp_data['net_profit']:.2f}%\n"
                   f"Volume: ${current_opp_data['volume']:.2f}"
            )
            logger.info(msg)
            await bot.send_message(chat_id=chat_id, text=msg)
            # Atualiza os dados da oportunidade ativa
            context.bot_data['active_opportunities'][key] = {
                'buy_price': current_opp_data['buy_price'],
                'sell_price': current_opp_data['sell_price'],
                'net_profit': current_opp_data['net_profit'],
                'volume': current_opp_data['volume'],
                'last_alert_time': current_time_dt,
                'missed_scans': 0 # Reseta o contador de scans perdidos
            }

    except Exception as e:
        logger.error(f"Erro geral na checagem de arbitragem: {e}", exc_info=True)
        if chat_id:
            await bot.send_message(chat_id=chat_id, text=f"Erro crítico na checagem de arbitragem: {e}")
    finally:
        # As conexões das exchanges são fechadas apenas no final do main()
        # para que as instâncias globais permaneçam abertas durante as varreduras.
        pass # Removido o close() aqui

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Armazena o chat_id do usuário que iniciou o bot para enviar alertas
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Ativado.\n"
        "Monitorando oportunidades de arbitragem de criptomoedas.\n"
        f"Lucro mínimo atual: {context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)}%\n"
        f"Volume de trade para liquidez: ${context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD):.2f}\n"
        f"Taxa de negociação por lado: {context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE)}%\n\n"
        "Use /setlucro <valor> para definir o lucro mínimo em %.\n"
        "Exemplo: /setlucro 3\n\n"
        "Use /setvolume <valor> para definir o volume de trade em USD para checagem de liquidez.\n"
        "Exemplo: /setvolume 100\n\n"
        "Use /setfee <valor> para definir a taxa de negociação por lado em %.\n"
        "Exemplo: /setfee 0.075"
    )
    logger.info(f"Bot iniciado por chat_id: {update.message.chat_id}")

# Comando /setlucro
async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("O lucro mínimo não pode ser negativo.")
            return
        context.bot_data['lucro_minimo_porcentagem'] = valor
        await update.message.reply_text(f"Lucro mínimo atualizado para {valor:.2f}%")
        logger.info(f"Lucro mínimo definido para {valor}% por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setlucro 2.5")

# Comando /setvolume
async def setvolume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor <= 0:
            await update.message.reply_text("O volume de trade deve ser um valor positivo.")
            return
        context.bot_data['trade_amount_usd'] = valor
        await update.message.reply_text(f"Volume de trade para checagem de liquidez atualizado para ${valor:.2f} USD")
        logger.info(f"Volume de trade definido para ${valor} por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setvolume 100")

# Comando /setfee
async def setfee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("A taxa de negociação não pode ser negativa.")
            return
        context.bot_data['fee_percentage'] = valor
        await update.message.reply_text(f"Taxa de negociação por lado atualizada para {valor:.3f}%")
        logger.info(f"Taxa de negociação definida para {valor}% por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setfee 0.075")

# FUNÇÃO PRINCIPAL DO BOT
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Inicializa e carrega os mercados de todas as exchanges UMA VEZ
    logger.info("Carregando mercados das exchanges (isso pode levar alguns segundos)...")
    for ex_id in EXCHANGES_LIST:
        try:
            exchange_class = getattr(ccxt, ex_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 3000,
            })
            await exchange.load_markets()
            global_exchanges_instances[ex_id] = exchange
            logger.info(f"Exchange {ex_id} carregada com sucesso.")
        except Exception as e:
            logger.error(f"ERRO CRÍTICO: Não foi possível carregar a exchange {ex_id}. Ela será ignorada. Erro: {e}")
            # Não remove do EXCHANGES_LIST, mas não adiciona à global_exchanges_instances
            # para que as varreduras não tentem usá-la.

    if len(global_exchanges_instances) < 2:
        logger.error("ERRO CRÍTICO: Menos de 2 exchanges foram carregadas com sucesso. O bot não pode operar.")
        # Aqui você pode adicionar uma forma de notificar o admin ou encerrar o bot se for o caso
        # Por enquanto, o bot continuará tentando, mas as varreduras falharão.

    # Adiciona handlers para os comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("setfee", setfee))

    # Adiciona a tarefa periódica de arbitragem
    # O 'first=5' faz a primeira execução 5 segundos após o bot iniciar
    # O 'interval=60' executa a cada 60 segundos (1 minuto)
    application.job_queue.run_repeating(check_arbitrage, interval=60, first=5)

    # Define os comandos que aparecerão no Telegram
    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot e ver configurações"),
        BotCommand("setlucro", "Definir lucro mínimo em % (Ex: /setlucro 2.5)"),
        BotCommand("setvolume", "Definir volume de trade em USD para liquidez (Ex: /setvolume 100)"),
        BotCommand("setfee", "Definir taxa de negociação por lado em % (Ex: /setfee 0.075)")
    ])

    logger.info("Bot iniciado com sucesso e aguardando mensagens...")
    # Inicia o polling para receber atualizações do Telegram
    try:
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally: # Este bloco 'finally' é executado sempre, mesmo se houver exceções
        # Fechar todas as conexões das exchanges quando o bot for encerrado
        logger.info("Fechando conexões das exchanges...")
        for exchange in global_exchanges_instances.values():
            try:
                await exchange.close()
            except Exception as e:
                logger.error(f"Erro inesperado ao fechar conexão da exchange {exchange.id}: {e}")

if __name__ == "__main__":
    asyncio.run(main())

