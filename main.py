import asyncio
import aiohttp
import telegram
import time

# Configuração do Telegram
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
bot = telegram.Bot(token=TOKEN)

# Exchanges e pares
exchanges = [
    'binance', 'kucoin', 'coinbase', 'mexc', 'bitget', 'bitfinex', 'gate',
    'kraken', 'bybit', 'okx', 'poloniex', 'bitmart', 'bitstamp', 'lbank'
]

symbols = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT',
    'ADA/USDT', 'AVAX/USDT', 'MATIC/USDT', 'DOT/USDT', 'TRX/USDT',
    'UNI/USDT', 'LTC/USDT', 'ETC/USDT', 'FIL/USDT', 'NEAR/USDT',
    'XLM/USDT', 'HBAR/USDT', 'ICP/USDT', 'SAND/USDT', 'APT/USDT',
    'INJ/USDT', 'IMX/USDT', 'GRT/USDT', 'EGLD/USDT', 'AAVE/USDT',
    'RNDR/USDT', 'FTM/USDT', 'RPL/USDT', 'QNT/USDT', 'KLAY/USDT',
    'CRV/USDT', 'ZEC/USDT', 'ENJ/USDT', 'BAND/USDT', 'SNX/USDT',
    'YFI/USDT', 'BAT/USDT', 'ANKR/USDT', '1INCH/USDT', 'COMP/USDT',
    'SUSHI/USDT', 'STORJ/USDT', 'ZEN/USDT', 'CELR/USDT', 'CKB/USDT',
    'OMG/USDT', 'WAVES/USDT', 'BAL/USDT', 'CVC/USDT', 'GALA/USDT',
    'OP/USDT', 'AR/USDT', 'PEPE/USDT', 'JASMY/USDT', 'SHIB/USDT',
    'ALGO/USDT', 'ZIL/USDT', 'SKL/USDT', 'FLOW/USDT', 'XEC/USDT',
    'MASK/USDT', 'CHZ/USDT', 'DASH/USDT', 'PYR/USDT', 'VET/USDT',
    'CRO/USDT', 'LRC/USDT', 'GLM/USDT', 'CTSI/USDT', 'MTL/USDT',
    'NMR/USDT', 'KSM/USDT', 'RAY/USDT', 'SXP/USDT', 'KNC/USDT',
    'UMA/USDT', 'AUDIO/USDT', 'DODO/USDT', 'REQ/USDT', 'COTI/USDT',
    'TRB/USDT', 'BNT/USDT', 'C98/USDT', 'REEF/USDT', 'BADGER/USDT',
    'ORN/USDT', 'TWT/USDT', 'SPELL/USDT', 'FET/USDT', 'ILV/USDT',
    'LPT/USDT', 'GHST/USDT', 'PLA/USDT', 'TOMO/USDT', 'UOS/USDT',
    'XNO/USDT', 'VRA/USDT', 'NKN/USDT', 'MDT/USDT', 'PERP/USDT'
]

import ccxt.async_support as ccxt

async def fetch_price(exchange_id, symbol):
    try:
        exchange = getattr(ccxt, exchange_id)()
        ticker = await exchange.fetch_ticker(symbol)
        await exchange.close()
        return ticker['last']
    except:
        return None

async def check_arbitrage():
    while True:
        try:
            for symbol in symbols:
                prices = {}
                for exchange_id in exchanges:
                    price = await fetch_price(exchange_id, symbol)
                    if price:
                        prices[exchange_id] = price

                if len(prices) >= 2:
                    max_exchange = max(prices, key=prices.get)
                    min_exchange = min(prices, key=prices.get)
                    max_price = prices[max_exchange]
                    min_price = prices[min_exchange]
                    profit = (max_price - min_price) / min_price * 100

                    if profit >= 2:  # Arbitragem com lucro acima de 2%
                        msg = f"🔁 Arbitragem: {symbol}\n🔼 Comprar: {min_exchange} - ${min_price:.2f}\n🔽 Vender: {max_exchange} - ${max_price:.2f}\n📊 Lucro: {profit:.2f}%"
                        await bot.send_message(chat_id=CHAT_ID, text=msg)

            await asyncio.sleep(60)

        except Exception as e:
            print(f"Erro: {e}")
            await asyncio.sleep(60)

asyncio.run(check_arbitrage())
