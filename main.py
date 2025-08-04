import asyncio
import aiohttp
import telegram
from telegram.ext import Application, CommandHandler
import os

TOKEN = "7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ"
CHAT_ID = "1093248456"
porcentagem_minima = 1.5  # Configuração inicial de lucro mínimo

exchanges = ["binance", "kraken", "coinbase", "bitfinex", "kucoin", "bittrex", "bitstamp", "gateio", "okx", "bybit", "crypto.com", "mexc", "hitbtc", "poloniex"]
pares = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "TRX/USDT"] * 10  # Total: 100 pares

monitorando = True

async def buscar_precos():
    url_base = "https://api.coingecko.com/api/v3/simple/price"
    precos = {}

    async with aiohttp.ClientSession() as session:
        for exchange in exchanges:
            for par in pares:
                moeda, stable = par.split('/')
                params = {"ids": moeda.lower(), "vs_currencies": stable.lower()}
                try:
                    async with session.get(url_base, params=params) as resp:
                        data = await resp.json()
                        preco = data.get(moeda.lower(), {}).get(stable.lower())
                        if preco:
                            precos.setdefault(par, {})[exchange] = preco
                except Exception:
                    continue
    return precos

async def encontrar_arbitragem(application):
    global monitorando
    while monitorando:
        precos = await buscar_precos()
        for par, dados in precos.items():
            if len(dados) < 2:
                continue
            menor = min(dados.values())
            maior = max(dados.values())
            lucro = ((maior - menor) / menor) * 100
            if lucro >= porcentagem_minima:
                msg = f"💸 Oportunidade: *{par}*\nLucro: *{lucro:.2f}%*\nCompra: *{menor:.2f}*\nVenda: *{maior:.2f}*"
                await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=telegram.constants.ParseMode.MARKDOWN)
        await asyncio.sleep(30)

# Comandos Telegram
async def start(update, context):
    await update.message.reply_text("🤖 Bot de Arbitragem Ativo!\nUse /porcentagem para definir lucro mínimo.")

async def ajuda(update, context):
    await update.message.reply_text(
        "📘 *Comandos disponíveis:*\n"
        "/start - Iniciar bot\n"
        "/porcentagem X - Definir lucro mínimo (ex: /porcentagem 2.5)\n"
        "/status - Ver lucro mínimo atual\n"
        "/stop - Parar monitoramento temporariamente",
        parse_mode=telegram.constants.ParseMode.MARKDOWN
    )

async def set_porcentagem(update, context):
    global porcentagem_minima
    try:
        nova = float(context.args[0])
        porcentagem_minima = nova
        await update.message.reply_text(f"✅ Lucro mínimo atualizado para {nova:.2f}%")
    except:
        await update.message.reply_text("❌ Use corretamente: /porcentagem 2.5")

async def status(update, context):
    await update.message.reply_text(f"📊 Lucro mínimo atual: {porcentagem_minima:.2f}%")

async def stop(update, context):
    global monitorando
    monitorando = False
    await update.message.reply_text("⏹️ Monitoramento pausado.")

# Inicialização do bot
async def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("porcentagem", set_porcentagem))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stop", stop))

    # Inicia monitoramento e bot
    asyncio.create_task(encontrar_arbitragem(application))
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
