import os
import asyncio
import aiohttp
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EXCHANGES = [
    ("https://api.binance.com/api/v3/ticker/price", "symbol", "price", "Binance"),
    ("https://api.coinbase.com/v2/exchange-rates", "data", "rates", "Coinbase"),
    # Adicione outras exchanges aqui, se quiser
]

COINS = ["BTC", "ETH", "LTC", "XRP", "BCH", "ADA", "SOL", "DOT", "AVAX", "DOGE", "TRX", "XLM", "BNB", "MATIC"]

bot = Bot(token=TOKEN)

async def fetch_prices(session, url, base_key, price_key, exchange_name):
    prices = {}
    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()
            for coin in COINS:
                symbol = f"{coin}USDT"
                if exchange_name == "Binance":
                    for item in data:
                        if item["symbol"] == symbol:
                            prices[coin] = float(item["price"])
                elif exchange_name == "Coinbase":
                    try:
                        prices[coin] = 1 / float(data["data"]["rates"][coin])
                    except KeyError:
                        pass
    except Exception as e:
        print(f"Erro na {exchange_name}: {e}")
    return exchange_name, prices

async def comparar():
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(fetch_prices(session, *ex) for ex in EXCHANGES))

        all_prices = {name: prices for name, prices in results}
        alerts = []

        for coin in COINS:
            valores = [(exchange, prices.get(coin)) for exchange, prices in all_prices.items() if coin in prices]
            for i in range(len(valores)):
                for j in range(i + 1, len(valores)):
                    (ex1, p1), (ex2, p2) = valores[i], valores[j]
                    if p1 and p2:
                        menor, maior = min(p1, p2), max(p1, p2)
                        lucro = (maior - menor) / menor * 100
                        if lucro >= 1.0:
                            alert = f"💰 Arbitragem: {coin}\n{ex1}: ${p1:.2f} | {ex2}: ${p2:.2f}\nLucro: {lucro:.2f}%"
                            alerts.append(alert)

        if alerts:
            msg = "\n\n".join(alerts)
            await bot.send_message(chat_id=CHAT_ID, text=f"🚨 Oportunidades:\n\n{msg}")
        else:
            print("Nenhuma arbitragem encontrada no momento.")

async def main_loop():
    while True:
        await comparar()
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Bot encerrado.")
