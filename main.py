import os
import asyncio
import aiohttp
from telegram import Bot

# Configurações (exchanges e pares)
EXCHANGES = [
    "binance", "kucoin", "bitget", "bybit", "mexc", "gate", "poloniex",
    "huobi", "okx", "kraken", "bitfinex", "bittrex", "ftx", "coinbase"
]

# 20 pares mais líquidos exemplo — adapte se quiser (os mais comuns)
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT",
    "DOGEUSDT", "DOTUSDT", "LTCUSDT", "AVAXUSDT", "SHIBUSDT", "MATICUSDT",
    "ATOMUSDT", "LINKUSDT", "TRXUSDT", "ETCUSDT", "XLMUSDT", "NEARUSDT",
    "ALGOUSDT", "VETUSDT"
]

# Lucro mínimo para alertar (em %)
MIN_PROFIT = 5.0

# Função para pegar preços das exchanges (exemplo simplificado)
async def fetch_price(session, exchange, pair):
    # Aqui você deve colocar o endpoint real da API de cada exchange e adaptar.
    # Esse exemplo usa uma URL genérica, você precisa adaptar para cada exchange.
    url = f"https://api.{exchange}.com/api/v3/ticker/price?symbol={pair}"
    try:
        async with session.get(url, timeout=5) as resp:
            data = await resp.json()
            price = float(data.get("price", 0))
            return price
    except Exception:
        return None

# Função para buscar preços para todos pares e exchanges
async def fetch_all_prices():
    prices = {}  # {pair: {exchange: price}}
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices[pair] = {}
            tasks = [fetch_price(session, ex, pair) for ex in EXCHANGES]
            results = await asyncio.gather(*tasks)
            for ex, price in zip(EXCHANGES, results):
                if price:
                    prices[pair][ex] = price
    return prices

# Função para detectar arbitragem e enviar alerta Telegram
async def check_arbitrage_and_alert(bot):
    prices = await fetch_all_prices()
    for pair, ex_prices in prices.items():
        if len(ex_prices) < 2:
            continue  # Precisa de pelo menos 2 exchanges com preço

        # Encontrar menor e maior preço e as exchanges correspondentes
        min_ex, min_price = min(ex_prices.items(), key=lambda x: x[1])
        max_ex, max_price = max(ex_prices.items(), key=lambda x: x[1])

        # Calcular lucro percentual
        profit = ((max_price - min_price) / min_price) * 100

        if profit >= MIN_PROFIT:
            message = (
                "🚨 Oportunidade de Arbitragem Cripto!\n\n"
                f"💰 Moeda: {pair.replace('USDT','')}\n"
                f"🔽 Comprar em: {min_ex.capitalize()} a ${min_price:.2f}\n"
                f"🔼 Vender em: {max_ex.capitalize()} a ${max_price:.2f}\n"
                f"📈 Lucro estimado: {profit:.2f}%"
            )
            await bot.send_message(chat_id=os.getenv("CHAT_ID"), text=message)

async def main():
    bot_token = os.getenv("TOKEN")
    if not bot_token or not os.getenv("CHAT_ID"):
        print("⚠️ Variáveis TOKEN ou CHAT_ID não configuradas no ambiente!")
        return

    bot = Bot(token=bot_token)

    while True:
        try:
            await check_arbitrage_and_alert(bot)
        except Exception as e:
            print("Erro na verificação:", e)
        await asyncio.sleep(60)  # Espera 60 segundos entre verificações

if __name__ == "__main__":
    asyncio.run(main())
