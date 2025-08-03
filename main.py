import asyncio
import aiohttp
import telegram

TOKEN = 'SEU_TOKEN_AQUI'
CHAT_ID = 'SEU_CHAT_ID_AQUI'

pares = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
         'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT',
         'TRX/USDT', 'LINK/USDT', 'LTC/USDT', 'ATOM/USDT', 'SHIB/USDT',
         'ETC/USDT', 'OP/USDT', 'UNI/USDT', 'NEAR/USDT', 'APE/USDT']

exchanges = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    "bitget": "https://api.bitget.com/api/spot/v1/market/ticker?symbol={}",
    "bybit": "https://api.bybit.com/v2/public/tickers?symbol={}",
    "mexc": "https://api.mexc.com/api/v3/ticker/price?symbol={}",
    "gate": "https://api.gate.io/api2/1/ticker/{}",
    "poloniex": "https://poloniex.com/public?command=returnTicker",
    "okx": "https://www.okx.com/api/v5/market/ticker?instId={}",
    "coinbase": "https://api.exchange.coinbase.com/products/{}/ticker",
    "huobi": "https://api.huobi.pro/market/detail/merged?symbol={}",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
    "bitstamp": "https://www.bitstamp.net/api/v2/ticker/{}",
    "bittrex": "https://api.bittrex.com/v3/markets/{}/ticker",
    "crypto": "https://api.crypto.com/v2/public/get-ticker?instrument_name={}"
}

async def fetch_price(session, url, exchange, par):
    try:
        if exchange == "binance":
            symbol = par.replace("/", "")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['price'])

        elif exchange == "kucoin":
            symbol = par.replace("/", "-")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['data']['price'])

        elif exchange == "bitget":
            symbol = par.replace("/", "")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['data']['close'])

        elif exchange == "bybit":
            symbol = par.replace("/", "")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['result'][0]['last_price'])

        elif exchange == "mexc":
            symbol = par.replace("/", "")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['price'])

        elif exchange == "gate":
            symbol = par.replace("/", "_").lower()
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['last'])

        elif exchange == "poloniex":
            symbol = par.replace("/", "_").upper()
            r = await session.get(url)
            data = await r.json()
            return float(data[symbol]['last'])

        elif exchange == "okx":
            symbol = par.replace("/", "-").upper()
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['data'][0]['last'])

        elif exchange == "coinbase":
            symbol = par.replace("/", "-")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['price'])

        elif exchange == "huobi":
            symbol = par.replace("/", "").lower()
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['tick']['close'])

        elif exchange == "kraken":
            symbol = par.replace("/", "")
            if symbol == "BTCUSDT":
                symbol = "XBTUSDT"
            r = await session.get(url.format(symbol))
            data = await r.json()
            key = list(data['result'].keys())[0]
            return float(data['result'][key]['c'][0])

        elif exchange == "bitstamp":
            symbol = par.replace("/", "").lower()
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['last'])

        elif exchange == "bittrex":
            symbol = par.replace("/", "-")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['lastTradeRate'])

        elif exchange == "crypto":
            symbol = par.replace("/", "_")
            r = await session.get(url.format(symbol))
            data = await r.json()
            return float(data['result']['data']['a'])

    except:
        return None

async def monitorar_arbitragem():
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="🔁 Bot de arbitragem iniciado!")

    while True:
        async with aiohttp.ClientSession() as session:
            for par in pares:
                tasks = [fetch_price(session, url, exchange, par) for exchange, url in exchanges.items()]
                prices = await asyncio.gather(*tasks)
                mercado = {}

                for i, exchange in enumerate(exchanges.keys()):
                    if prices[i]:
                        mercado[exchange] = prices[i]

                if len(mercado) >= 2:
                    maior = max(mercado, key=mercado.get)
                    menor = min(mercado, key=mercado.get)
                    preco_maior = mercado[maior]
                    preco_menor = mercado[menor]
                    dif = preco_maior - preco_menor
                    perc = (dif / preco_menor) * 100

                    if perc >= 0.5:  # Ajuste conforme desejado
                        msg = (
                            f"💸 Arbitragem encontrada: {par}\n\n"
                            f"🔼 Maior preço: {maior} - ${preco_maior:.2f}\n"
                            f"🔽 Menor preço: {menor} - ${preco_menor:.2f}\n"
                            f"📊 Diferença: ${dif:.2f} ({perc:.2f}%)"
                        )
                        await bot.send_message(chat_id=CHAT_ID, text=msg)

        await asyncio.sleep(60)

asyncio.run(monitorar_arbitragem())
