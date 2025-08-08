import logging
import requests
import time
import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# Configuração do logger (exibe apenas avisos e erros)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações do Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
bot = Bot(token=TELEGRAM_TOKEN)

# Parâmetros
VOLUME_MINIMO_USDT = 50
LUCRO_MINIMO_PORCENTO = 1.0
SLEEP_SECONDS = 120

# Exchanges confiáveis (13 principais)
EXCHANGES = [
    "binance", "coinbase", "kraken", "kucoin", "bybit", "bitfinex", "okx", "bitstamp",
    "mexc", "gate", "crypto_com", "huobi", "bithumb"
]

# Função para buscar as 100 moedas mais relevantes (por marketcap)
def get_top_100_coins():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1
        })
        data = response.json()
        return [coin["symbol"].upper() for coin in data]
    except Exception as e:
        logger.error(f"Erro ao obter moedas: {e}")
        return []

# Função para buscar arbitragem
def buscar_arbitragem():
    moedas = get_top_100_coins()
    if not moedas:
        logger.warning("Não foi possível obter a lista de moedas.")
        return

    for moeda in moedas:
        par = f"{moeda}/USDT"

        try:
            response = requests.get("https://api.coingecko.com/api/v3/simple/price", params={
                "ids": moeda.lower(),
                "vs_currencies": "usd",
                "include_market_cap": False,
                "include_24hr_vol": False,
                "include_24hr_change": False,
                "include_last_updated_at": False,
                "include_market_data": True
            })
            if response.status_code != 200:
                logger.warning(f"Erro {response.status_code} ao buscar preço da {moeda}")
                continue

            prices = {}

            # Buscar preços da moeda nas exchanges
            tickers = requests.get(f"https://api.coingecko.com/api/v3/coins/{moeda.lower()}/tickers").json().get("tickers", [])
            for t in tickers:
                exchange = t.get("market", {}).get("name", "").lower()
                price = t.get("last", 0.0)

                if exchange in EXCHANGES and t.get("target") == "USDT":
                    prices[exchange] = price

            if len(prices) < 2:
                continue

            menor = min(prices.items(), key=lambda x: x[1])
            maior = max(prices.items(), key=lambda x: x[1])

            preco_compra = menor[1]
            preco_venda = maior[1]
            lucro_percent = ((preco_venda - preco_compra) / preco_compra) * 100

            if lucro_percent >= LUCRO_MINIMO_PORCENTO:
                mensagem = (
                    f"💰 *Arbitragem para {par}*\n"
                    f"Compre em *{menor[0]}*: `{preco_compra:.8f}`\n"
                    f"Venda em *{maior[0]}*: `{preco_venda:.8f}`\n"
                    f"Lucro: *{lucro_percent:.2f}%*"
                )
                logger.warning(f"Oportunidade detectada: {mensagem}")
                bot.send_message(chat_id=ADMIN_CHAT_ID, text=mensagem, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Erro ao verificar {par}: {e}")

# Loop principal
if __name__ == "__main__":
    logger.warning("Bot de arbitragem iniciado...")
    while True:
        buscar_arbitragem()
        time.sleep(SLEEP_SECONDS)
