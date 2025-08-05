import os
import asyncio
import aiohttp
import logging
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuração logging debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID", "1093248456"))

# Variável global para lucro mínimo, default 1%
lucro_minimo = 1.0

pairs = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT",
    "BNBUSDT", "DOGEUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT",
    "AVAXUSDT", "TRXUSDT", "SHIBUSDT", "MATICUSDT", "ATOMUSDT"
]

exchanges = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "coinbase": "https://api.coinbase.com/v2/prices/{}-USDT/spot",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    # Você pode adicionar mais exchanges aqui conforme a necessidade
}

async def get_price(session, exchange, symbol):
    url = exchanges[exchange].format(symbol)
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            if exchange == "binance":
                return float(data['price'])
            elif exchange == "coinbase":
                return float(data['data']['amount'])
            elif exchange == "kucoin":
                return float(data['data']['price'])
    except Exception as e:
        logger.error(f"[Erro] {exchange}: {e}")
        return None

async def check_arbitrage(bot: Bot):
    async with aiohttp.ClientSession() as session:
        for pair in pairs:
            prices = {}
            for exchange in exchanges:
                price = await get_price(session, exchange, pair)
                if price:
                    prices[exchange] = price
            if len(prices) >= 2:
                min_ex = min(prices, key=prices.get)
                max_ex = max(prices, key=prices.get)
                min_price = prices[min_ex]
                max_price = prices[max_ex]
                profit = ((max_price - min_price) / min_price) * 100
                logger.debug(f"{pair} | {min_ex}={min_price} | {max_ex}={max_price} | lucro={profit:.2f}%")
                if profit >= lucro_minimo:
                    message = (
                        f"💰 Oportunidade de arbitragem!\n\n"
                        f"🪙 Par: {pair}\n"
                        f"🔻 Comprar: {min_ex} a {min_price:.2f}\n"
                        f"🔺 Vender: {max_ex} a {max_price:.2f}\n"
                        f"📈 Lucro estimado: {profit:.2f}%"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=message)

async def loop_arbitrage(app):
    while True:
        await check_arbitrage(app.bot)
        await asyncio.sleep(60)  # Intervalo de 60 segundos

# Comando /setlucro para alterar o lucro mínimo pelo Telegram
async def set_lucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global lucro_minimo
    if not context.args:
        await update.message.reply_text("Por favor, envie o valor do lucro mínimo. Exemplo: /setlucro 2.5")
        return
    try:
        valor = float(context.args[0])
        if valor <= 0:
            await update.message.reply_text("O valor deve ser maior que 0.")
            return
        lucro_minimo = valor
        await update.message.reply_text(f"Lucro mínimo alterado para {lucro_minimo:.2f}%")
    except ValueError:
        await update.message.reply_text("Valor inválido. Envie um número decimal. Exemplo: /setlucro 2.5")

# Comando /getlucro para mostrar o lucro mínimo atual
async def get_lucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Lucro mínimo atual é {lucro_minimo:.2f}%")

# Comando /start para boas vindas
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Bot de arbitragem ativo.\n"
        "Use /setlucro <valor> para definir lucro mínimo.\n"
        "Use /getlucro para ver o lucro mínimo atual."
    )

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlucro", set_lucro))
    app.add_handler(CommandHandler("getlucro", get_lucro))

    # Inicia o loop da arbitragem em paralelo
    app.job_queue.run_repeating(lambda ctx: asyncio.create_task(check_arbitrage(app.bot)), interval=60, first=1)

    logger.info("Bot iniciado e monitorando arbitragem...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
