import asyncio
import aiohttp
import os
from telegram import Bot

# Configurações do bot Telegram (pegar das variáveis de ambiente no Heroku)
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

# Exchanges listadas (14 confiáveis)
EXCHANGES = [
    "binance",
    "kucoin",
    "bitget",
    "bybit",
    "mexc",
    "gate",
    "poloniex",
    "ftx",
    "okx",
    "huobi",
    "bitfinex",
    "kraken",
    "coinbase",
    "gemini"
]

# Pares de moedas top 20 (maior liquidez)
PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "SOLUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT",
    "AVAXUSDT", "SHIBUSDT", "TRXUSDT", "UNIUSDT", "LINKUSDT",
    "ATOMUSDT", "XLMUSDT", "BCHUSDT", "VETUSDT", "FILUSDT"
]

MIN_PROFIT_PERCENT = 5.0  # filtro de lucro mínimo em %

API_ENDPOINTS = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={pair}",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair}",
    "bitget": "https://api.bitget.com/api/spot/v1/market/ticker?symbol={pair}",
    "bybit": "https://api.bybit.com/spot/quote/v1/ticker/price?symbol={pair}",
    "mexc": "https://www.mexc.com/api/v2/market/ticker?symbol={pair}",
    "gate": "https://api.gate.io/api2/1/ticker/{pair}",
    "poloniex": "https://poloniex.com/public?command=returnTicker",
    "ftx": "https://ftx.com/api/markets/{pair}",
    "okx": "https://www.okx.com/api/v5/market/ticker?instId={pair}",
    "huobi": "https://api.huobi.pro/market/detail/merged?symbol={pair}",
    "bitfinex": "https://api-pub.bitfinex.com/v2/ticker/t{pair}",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={pair}",
    "coinbase": "https://api.coinbase.com/v2/prices/{pair}/spot",
    "gemini": "https://api.gemini.com/v1/pubticker/{pair}"
}

# Função para normalizar o par para cada exchange, pois nem todas usam o mesmo padrão
def normalize_pair(exchange, pair):
    # Ajustes simples (exemplo para Binance usa USDT, Kraken usa XBT etc)
    # Pode ajustar mais conforme necessidade
    if exchange == "kraken":
        return pair.replace("USDT", "USDT").replace("BTC", "XBT")
    if exchange == "bitfinex":
        return pair.replace("USDT", "USD").upper()
    if exchange == "poloniex":
        return pair.upper()
    if exchange == "gemini":
        return pair.lower()
    if exchange == "coinbase":
        return pair[:3] + "-" + pair[3:]
    if exchange == "gate":
        return pair.lower()
    return pair.upper()

async def fetch_price(session, exchange, pair):
    url = API_ENDPOINTS[exchange].format(pair=normalize_pair(exchange, pair))
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            # Extrair o preço conforme estrutura da API de cada exchange
            # Exemplos principais, pode ter que adaptar para cada API:
            if exchange == "binance":
                return float(data['price'])
            if exchange == "kucoin":
                return float(data['data']['price'])
            if exchange == "bitget":
                return float(data['data']['last'])
            if exchange == "bybit":
                return float(data['result'][0]['price'])
            if exchange == "mexc":
                return float(data['data'][0]['last'])
            if exchange == "gate":
                return float(data['last'])
            if exchange == "poloniex":
                key = pair.upper()
                if key in data:
                    return float(data[key]['last'])
                return None
            if exchange == "ftx":
                return float(data['result']['price'])
            if exchange == "okx":
                return float(data['data'][0]['last'])
            if exchange == "huobi":
                return float(data['tick']['close'])
            if exchange == "bitfinex":
                return float(data[6])
            if exchange == "kraken":
                # Kraken retorna um objeto complexo
                key = list(data['result'].keys())[0]
                return float(data['result'][key]['c'][0])
            if exchange == "coinbase":
                return float(data['data']['amount'])
            if exchange == "gemini":
                return float(data['last'])
    except Exception:
        return None

async def check_arbitrage():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for ex in EXCHANGES:
                price = await fetch_price(session, ex, pair)
                if price:
                    prices[ex] = price
            if len(prices) < 2:
                continue  # precisa ter pelo menos 2 exchanges com preço

            # Encontrar menor preço (compra) e maior preço (venda)
            buy_exchange, buy_price = min(prices.items(), key=lambda x: x[1])
            sell_exchange, sell_price = max(prices.items(), key=lambda x: x[1])

            if sell_price <= buy_price:
                continue  # sem lucro

            profit_percent = ((sell_price - buy_price) / buy_price) * 100
            if profit_percent >= MIN_PROFIT_PERCENT:
                message = (
                    f"🚨 Oportunidade de Arbitragem Cripto!\n\n"
                    f"💰 Moeda: {pair}\n"
                    f"🔽 Comprar em: {buy_exchange.capitalize()} a ${buy_price:.4f}\n"
                    f"🔼 Vender em: {sell_exchange.capitalize()} a ${sell_price:.4f}\n"
                    f"📈 Lucro estimado: {profit_percent:.2f}%"
                )
                try:
                    await bot.send_message(chat_id=CHAT_ID, text=message)
                except Exception as e:
                    print(f"Erro ao enviar mensagem Telegram: {e}")

async def main():
    while True:
        await check_arbitrage()
        await asyncio.sleep(30)  # espera 30 segundos para nova checagem

if __name__ == "__main__":
    asyncio.run(main())
