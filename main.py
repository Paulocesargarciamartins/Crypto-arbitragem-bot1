import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import ccxt.async_support as ccxt
import os
import nest_asyncio

# Aplica o patch para permitir loops aninhados,
# corrigindo o problema no ambiente Heroku
nest_asyncio.apply()

# --- Configurações básicas ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# LUCRO_MINIMO_PORCENTAGEM será gerenciado via comando /setlucro
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0 # Quantidade de USD para verificar liquidez
DEFAULT_FEE_PERCENTAGE = 0.1 # Taxa de negociação média por lado (0.1% é comum)

# Novo: Limite máximo de lucro bruto para validação de dados.
# Se o lucro bruto for maior que isso, consideramos que os dados estão incorretos.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 500.0 # 500% é um valor muito alto, mas seguro para filtrar erros grotescos.

# Exchanges confiáveis para monitorar (20)
# Nota: Nem todas as exchanges suportam todos os pares ou têm as mesmas APIs.
# Algumas podem exigir chaves de API para acesso a dados de mercado.
EXCHANGES_LIST = [
    'binance', 'coinbasepro', 'kraken', 'bitfinex', 'bittrex',
    'huobipro', 'okex', 'bitstamp', 'gateio', 'kucoin',
    'poloniex', 'bybit', 'coinex', 'bitget', 'ascendex',
    'bibox', 'bitflyer', 'digifinex', 'mexc', 'lbank' # Substituindo ftx (falida) e adicionando mais algumas
]

# Pares USDT (reduzido para evitar sobrecarga de requisições durante o teste/exemplo)
# Para produção, você pode usar a lista completa de 150 pares.
PAIRS = [
    "ADA/USDT", "BTC/USDT", "ETH/USDT", "XRP/USDT", "BNB/USDT", "SOL/USDT",
    "DOGE/USDT", "LINK/USDT", "AVAX/USDT", "LTC/USDT"
]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Mude para INFO para menos logs, DEBUG para mais detalhes
)
logger = logging.getLogger(__name__)

# --- Funções do Bot ---

# Função para checar arbitragem entre exchanges
async def check_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    job = context.job

    # Obtém o chat_id para enviar mensagens.
    # Se o bot for reiniciado e ninguém usou /start, pode ser None.
    # Idealmente, você persistiria o chat_id em um banco de dados.
    chat_id = context.bot_data.get('admin_chat_id')
    if not chat_id:
        logger.warning("Nenhum chat_id de administrador configurado. Use /start para registrar.")
        return

    # Obtém o lucro mínimo e o valor de trade do bot_data, ou usa os defaults
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
                    'timeout': 10000, # 10 segundos de timeout
                })
                await exchange.load_markets()
                exchanges_instances[ex_id] = exchange
            except Exception as e:
                logger.warning(f"Não foi possível carregar a exchange {ex_id}: {e}")
                if ex_id in exchanges_instances: # Remove se houve erro após inicialização parcial
                    await exchanges_instances[ex_id].close()
                    del exchanges_instances[ex_id]
        
        if len(exchanges_instances) < 2:
            logger.error("Não há exchanges suficientes carregadas para verificar arbitragem.")
            await bot.send_message(chat_id=chat_id, text="Erro: Não foi possível conectar a exchanges suficientes para checar arbitragem.")
            return

        # Itera sobre cada par para encontrar oportunidades
        for pair in PAIRS:
            market_data = {} # Armazena bid/ask/volume para cada exchange para o par atual
            
            for ex_id, exchange in exchanges_instances.items():
                try:
                    # Verifica se o par existe na exchange e se suporta fetch_order_book
                    if pair in exchange.markets and exchange.has['fetchOrderBook']:
                        # Busca o livro de ofertas para verificar liquidez
                        # Aumentado o limite para 20 para uma visão mais robusta
                        order_book = await exchange.fetch_order_book(pair, limit=20) 
                        
                        if order_book and order_book['bids'] and order_book['asks']:
                            best_bid = order_book['bids'][0][0] # Melhor preço de compra (para quem vende)
                            best_bid_volume = order_book['bids'][0][1]
                            best_ask = order_book['asks'][0][0] # Melhor preço de venda (para quem compra)
                            best_ask_volume = order_book['asks'][0][1]

                            # Sanity check: Preços devem ser positivos e ask >= bid
                            if best_bid > 0 and best_ask > 0 and best_ask >= best_bid:
                                market_data[ex_id] = {
                                    'bid': best_bid,
                                    'bid_volume': best_bid_volume,
                                    'ask': best_ask,
                                    'ask_volume': best_ask_volume,
                                }
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

            # Novo: Sanity check para o lucro bruto
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
                # Mensagem de alerta simplificada
                msg = (f"💰 Arbitragem para {pair}!\n"
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
        # Fechar todas as conexões das exchanges
        for exchange in exchanges_instances.values():
            try:
                await exchange.close()
            except Exception as e:
                logger.error(f"Erro ao fechar conexão da exchange {exchange.id}: {e}")

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
    # O 'interval=60' executa a cada 60 segundos
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
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())

