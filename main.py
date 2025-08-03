import os
import time
import requests
from telegram import Bot

# Pega o token e chat ID do ambiente (variáveis configuradas no Heroku)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Checa se as variáveis estão definidas
if not TOKEN or not CHAT_ID:
    print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID precisam estar configurados nas variáveis de ambiente!")
    exit(1)

bot = Bot(token=TOKEN)

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
            time.sleep(10)
            continue

        # Binance -> KuCoin
        if k_bid - b_ask > 0:
            lucro = (k_bid - b_ask) / b_ask * 100
            if lucro > 1:  # Ajuste lucro mínimo se quiser
                msg = (
                    f"💰 Arbitragem detectada!\n"
                    f"Comprar na Binance a {b_ask}\n"
                    f"Vender na KuCoin a {k_bid}\n"
                    f"Lucro estimado: {lucro:.2f}%"
                )
                print(msg)
                try:
                    bot.send_message(chat_id=CHAT_ID, text=msg)
                except Exception as e:
                    print(f"Erro ao enviar mensagem no Telegram: {e}")

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
                try:
                    bot.send_message(chat_id=CHAT_ID, text=msg)
                except Exception as e:
                    print(f"Erro ao enviar mensagem no Telegram: {e}")

        time.sleep(10)

if __name__ == "__main__":
    print("Bot iniciado!")
    check_arbitrage()
