import asyncio
import aiohttp
import time
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Token do seu bot Telegram e ID do chat
# Lembre-se de não expor o token publicamente em produção.
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'

# Parâmetros de arbitragem configuráveis
percentual_lucro = 1.5  # padrão inicial
moedas_monitoradas = ['BTC', 'ETH', 'LTC']
exchanges_monitoradas = ['binance', 'coinbase', 'kraken', 'bitstamp']

# Estado de monitoramento
monitorando = True

# Função para calcular arbitragem fictícia (simulação simplificada)
async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        while monitorando:
            oportunidades = []

            for moeda in moedas_monitoradas:
                for ex1 in exchanges_monitoradas:
                    for ex2 in exchanges_monitoradas:
                        if ex1 == ex2:
                            continue
                        preco_compra = 100  # Simulado
                        preco_venda = 100 + percentual_lucro  # Simulado

                        lucro = preco_venda - preco_compra
                        percentual = (lucro / preco_compra) * 100

                        if percentual >= percentual_lucro:
                            oportunidades.append(
                                f'Arbitragem detectada: {moeda} | Comprar em {ex1} a {preco_compra}, Vender em {ex2} a {preco_venda} | Lucro: {percentual:.2f}%'
                            )

            if oportunidades:
                mensagem = "\n".join(oportunidades)
                await bot.send_message(chat_id=CHAT_ID, text=mensagem)

            await asyncio.sleep(30)

# Bot Telegram (envio e comandos)
bot = telegram.Bot(token=TOKEN)

# HANDLERS COMANDOS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    monitorando = True
    await update.message.reply_text("✅ Monitoramento iniciado!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    monitorando = False
    await update.message.reply_text("🛑 Monitoramento parado!")

async def porcentagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global percentual_lucro
    try:
        nova = float(context.args[0])
        percentual_lucro = nova
        await update.message.reply_text(f"✅ Novo percentual de lucro: {nova}%")
    except:
        await update.message.reply_text("❌ Use: /porcentagem 2.5")

async def moeda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global moedas_monitoradas
    if context.args:
        moedas_monitoradas = [moeda.upper() for moeda in context.args]
        await update.message.reply_text(f"✅ Moedas atualizadas: {', '.join(moedas_monitoradas)}")
    else:
        await update.message.reply_text("❌ Use: /moeda BTC ETH LTC")

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global exchanges_monitoradas
    if context.args:
        exchanges_monitoradas = [ex.lower() for ex in context.args]
        await update.message.reply_text(f"✅ Exchanges atualizadas: {', '.join(exchanges_monitoradas)}")
    else:
        await update.message.reply_text("❌ Use: /exchange binance coinbase kraken")

# Inicialização do bot com comandos
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("porcentagem", porcentagem))
    app.add_handler(CommandHandler("moeda", moeda))
    app.add_handler(CommandHandler("exchange", exchange))

    # Inicia monitoramento de arbitragem em segundo plano
    asyncio.create_task(verificar_arbitragem())

    # Executa o bot
    await app.run_polling()

# Início
if __name__ == '__main__':
    asyncio.run(main())

