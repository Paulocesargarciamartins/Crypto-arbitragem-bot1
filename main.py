import asyncio
import aiohttp
from telegram import Bot
from telegram.error import TelegramError

# Configurações do bot (já configuradas via VARS de ambiente no Heroku)
import os
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_TOKEN)

# Lista das 14 exchanges confiáveis
EXCHANGES = [
    'binance', 'kucoin', 'bitget', 'bybit', 'mexc', 'gate', 'poloniex',
    'bitfinex', 'huobi', 'okx', 'kraken', 'coinbase', 'bitstamp', 'gemini'
]

# 20 pares de moedas mais líquidos para analisar (exemplo comum)
PAIRS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT', 
    'DOTUSDT', 'MATICUSDT', 'LTCUSDT', 'BCHUSDT', 'SHIBUSDT', 'AVAXUSDT', 'UNIUSDT', 
    'ATOMUSDT', 'LINKUSDT', 'ALGOUSDT', 'FTMUSDT', 'VETUSDT', 'FILUSDT'
]

LUCRO_MINIMO = 0.05  # 5% lucro mínimo para alertar

API_URLS = {
    # Exemplo de API pública para cada exchange, se houver
    # Aqui vou usar um padrão fictício só pra ilustrar
    'binance': 'https://api.binance.com/api/v3/ticker/price?symbol={symbol}',
    'kucoin': 'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}',
    'bitget': 'https://api.bitget.com/api/spot/v1/market/ticker?symbol={symbol}',
    'bybit': 'https://api.bybit.com/spot/quote/v1/ticker/price?symbol={symbol}',
    'mexc': 'https://www.mexc.com/open/api/v2/market/ticker?symbol={symbol}',
    'gate': 'https://api.gate.io/api2/1/tickers/{symbol}',
    'poloniex': 'https://poloniex.com/public?command=returnTicker',
    'bitfinex': 'https://api-pub.bitfinex.com/v2/tickers?symbols=t{symbol}',
    'huobi': 'https://api.huobi.pro/market/detail/merged?symbol={symbol}',
    'okx': 'https://www.okx.com/api/v5/market/ticker?instId={symbol}',
    'kraken': 'https://api.kraken.com/0/public/Ticker?pair={symbol}',
    'coinbase': 'https://api.coinbase.com/v2/prices/{symbol}/spot',
    'bitstamp': 'https://www.bitstamp.net/api/v2/ticker/{symbol}/',
    'gemini': 'https://api.gemini.com/v1/pubticker/{symbol}'
}

# Função para padronizar símbolos para cada exchange (simplificada)
def normalize_symbol(exchange, pair):
    # Em geral, troca "USDT" por "USDT" ou "USD" dependendo da exchange
    # Aqui só um exemplo básico para manter igual
    return pair

async def fetch_price(session, exchange, symbol):
    url = API_URLS.get(exchange)
    if not url:
        return None
    try:
        if exchange == 'poloniex':
            # Poloniex retorna todos, tratar separado
            async with session.get(url) as resp:
                data = await resp.json()
                ticker = data.get(symbol.lower())
                if ticker:
                    return float(ticker['last'])
                return None
        else:
            api_url = url.format(symbol=symbol)
            async with session.get(api_url) as resp:
                data = await resp.json()
                # Parse padrão para diferentes exchanges:
                if exchange == 'binance':
                    return float(data['price'])
                elif exchange == 'kucoin':
                    return float(data['data']['price'])
                elif exchange == 'bitget':
                    return float(data['data']['last'])
                elif exchange == 'bybit':
                    return float(data['result'][0]['lastPrice'])
                elif exchange == 'mexc':
                    return float(data['data'][0]['lastPrice'])
                elif exchange == 'gate':
                    return float(data['last'])
                elif exchange == 'bitfinex':
                    return float(data[0][7])
                elif exchange == 'huobi':
                    return float(data['tick']['close'])
                elif exchange == 'okx':
                    return float(data['data'][0]['last'])
                elif exchange == 'kraken':
                    # Kraken tem par diferente, pode precisar ajustar
                    pair_key = list(data['result'].keys())[0]
                    return float(data['result'][pair_key]['c'][0])
                elif exchange == 'coinbase':
                    return float(data['data']['amount'])
                elif exchange == 'bitstamp':
                    return float(data['last'])
                elif exchange == 'gemini':
                    return float(data['last'])
                else:
                    return None
    except Exception:
        return None

async def check_arbitrage():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                symbol = normalize_symbol(exchange, pair)
                price = await fetch_price(session, exchange, symbol)
                if price:
                    prices[exchange] = price
            if len(prices) < 2:
                continue
            max_exchange = max(prices, key=prices.get)
            min_exchange = min(prices, key=prices.get)
            max_price = prices[max_exchange]
            min_price = prices[min_exchange]
            diff = max_price - min_price
            lucro = diff / min_price
            if lucro >= LUCRO_MINIMO:
                message = (
                    f"🚨 Oportunidade de Arbitragem Cripto!\n\n"
                    f"💰 Moeda: {pair}\n"
                    f"🔽 Comprar em: {min_exchange.capitalize()} a ${min_price:.2f}\n"
                    f"🔼 Vender em: {max_exchange.capitalize()} a ${max_price:.2f}\n"
                    f"📈 Lucro estimado: {lucro*100:.2f}%"
                )
                try:
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                except TelegramError as e:
                    print("Erro ao enviar mensagem:", e)

async def main():
    while True:
        await check_arbitrage()
        await asyncio.sleep(30)  # intervalo de 30 segundos

if __name__ == '__main__':
    asyncio.run(main())
