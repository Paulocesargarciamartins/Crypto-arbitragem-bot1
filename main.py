import requests
import time

def get_binance_price(symbol="BTCUSDT"):
    try:
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
        response = requests.get(url).json()
        return float(response["bidPrice"]), float(response["askPrice"])
    except Exception as e:
        print("Erro Binance:", e)
        return None, None

def get_kucoin_price(symbol="BTC-USDT"):
    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}"
        response = requests.get(url).json()
        data = response["data"]
        return float(data["bestBid"]), float(data["bestAsk"])
    except Exception as e:
        print("Erro KuCoin:", e)
        return None, None

def check_arbitrage():
    while True:
        b_bid, b_ask = get_binance_price()
        k_bid, k_ask = get_kucoin_price()

        if None in [b_bid, b_ask, k_bid, k_ask]:
            print("Erro ao buscar dados.")
            time.sleep(5)
            continue

        if k_bid - b_ask > 0:
            lucro = (k_bid - b_ask) / b_ask * 100
            if lucro > 1:
                print(f"💰 Arbitragem: Comprar na Binance a {b_ask}, vender na KuCoin a {k_bid} | Lucro: {lucro:.2f}%")

        if b_bid - k_ask > 0:
            lucro = (b_bid - k_ask) / k_ask * 100
            if lucro > 1:
                print(f"💰 Arbitragem: Comprar na KuCoin a {k_ask}, vender na Binance a {b_bid} | Lucro: {lucro:.2f}%")

        time.sleep(10)

if __name__ == "__main__":
    check_arbitrage()
