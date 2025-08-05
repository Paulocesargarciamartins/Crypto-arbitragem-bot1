import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

# Configuração básica do logging
logging.basicConfig(
    format='[%(levelname)s] %(asctime)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "1093248456")

# Parâmetros
DEFAULT_MIN_PROFIT = 1.0  # lucro mínimo em %

# Lista de pares USDT (exemplo com 15 pares, pode expandir)
pairs = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT",
    "BNBUSDT", "DOGEUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT",
    "AVAXUSDT", "TRXUSDT", "SHIBUSDT", "MATICUSDT", "ATOMUSDT"
]

# Exchanges e seus endpoints para obter preço
exchanges = {
    "Binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "Coinbase": "https://api.coinbase.com/v2/prices/{}-USDT/spot",
    "KuCoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    "Bitstamp": "https://www.bitstamp.net/api/v2/ticker/{}.json",
    "MercadoBitcoin": "https://www.mercadobitcoin.net/api/{}/ticker/",
}

# Variável global para lucro mínimo, atualizável via comando
min_profit = DEFAULT_MIN_PROFIT

async def get_price(session: aiohttp.ClientSession, exchange: str, symbol: str):
    url = exchanges[exchange].format(symbol)
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"[Erro] {exchange}: status {resp.status} para {url}")
                return None
            data = await resp.json()
            if exchange == "Binance":
                return float(data['price'])
            elif exchange == "Coinbase":
                return float(data['data']['amount'])
            elif exchange == "KuCoin":
                return float(data['data']['price'])
            elif exchange == "Bitstamp":
                return float(data['last'])
            elif exchange == "MercadoBitcoin":
                return float(data['ticker']['last'])
    except Exception as e:
        logger.warning(f"[Erro] {exchange}: {e}")
        return None

async def check_arbitrage(bot):
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
                logger.debug(f"{pair} - Preços: {prices}")
                if profit >= min_profit:
                    message = (
                        f"💰 Oportunidade de arbitragem!\n\n"
                        f"🪙 Par: {pair}\n"
                        f"🔻 Comprar: {min_ex} a {min_price:.2f}\n"
                        f"🔺 Vender: {max_ex} a {max_price:.2f}\n"
                        f"📈 Lucro estimado: {profit:.2f}%"
                    )
                    try:
                        await bot.send_message(chat_id=CHAT_ID, text=message)
                        logger.info(f"Alerta enviado para {pair} com lucro {profit:.2f}%")
                    except Exception as e:
                        logger.error(f"Erro ao enviar mensagem Telegram: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Sou seu bot de arbitragem.\n"
        "Use /setprofit <valor> para definir o lucro mínimo em %.\n"
        "Exemplo: /setprofit 1.5"
    )

async def set_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global min_profit
    try:
        if len(context.args) != 1:
            raise ValueError("Número errado de argumentos")
        value = float(context.args[0].replace(',', '.'))
        if value <= 0:
            raise ValueError("Lucro deve ser maior que zero")
        min_profit = value
        await update.message.reply_text(f"Lucro mínimo configurado para {min_profit}%")
    except Exception:
        await update.message.reply_text("Uso correto: /setprofit <valor_em_porcentagem>")

async def arbitrage_job(app):
    await check_arbitrage(app.bot)

async def periodic_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    await check_arbitrage(context.bot)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setprofit", set_profit))

    # Executa a checagem a cada 60 segundos
    app.job_queue.run_repeating(periodic_arbitrage, interval=60, first=5)

    logger.info("Bot iniciado")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
