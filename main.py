import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import ccxt.async_support as ccxt
import os
import nest_asyncio
from datetime import datetime

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
# Ajustado para 100.0% conforme solicitado.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0 

# Exchanges confiáveis para monitorar (agora 17, Coinex removida)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'bitfinex', 'bittrex',
    'huobi', 'okx', 'bitstamp', 'kucoin',
    'poloniex', 'bybit', 'bitget', 'ascendex', 
    'bibox', 'bitflyer', 'digifinex', 'mexc' 
]


# Pares USDT (lista completa de 150 pares)
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
    "MKR/USDT", "FIL/USDT", "OP/USDT", "IOTA/USDT", "DASH/USDT", "NEXO/USDT", 
    "SUSHI/USDT", "BGB/USDT", "WIF/USDT", "FLOW/USDT", "IMX/USDT", "RUNE/USDT", 
    "LDO/USDT", "FET/USDT", "GRT/USDT", "FTM/USDT", "QNT/USDT", "STRK/USDT", 
    "VET/USDT", "INJ/USDT", "DYDX/USDT", "EGLD/USDT", "JUP/USDT", "GALA/USDT", 
    "AXS/USDT", "THETA/USDT", "MINA/USDT", "ENJ/USDT", "CHZ/USDT", "YFI/USDT", 
    "GMX/USDT", "ZEC/USDT", "ZIL/USDT", "GMT/USDT", "WAVES/USDT", "KLAY/USDT", 
    "KAVA/USDT", "CELO/USDT", "XEC/USDT", "HNT/USDT", "RSR/USDT", "RVN/USDT", 
    "BAT/USDT", "DCR/USDT", "DGB/USDT", "XEM/USDT", "SC/USDT", "ZEN/USDT", 
    "COMP/USDT", "SNX/USDT", "UMA/USDT", "CRV/USDT", "KNC/USDT", "BAL/USDT", 
    "ZRX/USDT", "OGN/USDT", "RLC/USDT", "BAND/USDT", "TOMO/USDT", "AR/USDT", 
    "PERP/USDT", "LINA/USDT", "ANKR/USDT", "OCEAN/USDT", "SFP/USDT", "ONE/USDT", 
    "PHA/USDT", "CKB/USDT", "CTK/USDT", "YFII/USDT", "BOND/USDT", "UTK/USDT", 
    "CVC/USDT", "IRIS/USDT", "NULS/USDT", "NKN/USDT", "STX/USDT", "DODO/USDT", 
    "NMR/USDT", "MCO/USDT", "LPT/USDT", "SKL/USDT", "REQ/USDT", "CQT/USDT", 
    "WTC/USDT", "TCT/USDT", "COTI/USDT", "MDT/USDT", "TFUEL/USDT", "TUSD/USDT", 
    "SRM/USDT", "GLM/USDT", "MANA/USDT", "SAND/USDT", "ICP/USDT", "APE/USDT"
]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Mude para INFO para menos logs, DEBUG para mais detalhes
)
logger = logging.getLogger(__name__)

# --- Funções Auxiliares para Busca Concorrente ---
async def fetch_market_data_for_exchange(exchange, pair, ex_id):
    """
    Busca dados de mercado para um par específico em uma única exchange.
    Retorna uma tupla (ex_id, market_data) ou None em caso de erro/dados inválidos.
    """
    try:
        if pair in exchange.markets and exchange.has['fetchOrderBook']:
            # Busca o livro de ofertas para verificar liquidez
            # Aumentado o limite para 100 para uma visão mais robusta e compatibilidade com Kucoin
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

    logger.info(f"Iniciando checagem de arbitragem. Lucro mínimo: {lucro_minimo_porcentagem}%, Volume de trade: {trade_amount_usd} USD")

    exchanges_instances = {}
    try:
        # Inicializa as exchanges
        for ex_id in EXCHANGES_LIST:
            try:
                exchange_class = getattr(ccxt, ex_id)
                exchange = exchange_class({
                    'enableRateLimit': True, # Garante que o ccxt respeite os limites de taxa da API
                    'timeout': 5000, # Reduzido timeout para 5 segundos para requisições mais rápidas
                })
                await exchange.load_markets()
                exchanges_instances[ex_id] = exchange
            except Exception as e:
                logger.warning(f"Não foi possível carregar a exchange {ex_id}: {e}")
                if ex_id in exchanges_instances:
                    await exchanges_instances[ex_id].close()
                    del exchanges_instances[ex_id]
        
        if len(exchanges_instances) < 2:
            logger.error("Não há exchanges suficientes carregadas para verificar arbitragem.")
            await bot.send_message(chat_id=chat_id, text="Erro: Não foi possível conectar a exchanges suficientes para checar arbitragem.")
            return

        # Itera sobre cada par para encontrar oportunidades
        for pair in PAIRS:
            market_data_tasks = []
            for ex_id, exchange in exchanges_instances.items():
                # Cria uma tarefa para buscar os dados de cada exchange para o par atual
                market_data_tasks.append(
                    fetch_market_data_for_exchange(exchange, pair, ex_id)
                )
            
            # Executa todas as tarefas de busca para o par atual CONCORRENTEMENTE
            results = await asyncio.gather(*market_data_tasks, return_exceptions=True)

            market_data = {}
            for result in results:
                if isinstance(result, Exception):
                    # Loga a exceção mas não interrompe o processo principal
                    logger.warning(f"Erro durante a busca concorrente de dados: {result}")
                elif result: # result é (ex_id, data)
                    ex_id, data = result
                    market_data[ex_id] = data
            
            # Se não houver dados de pelo menos duas exchanges para o par, pular
            if len(market_data) < 2:
                continue

            # Encontrar a melhor oportunidade de arbitragem para o par
            best_buy_ex = None
            best_buy_price = float('inf')
            best_buy_volume = 0

            best_sell_ex = None
            best_sell_price = 0.0
            best_sell_volume = 0

            for ex_id, data in market_data.items():
                # Encontrar a exchange com o menor preço de compra (ask)
                if data['ask'] < best_buy_price:
                    best_buy_price = data['ask']
                    best_buy_ex = ex_id
                    best_buy_volume = data['ask_volume']

                # Encontrar a exchange com o maior preço de venda (bid)
                if data['bid'] > best_sell_price:
                    best_sell_price = data['bid']
                    best_sell_ex = ex_id
                    best_sell_volume = data['bid_volume']

            # Se as melhores exchanges para compra e venda forem as mesmas, não há arbitragem simples
            if best_buy_ex == best_sell_ex:
                logger.debug(f"Melhores preços de compra e venda são na mesma exchange para {pair}. Pulando.")
                continue

            # Calcular lucro bruto
            # Evitar divisão por zero
            if best_buy_price == 0:
                logger.warning(f"Preço de compra zero para {pair}. Pulando arbitragem.")
                continue

            gross_profit_percentage = ((best_sell_price - best_buy_price) / best_buy_price) * 100

            # Sanity check para o lucro bruto
            if gross_profit_percentage > MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK:
                logger.warning(f"Lucro bruto irrealista para {pair} ({gross_profit_percentage:.2f}%). "
                               f"Dados suspeitos: Comprar em {best_buy_ex}: {best_buy_price}, Vender em {best_sell_ex}: {best_sell_price}. Pulando.")
                continue

            # Calcular lucro líquido após taxas (compra + venda)
            net_profit_percentage = gross_profit_percentage - (2 * fee_percentage)

            # Verificar liquidez mínima
            # O volume necessário para o trade_amount_usd
            # Evitar divisão por zero caso o preço seja muito baixo
            required_buy_volume = trade_amount_usd / best_buy_price if best_buy_price > 0 else float('inf')
            required_sell_volume = trade_amount_usd / best_sell_price if best_sell_price > 0 else float('inf')

            has_sufficient_liquidity = (
                best_buy_volume >= required_buy_volume and
                best_sell_volume >= required_sell_volume
            )

            if net_profit_percentage >= lucro_minimo_porcentagem and has_sufficient_liquidity:
                # Mensagem de alerta simplificada com timestamp
                current_time = datetime.now().strftime("%H:%M:%S")
                msg = (f"💰 Arbitragem para {pair} ({current_time})!\n"
                       f"Compre em {best_buy_ex}: {best_buy_price:.8f}\n"
                       f"Venda em {best_sell_ex}: {best_sell_price:.8f}\n"
                       f"Lucro Líquido: {net_profit_percentage:.2f}%\n"
                       f"Volume: ${trade_amount_usd:.2f}"
                )
                logger.info(msg)
                await bot.send_message(chat_id=chat_id, text=msg)
            else:
                logger.debug(f"Arbitragem para {pair} não atende aos critérios: "
                             f"Lucro Líquido: {net_profit_percentage:.2f}% (Mínimo: {lucro_minimo_porcentagem}%), "
                             f"Liquidez Suficiente: {has_sufficient_liquidity}")

    except Exception as e:
        logger.error(f"Erro geral na checagem de arbitragem: {e}", exc_info=True)
        if chat_id:
            await bot.send_message(chat_id=chat_id, text=f"Erro crítico na checagem de arbitragem: {e}")
    finally:
        # Correção: Adiciona tratamento de erro para RuntimeError ao fechar exchanges
        for exchange in exchanges_instances.values():
            try:
                await exchange.close()
            except RuntimeError as e:
                logger.warning(f"Erro ao fechar conexão da exchange {exchange.id} (RuntimeError): {e}. Pode ocorrer durante o desligamento do loop.")
            except Exception as e:
                logger.error(f"Erro inesperado ao fechar conexão da exchange {exchange.id}: {e}")

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

    # Adiciona handlers para os comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("setfee", setfee))

    # Adiciona a tarefa periódica de arbitragem
    # O 'first=5' faz a primeira execução 5 segundos após o bot iniciar
    # O 'interval=90' executa a cada 90 segundos (1.5 minutos)
    application.job_queue.run_repeating(check_arbitrage, interval=90, first=5)

    # Define os comandos que aparecerão no Telegram
    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot e ver configurações"),
        BotCommand("setlucro", "Definir lucro mínimo em % (Ex: /setlucro 2.5)"),
        BotCommand("setvolume", "Definir volume de trade em USD para liquidez (Ex: /setvolume 100)"),
        BotCommand("setfee", "Definir taxa de negociação por lado em % (Ex: /setfee 0.075)")
    ])

    logger.info("Bot iniciado com sucesso e aguardando mensagens...")
    # Inicia o polling para receber atualizações do Telegram
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())

