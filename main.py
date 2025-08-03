import asyncio
import aiohttp
import telegram

TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
PROFIT_THRESHOLD = 0.05  # 5% de lucro mínimo

EXCHANGES = [
    'binance', 'kraken', 'coinbase', 'kucoin', 'bitstamp',
    'bitfinex', 'mexc', 'gate', 'huobi', 'okx',
    'bitget', 'bybit', 'bitmart', 'poloniex'
]

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'SOL/USDT', 'DOGE/USDT', 'AVAX/USDT',
    'TRX/USDT', 'LINK/USDT', 'DOT/USDT', 'MATIC/USDT',
    'SHIB/USDT', 'LTC/USDT', 'BCH/USDT', 'XLM/USDT',
    'UNI/USDT', 'ATOM/USDT', 'ETC/USDT', 'TON/USDT'
]

bot = telegram.Bot(token=TOKEN)

async def fetch_ticker(session, exchange, symbol):
    url = f'https://api.ccxt.pro/{exchange}/ticker?symbol={symbol}'
    try:
        async with session.get(url, timeout=10) as response:
            return await response.json()
    except Exception:
        return None

async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            preços = []
            for ex in EXCHANGES:
                symbol = pair.replace("/", "")
                url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
                try:
                    async with session.get(url) as resp:
                        data = await resp.json()
                        preço = float(data['price'])
                        preços.append((ex, preço))
                except:
                    continue

            if len(preços) < 2:
                continue

            menor = min(preços, key=lambda x: x[1])
            maior = max(preços, key=lambda x: x[1])
            lucro = (maior[1] - menor[1]) / menor[1]

            if lucro >= PROFIT_THRESHOLD:
                mensagem = (
                    f'💰 *Arbitragem encontrada!*\n\n'
                    f'Par: `{pair}`\n\n'
                    f'🔻 Comprar em: `{menor[0]}` a *{menor[1]:.2f}*\n'
                    f'🔺 Vender em: `{maior[0]}` a *{maior[1]:.2f}*\n\n'
                    f'📈 Lucro estimado: *{lucro * 100:.2f}%*'
                )
                await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode='Markdown')

async def main():
    while True:
        await verificar_arbitragem()
        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(main())
