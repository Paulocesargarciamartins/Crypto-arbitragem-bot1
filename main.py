import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.async_support as ccxt
import os

# Configurações básicas
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Configure no Heroku config vars
LUCRO_MINIMO_PORCENTAGEM = 2.0  # Exemplo, pode ajustar e mandar via comando Telegram

# Exchanges confiáveis para monitorar (20)
EXCHANGES_LIST = [
    'binance', 'coinbasepro', 'kraken', 'bitfinex', 'bittrex',
    'huobipro', 'okex', 'bitstamp', 'gateio', 'kucoin',
    'poloniex', 'ftx', 'bitmart', 'bybit', 'coinex',
    'bitget', 'ascendex', 'bibox', 'bitflyer', 'digifinex'
]

# Pares USDT (exemplo curto, você pode ampliar)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", "LTC/USDT",
    # ... até 100 pares (adicione conforme seu histórico)
]

logging.basicConfig(
    format='[%(levelname)s] %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Função para checar arbitragem entre exchanges
async def check_arbitrage(bot):
    try:
        exchanges = {}
        for ex_id in EXCHANGES_LIST:
            exchange = getattr(ccxt, ex_id)({
                'enableRateLimit': True,
            })
            await exchange.load_markets()
            exchanges[ex_id] = exchange

        for pair in PAIRS:
            prices = {}
            for ex_id, exchange in exchanges.items():
                if pair in exchange.markets:
                    ticker = await exchange.fetch_ticker(pair)
                    prices[ex_id] = ticker['last']
            if len(prices) < 2:
                continue

            min_ex = min(prices, key=prices.get)
            max_ex = max(prices, key=prices.get)
            min_price = prices[min_ex]
            max_price = prices[max_ex]

            lucro = (max_price - min_price) / min_price * 100

            if lucro >= LUCRO_MINIMO_PORCENTAGEM:
                msg = (f"🟢 Arbitragem encontrada para {pair}!\n"
                       f"Comprar em {min_ex}: {min_price}\n"
                       f"Vender em {max_ex}: {max_price}\n"
                       f"Lucro estimado: {lucro:.2f}%")
                logger.info(msg)
                await bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text=msg)

        # Fechar exchanges para liberar recursos
        for exchange in exchanges.values():
            await exchange.close()

    except Exception as e:
        logger.error(f"Erro na checagem de arbitragem: {e}")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Ativado.\n"
        "Use /setlucro <valor> para definir lucro mínimo em %.\n"
        "Exemplo: /setlucro 3"
    )

# Comando /setlucro
async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LUCRO_MINIMO_PORCENTAGEM
    try:
        valor = float(context.args[0])
        LUCRO_MINIMO_PORCENTAGEM = valor
        await update.message.reply_text(f"Lucro mínimo atualizado para {valor}%")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setlucro 2.5")

# A ÚNICA FUNÇÃO PRINCIPAL QUE RODA DE FATO
def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))

    # Agendar tarefa de arbitragem a cada 60 segundos
    async def periodic_arbitrage_task(context: ContextTypes.DEFAULT_TYPE):
        await check_arbitrage(application.bot)

    application.job_queue.run_repeating(periodic_arbitrage_task, interval=60, first=5)

    # Comandos oficiais (exibir no Telegram). O run_polling() fará a inicialização.
    asyncio.run(application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot"),
        BotCommand("setlucro", "Definir lucro mínimo em %")
    ]))

    logger.info("Bot iniciado com sucesso.")
    application.run_polling()

if __name__ == "__main__":
    run_bot()
