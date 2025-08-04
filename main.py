import os
import asyncio
import aiohttp
from telegram import Bot

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "1093248456"
bot = Bot(token=TOKEN)

pairs = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT",
    "BNBUSDT", "DOGEUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT",
    "AVAXUSDT", "TRXUSDT", "SHIBUSDT", "MATICUSDT", "ATOMUSDT"
]

exchanges = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "coinbase": "https://api.coinbase.com/v2/prices/{}-USDT/spot",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
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
    except Exception:
        return None

async def check_arbitrage():
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
                if profit >= 1:  # lucro mínimo de 1%
                    message = (
                        f"💰 Oportunidade de arbitragem!\n\n"
                        f"🪙 Par: {pair}\n"
                        f"🔻 Comprar: {min_ex} a {min_price:.2f}\n"
                        f"🔺 Vender: {max_ex} a {max_price:.2f}\n"
                        f"📈 Lucro estimado: {profit:.2f}%"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=message)

async def main():
    while True:
        await check_arbitrage()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
