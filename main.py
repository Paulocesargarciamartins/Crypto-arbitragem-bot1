import os
import asyncio
import aiohttp
import telegram
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = telegram.Bot(token=TOKEN)

EXCHANGES = [
    'binance', 'bitfinex', 'kraken', 'kucoin', 'coinbase',
    'gateio', 'bitstamp', 'mexc', 'bitmart', 'okx',
    'bybit', 'bingx', 'huobi', 'whitebit'
]

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'ADA/USDT', 'BNB/USDT', 'XRP/USDT',
    'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'TRX/USDT',
    'MATIC/USDT', 'SHIB/USDT', 'ATOM/USDT', 'LTC/USDT', 'BCH/USDT',
    'FTM/USDT', 'NEAR/USDT', 'APE/USDT', 'CHZ/USDT', 'ALGO/USDT',
    'XLM/USDT', 'EGLD/USDT', 'VET/USDT', 'SAND/USDT', 'AAVE/USDT',
    'GALA/USDT', 'AXS/USDT', 'THETA/USDT', 'RUNE/USDT', 'ZIL/USDT',
    'CRV/USDT', '1INCH/USDT', 'COMP/USDT', 'KSM/USDT', 'ENJ/USDT',
    'XTZ/USDT', 'LRC/USDT', 'SNX/USDT', 'DYDX/USDT', 'YFI/USDT',
    'UNI/USDT', 'REN/USDT', 'ZEC/USDT', 'DASH/USDT', 'WAVES/USDT',
    'ICX/USDT', 'OMG/USDT', 'STORJ/USDT', 'SUSHI/USDT', 'QTUM/USDT',
    'ANKR/USDT', 'RSR/USDT', 'XEM/USDT', 'BAND/USDT', 'SKL/USDT',
    'LUNA/USDT', 'SRM/USDT', 'CVC/USDT', 'STMX/USDT', 'TOMO/USDT',
    'KAVA/USDT', 'AR/USDT', 'GLMR/USDT', 'ACA/USDT', 'FET/USDT',
    'INJ/USDT', 'CFX/USDT', 'OP/USDT', 'LDO/USDT', 'RNDR/USDT',
    'XNO/USDT', 'PEPE/USDT', 'BONK/USDT', 'WLD/USDT', 'TURBO/USDT',
    'SEI/USDT', 'PYTH/USDT', 'TIA/USDT', 'AEVO/USDT', 'PENDLE/USDT',
    'DOGAI/USDT', 'JASMY/USDT', 'HOOK/USDT', 'BLUR/USDT', 'ID/USDT',
    'SUI/USDT', 'ARB/USDT', 'GMX/USDT', 'CRO/USDT', 'BICO/USDT',
    'MASK/USDT', 'ZRX/USDT', 'RLC/USDT', 'CELR/USDT', 'NKN/USDT',
    'NMR/USDT', 'ILV/USDT', 'AGIX/USDT', 'HIGH/USDT', 'OCEAN/USDT'
]

async def get_price(session, exchange, pair):
    try:
        base, quote = pair.split('/')
        url = f'https://api.cryptorank.io/v0/markets/prices?pair={base}{quote}&exchange={exchange}'
        async with session.get(url) as response:
            data = await response.json()
            return data.get('price', None)
    except:
        return None

async def check_arbitrage():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = []
            for exchange in EXCHANGES:
                price = await get_price(session, exchange, pair)
                if price:
                    prices.append((exchange, price))
            if len(prices) >= 2:
                min_ex, min_price = min(prices, key=lambda x: x[1])
                max_ex, max_price = max(prices, key=lambda x: x[1])
                if min_price == 0:
                    continue
                profit_percent = ((max_price - min_price) / min_price) * 100
                if profit_percent >= 1:  # Arbitragem com lucro maior que 1%
                    msg = (
                        f"📈 Oportunidade de Arbitragem:\n\n"
                        f"Par: {pair}\n"
                        f"Comprar em: {min_ex.upper()} a {min_price:.2f}\n"
                        f"Vender em: {max_ex.upper()} a {max_price:.2f}\n"
                        f"Lucro estimado: {profit_percent:.2f}%"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                    await asyncio.sleep(1)

async def main():
    while True:
        await check_arbitrage()
        await asyncio.sleep(60)  # verifica a cada 60 segundos

if __name__ == "__main__":
    asyncio.run(main())
