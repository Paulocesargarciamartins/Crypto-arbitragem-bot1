import asyncio
import aiohttp
import telegram

# Configurações do Telegram
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# Exchanges e endpoints
EXCHANGES = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "bybit": "https://api.bybit.com/v2/public/tickers?symbol={}",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    "gate": "https://api.gate.io/api2/1/ticker/{}",
    "okx": "https://www.okx.com/api/v5/market/ticker?instId={}",
    "bitget": "https://api.bitget.com/api/spot/v1/market/ticker?symbol={}",
    "bitfinex": "https://api-pub.bitfinex.com/v2/ticker/t{}",
    "poloniex": "https://poloniex.com/public?command=returnTicker",
    "mexc": "https://api.mexc.com/api/v3/ticker/price?symbol={}",
}

# Pares de moedas com alta liquidez
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "TRXUSDT",
    "MATICUSDT", "LTCUSDT", "SHIBUSDT", "LINKUSDT", "OPUSDT"
]

# Função para pegar preço em cada exchange
async def fetch_price(session, exchange, url, pair):
    try:
        if exchange == "kraken":
            pair_map = {"BTCUSDT": "XBTUSDT", "ETHUSDT": "ETHUSDT"}
            kraken_pair = pair_map.get(pair, pair)
            async with session.get(url.format(kraken_pair)) as r:
                data = await r.json()
                price = list(data["result"].values())[0]["c"][0]
        elif exchange == "gate":
            async with session.get(url.format(pair.lower())) as r:
                data = await r.json()
                price = data["last"]
        elif exchange == "okx":
            async with session.get(url.format(pair)) as r:
                data = await r.json()
                price = data["data"][0]["last"]
        elif exchange == "bitfinex":
            async with session.get(url.format(pair)) as r:
                data = await r.json()
                price = data[6]
        elif exchange == "poloniex":
            async with session.get(url) as r:
                data = await r.json()
                price = data[pair]["last"]
        else:
            async with session.get(url.format(pair)) as r:
                data = await r.json()
                price = data["price"]
        return float(price)
    except Exception:
        return None

# Função para comparar preços entre exchanges
async def buscar_arbitragem():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for ex, url in EXCHANGES.items():
                price = await fetch_price(session, ex, url, pair)
                if price:
                    prices[ex] = price
            if len(prices) < 2:
                continue
            min_ex = min(prices, key=prices.get)
            max_ex = max(prices, key=prices.get)
            min_price = prices[min_ex]
            max_price = prices[max_ex]
            lucro = ((max_price - min_price) / min_price) * 100
            if lucro >= 5:
                msg = f"💰 Oportunidade de Arbitragem\nPar: {pair}\nComprar: {min_ex} por {min_price:.2f}\nVender: {max_ex} por {max_price:.2f}\nLucro: {lucro:.2f}%"
                await enviar_telegram(msg)

# Enviar mensagem para Telegram
async def enviar_telegram(msg):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

# Loop contínuo
async def main():
    print("Bot de arbitragem iniciado!")
    while True:
        try:
            await buscar_arbitragem()
        except Exception as e:
            print("Erro:", e)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
