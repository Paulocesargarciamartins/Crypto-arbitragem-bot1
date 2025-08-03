import asyncio
import aiohttp
import telegram

# Configurações Telegram - substitua com seus dados
TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

# Exchanges com APIs públicas simples (exemplos)
EXCHANGES = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
    "gateio": "https://api.gate.io/api2/1/ticker/{}",
    "okx": "https://www.okx.com/api/v5/market/ticker?instId={}",
    "bitfinex": "https://api-pub.bitfinex.com/v2/ticker/t{}",
    "bitget": "https://api.bitget.com/api/spot/v1/market/ticker?symbol={}",
    "poloniex": "https://poloniex.com/public?command=returnTicker",
    "mexc": "https://api.mexc.com/api/v3/ticker/price?symbol={}",
    "bybit": "https://api.bybit.com/v2/public/tickers?symbol={}"
}

# Pares de moedas - padrão USDT, formato conforme API
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "TRXUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "SHIBUSDT", "LINKUSDT", "OPUSDT"
]

MIN_PROFIT = 1.0  # percentual mínimo para alertar

async def fetch_price(session, exchange, pair):
    try:
        if exchange == "kraken":
            # Kraken usa pares diferentes (exemplo BTCUSDT = XBTUSDT)
            kraken_pair = pair.replace("USDT", "USD").replace("BTC", "XBT")
            url = EXCHANGES[exchange].format(kraken_pair)
            async with session.get(url) as resp:
                data = await resp.json()
                result = data.get("result")
                if not result:
                    return None
                first_key = list(result.keys())[0]
                price = float(result[first_key]["c"][0])
                return price

        elif exchange == "poloniex":
            async with session.get(EXCHANGES[exchange]) as resp:
                data = await resp.json()
                price = data.get(pair)
                if price:
                    return float(price["last"])
                return None

        elif exchange == "bitfinex":
            # Bitfinex formato tBTCUSD
            symbol = "t" + pair.replace("USDT", "USD")
            url = EXCHANGES[exchange].format(symbol)
            async with session.get(url) as resp:
                data = await resp.json()
                if isinstance(data, list) and len(data) > 6:
                    return float(data[6])
                return None

        else:
            url = EXCHANGES[exchange].format(pair)
            async with session.get(url) as resp:
                data = await resp.json()
                # Formatos variados, tenta diferentes chaves:
                if "price" in data:
                    return float(data["price"])
                elif "last" in data:
                    return float(data["last"])
                elif "data" in data:
                    # KuCoin por exemplo
                    if "price" in data["data"]:
                        return float(data["data"]["price"])
                    elif "bestAsk" in data["data"]:
                        return float(data["data"]["bestAsk"])
                elif isinstance(data, list) and len(data) > 0:
                    # Bybit retorna lista em 'result'
                    if "last_price" in data[0]:
                        return float(data[0]["last_price"])
                return None
    except Exception as e:
        print(f"Erro ao buscar preço {pair} em {exchange}: {e}")
        return None

async def check_arbitrage():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                price = await fetch_price(session, exchange, pair)
                if price:
                    prices[exchange] = price
            if len(prices) < 2:
                continue
            min_ex = min(prices, key=prices.get)
            max_ex = max(prices, key=prices.get)
            min_price = prices[min_ex]
            max_price = prices[max_ex]
            profit = (max_price - min_price) / min_price * 100
            if profit >= MIN_PROFIT:
                message = (
                    f"🚨 *Oportunidade de Arbitragem!*\n"
                    f"Par: `{pair}`\n"
                    f"Comprar em: *{min_ex}* a {min_price:.4f}\n"
                    f"Vender em: *{max_ex}* a {max_price:.4f}\n"
                    f"Lucro estimado: *{profit:.2f}%*"
                )
                await send_telegram(message)

async def send_telegram(message):
    bot = telegram.Bot(token=TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Erro ao enviar mensagem Telegram: {e}")

async def main():
    print("Bot de arbitragem iniciado!")
    while True:
        await check_arbitrage()
        await asyncio.sleep(60)  # aguarda 60 segundos antes de checar de novo

if __name__ == "__main__":
    asyncio.run(main())
