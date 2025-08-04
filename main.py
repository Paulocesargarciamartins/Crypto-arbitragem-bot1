import asyncio
import aiohttp
import telegram

TOKEN = '7218062934:AAFokGnqbOozHMLEB63IsTjxA8uZhfBoZj8'
CHAT_ID = '1093248456'
MARGEM_LUCRO = 1.0  # margem mínima de lucro %

bot = telegram.Bot(token=TOKEN)

EXCHANGES = {
    "binance": "https://api.binance.com/api/v3/ticker/price",
    "kucoin": "https://api.kucoin.com/api/v1/market/allTickers",
    "bitfinex": "https://api-pub.bitfinex.com/v2/tickers?symbols=ALL",
    "huobi": "https://api.huobi.pro/market/tickers",
    "bitmart": "https://api-cloud.bitmart.com/spot/v1/ticker",
    "mexc": "https://api.mexc.com/api/v3/ticker/price",
    "okx": "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
}

pares_interesse = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT", "LTCUSDT"
]

async def buscar_precos():
    precos = {}
    async with aiohttp.ClientSession() as session:
        for nome, url in EXCHANGES.items():
            try:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    precos[nome] = data
            except Exception as e:
                print(f"[Erro] {nome}: {e}")
    return precos

def calcular_lucro(maior, menor):
    try:
        return round(((maior - menor) / menor) * 100, 2)
    except:
        return 0

def extrair_preco(exchange, data, symbol):
    try:
        symbol = symbol.upper()
        if exchange == "binance":
            for item in data:
                if item['symbol'] == symbol:
                    return float(item['price'])
        elif exchange == "kucoin":
            for item in data['data']['ticker']:
                if item['symbolName'].replace("-", "") == symbol:
                    return float(item['last'])
        elif exchange == "bitfinex":
            for item in data:
                if item[0].upper() == f"T{symbol}":
                    return float(item[7])
        elif exchange == "huobi":
            for item in data['data']:
                if item['symbol'].upper() == symbol:
                    return float(item['close'])
        elif exchange == "bitmart":
            for item in data['data']['tickers']:
                if item['symbol'].upper() == symbol:
                    return float(item['last_price'])
        elif exchange == "mexc":
            for item in data:
                if item['symbol'].upper() == symbol:
                    return float(item['price'])
        elif exchange == "okx":
            for item in data['data']:
                if item['instId'].replace("-", "").upper() == symbol:
                    return float(item['last'])
    except:
        return None
    return None

async def processar_arbitragem():
    global MARGEM_LUCRO

    while True:
        precos = await buscar_precos()
        for par in pares_interesse:
            melhores = {}
            for nome, dados in precos.items():
                preco = extrair_preco(nome, dados, par)
                if preco:
                    melhores[nome] = preco
            if len(melhores) >= 2:
                maior = max(melhores.items(), key=lambda x: x[1])
                menor = min(melhores.items(), key=lambda x: x[1])
                lucro = calcular_lucro(maior[1], menor[1])
                if lucro >= MARGEM_LUCRO:
                    mensagem = (
                        f"💰 Oportunidade de arbitragem!\n\n"
                        f"🪙 Par: {par}\n"
                        f"🔻 Comprar: {menor[0]} a {menor[1]:.6f}\n"
                        f"🔺 Vender: {maior[0]} a {maior[1]:.6f}\n"
                        f"📈 Lucro estimado: {lucro:.2f}%"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem)

        await asyncio.sleep(60)

async def main():
    await processar_arbitragem()

if __name__ == "__main__":
    asyncio.run(main())
