import asyncio
import aiohttp
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler
import time

# Configurações
TOKEN = 'SEU_TOKEN_AQUI'
CHAT_ID = 1093248456  # Substitua pelo seu
lucro_minimo = 0.5  # lucro mínimo em %
monitorando = True

exchanges = ['binance', 'kraken', 'coinbase', 'bitstamp']
pares = ['BTC/USDT', 'ETH/USDT']

bot = telegram.Bot(token=TOKEN)

async def enviar_alerta(msg):
    await bot.send_message(chat_id=CHAT_ID, text=msg)

async def buscar_preco(session, exchange, par):
    # Simulação de preço
    await asyncio.sleep(0.2)
    preco_simulado = 10000 + hash(f"{exchange}-{par}") % 1000
    return preco_simulado

async def verificar_arbitragem():
    global monitorando
    while monitorando:
        async with aiohttp.ClientSession() as session:
            for par in pares:
                precos = {}
                for exchange in exchanges:
                    preco = await buscar_preco(session, exchange, par)
                    precos[exchange] = preco

                menor = min(precos.values())
                maior = max(precos.values())

                lucro = ((maior - menor) / menor) * 100
                if lucro >= lucro_minimo:
                    msg = (
                        f"🔔 Oportunidade de arbitragem!\nPar: {par}\n"
                        f"💰 Comprar em: {min(precos, key=precos.get)} a {menor:.2f}\n"
                        f"💸 Vender em: {max(precos, key=precos.get)} a {maior:.2f}\n"
                        f"📊 Lucro: {lucro:.2f}%"
                    )
                    await enviar_alerta(msg)
        await asyncio.sleep(10)

# Comandos do Telegram

async def start(update, context):
    global monitorando
    monitorando = True
    await update.message.reply_text("✅ Monitoramento iniciado.")
    asyncio.create_task(verificar_arbitragem())

async def stop(update, context):
    global monitorando
    monitorando = False
    await update.message.reply_text("🛑 Monitoramento parado.")

async def set_percent(update, context):
    global lucro_minimo
    try:
        lucro_minimo = float(context.args[0])
        await update.message.reply_text(f"📈 Margem de lucro mínima ajustada para {lucro_minimo}%")
    except:
        await update.message.reply_text("⚠️ Use o comando assim: /setpercent 1.2")

async def add_pair(update, context):
    global pares
    try:
        novo = context.args[0].upper()
        if novo not in pares:
            pares.append(novo)
            await update.message.reply_text(f"✅ Par adicionado: {novo}")
        else:
            await update.message.reply_text("⚠️ Esse par já está sendo monitorado.")
    except:
        await update.message.reply_text("⚠️ Use assim: /addpair BTC/USDT")

async def add_exchange(update, context):
    global exchanges
    try:
        nova = context.args[0].lower()
        if nova not in exchanges:
            exchanges.append(nova)
            await update.message.reply_text(f"✅ Exchange adicionada: {nova}")
        else:
            await update.message.reply_text("⚠️ Essa exchange já está sendo monitorada.")
    except:
        await update.message.reply_text("⚠️ Use assim: /addexchange binance")

# Inicialização do bot
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("setpercent", set_percent))
    app.add_handler(CommandHandler("addpair", add_pair))
    app.add_handler(CommandHandler("addexchange", add_exchange))

    print("🤖 Bot rodando...")
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

asyncio.run(main())
