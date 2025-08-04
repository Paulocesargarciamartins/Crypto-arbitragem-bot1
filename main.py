import os
import requests
import time
import telegram

# Obtem o TOKEN do Heroku (variável de ambiente)
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "1093248456"  # Seu chat_id

# Cria o bot do Telegram
bot = telegram.Bot(token=TOKEN)

# Lista de pares de moedas a monitorar
pairs = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT",
    "BNB/USDT", "DOGE/USDT", "ADA/USDT", "SOL/USDT", "DOT/USDT",
    "AVAX/USDT", "TRX/USDT", "SHIB/USDT", "MATIC/USDT", "ATOM/USDT"
]

# Exchanges a serem comparadas
exchanges = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol=",
    "coinbase": "https://api.coinbase.com/v2/prices/{}-USDT/spot",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
}

def get_price(exchange, pair):
    base, quote = pair.split('/')
    symbol = base + quote
    try:
        if exchange == "binance":
            r = requests.get(exchanges[exchange] + symbol)
            return float(r.json()['price'])
        elif exchange == "coinbase":
            r = requests.get(exchanges[exchange].format(base))
            return float(r.json()['data']['amount'])
        elif exchange == "kucoin":
            r = requests.get(exchanges[exchange].format(symbol))
            return float(r.json()['data']['price'])
    except:
        return None

def check_arbitrage():
    for pair in pairs:
        prices = {}
        for exchange in exchanges:
            price = get_price(exchange, pair)
            if price:
                prices[exchange] = price
        if len(prices) >= 2:
            min_ex = min(prices, key=prices.get)
            max_ex = max(prices, key=prices.get)
            min_price = prices[min_ex]
            max_price = prices[max_ex]
            profit = ((max_price - min_price) / min_price) * 100
            if profit >= 1:  # lucro mínimo de 1%
                message = (
                    f"💰 Oportunidade de arbitragem!\n\n"
                    f"🪙 Par: {pair}\n"
                    f"🔻 Comprar: {min_ex} a {min_price:.2f}\n"
                    f"🔺 Vender: {max_ex} a {max_price:.2f}\n"
                    f"📈 Lucro estimado: {profit:.2f}%"
                )
                bot.send_message(chat_id=CHAT_ID, text=message)

while True:
    check_arbitrage()
    time.sleep(60)  # Checa a cada 60 segundos
