import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "")  # pode deixar em branco ou fixar

MIN_PROFIT_PERCENTAGE = 2.0

EXCHANGES = [
    "binance", "coinbase", "kucoin", "kraken", "gateio", "bitfinex", "okx",
    "mexc", "huobi", "bitstamp", "bybit", "bitget", "bittrex", "poloniex"
]

PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "LTC/USDT", "SOL/USDT", "ADA/USDT",
    "AVAX/USDT", "DOGE/USDT", "DOT/USDT", "TRX/USDT", "MATIC/USDT", "LINK/USDT",
    "BCH/USDT", "XLM/USDT", "UNI/USDT", "ATOM/USDT", "ETC/USDT", "HBAR/USDT",
    "NEAR/USDT", "VET/USDT", "FIL/USDT", "XTZ/USDT", "EOS/USDT", "THETA/USDT",
    "ICP/USDT", "AAVE/USDT", "QNT/USDT", "FLOW/USDT", "GRT/USDT", "ALGO/USDT",
    "SAND/USDT", "MANA/USDT", "EGLD/USDT", "FTM/USDT", "RUNE/USDT", "KAVA/USDT",
    "1INCH/USDT", "BAT/USDT", "ZRX/USDT", "ENJ/USDT", "SNX/USDT", "COMP/USDT",
    "YFI/USDT", "LRC/USDT", "OMG/USDT", "CRV/USDT", "BAL/USDT", "ANKR/USDT",
    "WAVES/USDT", "KSM/USDT", "SRM/USDT", "REN/USDT", "CELR/USDT", "CVC/USDT",
    "CHZ/USDT", "SKL/USDT", "SXP/USDT", "BNT/USDT", "DGB/USDT", "STMX/USDT",
    "OCEAN/USDT", "ARDR/USDT", "FET/USDT", "NKN/USDT", "POND/USDT", "MDT/USDT",
    "BLZ/USDT", "XVS/USDT", "COTI/USDT", "RSR/USDT", "REEF/USDT", "DENT/USDT",
    "HOT/USDT", "WIN/USDT", "PERL/USDT", "TOMO/USDT", "VITE/USDT", "DOCK/USDT",
    "NULS/USDT", "CTSI/USDT", "STPT/USDT", "RIF/USDT", "VIDT/USDT", "TRB/USDT",
    "XEM/USDT", "STRAX/USDT", "LPT/USDT", "MTL/USDT", "CVC/USDT", "POWR/USDT",
    "AMB/USDT", "FUN/USDT", "TROY/USDT", "MIR/USDT", "FRONT/USDT", "ALPHA/USDT",
    "ORN/USDT", "UTK/USDT", "FORTH/USDT", "MFT/USDT", "LIT/USDT", "TWT/USDT"
]


async def fetch_price(session, exchange, pair):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={pair.split('/')[0].lower()}&vs_currencies=usd"
        async with session.get(url) as response:
            data = await response.json()
            return data.get(pair.split('/')[0].lower(), {}).get("usd")
    except:
        return None


async def check_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    global MIN_PROFIT_PERCENTAGE
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                price = await fetch_price(session, exchange, pair)
                if price:
                    prices[exchange] = price

            if len(prices) >= 2:
                min_exchange = min(prices, key=prices.get)
                max_exchange = max(prices, key=prices.get)
                min_price = prices[min_exchange]
                max_price = prices[max_exchange]
                profit_percent = ((max_price - min_price) / min_price) * 100

                if profit_percent >= MIN_PROFIT_PERCENTAGE:
                    message = (
                        f"💰 Oportunidade de arbitragem!\n"
                        f"Par: {pair}\n"
                        f"Comprar em: {min_exchange.upper()} por ${min_price:.2f}\n"
                        f"Vender em: {max_exchange.upper()} por ${max_price:.2f}\n"
                        f"Lucro estimado: {profit_percent:.2f}%"
                    )
                    await context.bot.send_message(chat_id=CHAT_ID, text=message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot de arbitragem iniciado! Use /porcentagem X para alterar o lucro mínimo.")


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponíveis:\n/start\n/ajuda\n/porcentagem X")


async def set_porcentagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MIN_PROFIT_PERCENTAGE
    try:
        value = float(context.args[0])
        MIN_PROFIT_PERCENTAGE = value
        await update.message.reply_text(f"🛠️ Nova margem de lucro definida: {value:.2f}%")
    except:
        await update.message.reply_text("Erro. Use o comando assim: /porcentagem 2.5")


async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("porcentagem", set_porcentagem))

    job_queue = app.job_queue
    job_queue.run_repeating(check_arbitrage, interval=60, first=10)

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
