import asyncio
import aiohttp
import telegram
import logging
from datetime import datetime

# Configurações do bot Telegram
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# Parâmetros do bot
MOEDA_REFERENCIA = "USDC"
VALOR_INVESTIMENTO = 15
LIMITE_LUCRO_PERCENTUAL = 1.0  # % de diferença para alertar

# Exchanges a serem consultadas
EXCHANGES = [
    "binance", "coinbase", "kraken", "kucoin", "bitfinex", "gate", "bitstamp",
    "mexc", "bitmart", "bitget", "okx", "bybit", "poloniex", "lbank",
    "crypto_com", "hitbtc", "probit", "bittrex", "digifinex", "p2b"
]

# Número de moedas mais negociadas (ou principais) para verificar
TOP_N_COINS = 150

# Configuração de log para debug
logging.basicConfig(level=logging.DEBUG)

# Inicializa o bot Telegram
bot = telegram.Bot(token=TELEGRAM_TOKEN)

async def buscar_top_moedas():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": MOEDA_REFERENCIA.lower(),
        "order": "volume_desc",
        "per_page": TOP_N_COINS,
        "page": 1
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return [coin["id"] for coin in data]

async def buscar_preco(session, moeda, exchange):
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": moeda,
        "vs_currencies": MOEDA_REFERENCIA.lower(),
        "include_market_cap": False,
        "include_24hr_vol": False,
        "include_24hr_change": False,
        "include_last_updated_at": False,
        "exchange_ids": exchange
    }
    async with session.get(url, params=params) as resp:
        try:
            data = await resp.json()
            return data.get(moeda, {}).get(MOEDA_REFERENCIA.lower())
        except Exception as e:
            logging.debug(f"Erro ao buscar preço de {moeda} na {exchange}: {e}")
            return None

async def verificar_arbitragem():
    moedas = await buscar_top_moedas()
    logging.debug(f"Top {TOP_N_COINS} moedas: {moedas[:10]}...")

    async with aiohttp.ClientSession() as session:
        for moeda in moedas:
            tasks = [buscar_preco(session, moeda, ex) for ex in EXCHANGES]
            precos = await asyncio.gather(*tasks)

            pares = list(zip(EXCHANGES, precos))
            pares = [(ex, preco) for ex, preco in pares if preco]

            if len(pares) < 2:
                continue

            menor = min(pares, key=lambda x: x[1])
            maior = max(pares, key=lambda x: x[1])

            diff_percent = ((maior[1] - menor[1]) / menor[1]) * 100

            if diff_percent >= LIMITE_LUCRO_PERCENTUAL:
                lucro_est = (VALOR_INVESTIMENTO / menor[1]) * maior[1] - VALOR_INVESTIMENTO
                msg = (
                    f"🔁 *Arbitragem Encontrada!*\n"
                    f"🪙 Moeda: *{moeda.upper()}*\n"
                    f"📉 Comprar: *{menor[0]}* por *{menor[1]:.4f}*\n"
                    f"📈 Vender: *{maior[0]}* por *{maior[1]:.4f}*\n"
                    f"💰 Lucro estimado: *{lucro_est:.2f} {MOEDA_REFERENCIA}* ({diff_percent:.2f}%)\n"
                    f"🕒 {datetime.utcnow().strftime('%H:%M:%S')}"
                )
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")

async def main():
    while True:
        try:
            await verificar_arbitragem()
        except Exception as e:
            logging.debug(f"Erro geral: {e}")
        await asyncio.sleep(60)  # espera 1 minuto

if __name__ == "__main__":
    asyncio.run(main())
