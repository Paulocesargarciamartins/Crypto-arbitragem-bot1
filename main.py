import os
import asyncio
import aiohttp
import logging
import telegram
from datetime import datetime

# ========================
# CONFIGURAÇÕES PRINCIPAIS
# ========================
TOKEN = os.getenv("TELEGRAM_TOKEN") or "SEU_TOKEN_AQUI"
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "SEU_CHAT_ID"
LUCRO_MINIMO = 0.05  # 5%
MOEDA = "USDT"

EXCHANGES = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={par}",
    "coinbase": "https://api.coinbase.com/v2/prices/{par}/spot",
    "bitfinex": "https://api-pub.bitfinex.com/v2/ticker/t{par}",
}

# ========================
# FUNÇÃO DE ALERTA TELEGRAM
# ========================
async def enviar_telegram(mensagem: str):
    try:
        bot = telegram.Bot(token=TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem no Telegram: {e}")

# ========================
# FUNÇÃO DE CONSULTA EM CADA EXCHANGE
# ========================
async def buscar_preco(session, nome, par):
    try:
        if nome == "binance":
            url = EXCHANGES[nome].format(par=par.replace("/", "")).upper()
            async with session.get(url) as r:
                json = await r.json()
                return float(json["price"])
        elif nome == "coinbase":
            url = EXCHANGES[nome].format(par=par)
            async with session.get(url) as r:
                json = await r.json()
                return float(json["data"]["amount"])
        elif nome == "bitfinex":
            url = EXCHANGES[nome].format(par=par.replace("/", "")).upper()
            async with session.get(url) as r:
                json = await r.json()
                return float(json[6])
    except Exception as e:
        await enviar_telegram(f"⚠️ Erro ao consultar {nome}: {e}")
        return None

# ========================
# FUNÇÃO DE ANÁLISE DE ARBITRAGEM
# ========================
async def verificar_arbitragem():
    pares = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT"]
    async with aiohttp.ClientSession() as session:
        for par in pares:
            precos = {}
            for nome in EXCHANGES:
                preco = await buscar_preco(session, nome, par)
                if preco:
                    precos[nome] = preco

            if len(precos) < 2:
                continue

            menor_exchange = min(precos, key=precos.get)
            maior_exchange = max(precos, key=precos.get)
            menor = precos[menor_exchange]
            maior = precos[maior_exchange]
            lucro = (maior - menor) / menor

            if lucro >= LUCRO_MINIMO:
                msg = (
                    f"💸 <b>ARBITRAGEM ENCONTRADA</b>\n\n"
                    f"🪙 Moeda: <b>{par}</b>\n"
                    f"🔻 Comprar: {menor_exchange} - <b>${menor:.2f}</b>\n"
                    f"🔺 Vender: {maior_exchange} - <b>${maior:.2f}</b>\n"
                    f"📈 Lucro estimado: <b>{lucro*100:.2f}%</b>\n"
                    f"⏱ {datetime.utcnow().strftime('%H:%M:%S')} UTC"
                )
                await enviar_telegram(msg)

# ========================
# FUNÇÃO PRINCIPAL DE LOOP
# ========================
async def main():
    while True:
        try:
            await verificar_arbitragem()
        except Exception as e:
            await enviar_telegram(f"❌ Erro inesperado no bot: {e}")
        await asyncio.sleep(60)  # aguarda 60 segundos entre as verificações

# ========================
# EXECUÇÃO
# ========================
if __name__ == "__main__":
    asyncio.run(main())
