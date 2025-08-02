import requests
import time
import telegram

# Configuração do bot Telegram
TOKEN = "7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ"  # ⚠️ Nunca compartilhe esse token publicamente!
CHAT_ID = "1093248456"

bot = telegram.Bot(token=TOKEN)

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

        # Binance -> KuCoin
        if k_bid - b_ask > 0:
            lucro = (k_bid - b_ask) / b_ask * 100
            if lucro > 1:
                msg = (
                    f"💰 Arbitragem detectada!\n"
                    f"Comprar na Binance a {b_ask}\n"
                    f"Vender na KuCoin a {k_bid}\n"
                    f"Lucro estimado: {lucro:.2f}%"
                )
                print(msg)
                bot.send_message(chat_id=CHAT_ID, text=msg)

        # KuCoin -> Binance
        if b_bid - k_ask > 0:
            lucro = (b_bid - k_ask) / k_ask * 100
            if lucro > 1:
                msg = (
                    f"💰 Arbitragem detectada!\n"
                    f"Comprar na KuCoin a {k_ask}\n"
                    f"Vender na Binance a {b_bid}\n"
                    f"Lucro estimado: {lucro:.2f}%"
                )
                print(msg)
                bot.send_message(chat_id=CHAT_ID, text=msg)

        time.sleep(10)

if __name__ == "__main__":
    check_arbitrage()
