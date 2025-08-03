import asyncio
import aiohttp
import telegram

# Configurações do bot Telegram
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'

bot = telegram.Bot(token=TOKEN)

# Exchanges e pares de moedas principais
EXCHANGES = [
    'binance', 'okx', 'bybit', 'kucoin', 'gate', 'kraken', 'bitfinex',
    'huobi', 'mexc', 'bitstamp', 'poloniex', 'cryptocom', 'coinex', 'bitget'
]

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
    'LTC/USDT', 'TRX/USDT', 'SHIB/USDT', 'LINK/USDT', 'UNI/USDT',
    'ATOM/USDT', 'ETC/USDT', 'XLM/USDT', 'NEAR/USDT', 'TON/USDT'
]

API_URL = "https://api.coingecko.com/api/v3/simple/price"

async def buscar_precos():
    params = {
        'ids': ','.join({pair.split('/')[0].lower() for pair in PAIRS}),
        'vs_currencies': 'usd',
        'include_market_cap': 'false'
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params=params) as resp:
            return await resp.json()

async def analisar_arbitragem():
    while True:
        precos = await buscar_precos()
        oportunidades = []

        for pair in PAIRS:
            coin = pair.split('/')[0].lower()
            for i in range(len(EXCHANGES)):
                for j in range(len(EXCHANGES)):
                    if i != j:
                        preco_compra = 100.0
                        preco_venda = 104.0  # simulação de lucro ≥ 4%
                        lucro = ((preco_venda - preco_compra) / preco_compra) * 100

                        if lucro >= 4:
                            oportunidades.append({
                                'coin': coin.upper(),
                                'comprar_em': EXCHANGES[i].capitalize(),
                                'vender_em': EXCHANGES[j].capitalize(),
                                'lucro': round(lucro, 2),
                                'preco_compra': preco_compra,
                                'preco_venda': preco_venda
                            })

        for o in oportunidades:
            mensagem = (
                f"🚨 Oportunidade de Arbitragem Cripto!\n\n"
                f"💰 Moeda: {o['coin']}\n"
                f"🔽 Comprar em: {o['comprar_em']} a ${o['preco_compra']}\n"
                f"🔼 Vender em: {o['vender_em']} a ${o['preco_venda']}\n"
                f"📈 Lucro estimado: {o['lucro']}%\n"
            )
            await bot.send_message(chat_id=CHAT_ID, text=mensagem)

        await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(analisar_arbitragem())
