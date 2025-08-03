import aiohttp
import asyncio
import telegram

TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
bot = telegram.Bot(token=TOKEN)

EXCHANGES = {
    'binance': 'https://api.binance.com/api/v3/ticker/price?symbol=XRPUSDT',
    'kucoin': 'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=XRP-USDT',
    'bitget': 'https://api.bitget.com/api/spot/v1/market/ticker?symbol=XRPUSDT_SPBL',
    'bybit': 'https://api.bybit.com/v5/market/tickers?category=spot&symbol=XRPUSDT',
    'mexc': 'https://api.mexc.com/api/v3/ticker/price?symbol=XRPUSDT',
    'gate': 'https://api.gateio.ws/api/v4/spot/tickers?currency_pair=XRP_USDT',
    'poloniex': 'https://api.poloniex.com/markets/XRP_USDT/price',
}

async def fetch_price(session, name, url):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            data = await response.json()

            if name == 'binance' or name == 'mexc':
                return name, float(data['price'])

            elif name == 'kucoin':
                return name, float(data['data']['price'])

            elif name == 'bitget':
                return name, float(data['data']['close'])

            elif name == 'bybit':
                return name, float(data['result']['list'][0]['lastPrice'])

            elif name == 'gate':
                return name, float(data[0]['last'])

            elif name == 'poloniex':
                return name, float(data['price'])

    except Exception as e:
        print(f"❌ Erro ao buscar preço em {name}: {e}")
        return name, None

async def verificar_arbitragem():
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_price(session, name, url) for name, url in EXCHANGES.items()]
            resultados = await asyncio.gather(*tasks)

            precos = {nome: preco for nome, preco in resultados if preco is not None}

            if precos:
                maior = max(precos.items(), key=lambda x: x[1])
                menor = min(precos.items(), key=lambda x: x[1])
                diferenca = maior[1] - menor[1]
                lucro_percentual = (diferenca / menor[1]) * 100

                print(f"\n🟢 Preços: {precos}")
                print(f"💰 Maior: {maior}")
                print(f"🔻 Menor: {menor}")
                print(f"📈 Diferença: {diferenca:.4f} ({lucro_percentual:.2f}%)")

                if lucro_percentual > 1:
                    msg = (
                        f"🚨 Oportunidade de arbitragem:\n"
                        f"🔻 Comprar em {menor[0]} a {menor[1]:.4f}\n"
                        f"🔺 Vender em {maior[0]} a {maior[1]:.4f}\n"
                        f"📊 Lucro estimado: {lucro_percentual:.2f}%"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
            else:
                print("Nenhum preço disponível no momento.")

        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(verificar_arbitragem())
