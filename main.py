import asyncio
import aiohttp
import telegram
import logging
from telegram.ext import Application, CommandHandler
from decimal import Decimal

# CONFIGURAÇÕES
TOKEN = "SEU_TOKEN_AQUI"  # Substitua pelo seu token real
CHAT_ID = "SEU_CHAT_ID_AQUI"
MIN_LUCRO = 1.5  # valor inicial
MOEDAS = ["BTC", "ETH", "XRP", "ADA", "SOL", "DOT", "DOGE", "TRX", "LTC", "AVAX", "MATIC", "LINK", "BCH", "XLM"]
EXCHANGES = ["binance", "kucoin", "mexc", "bybit", "bitfinex", "gate", "coinex", "coinbase", "bitmart", "crypto", "bitget", "okx", "huobi", "poloniex"]

# LOGGER
logging.basicConfig(level=logging.INFO)

# GLOBAL
precos = {}
lucro_minimo = Decimal(MIN_LUCRO)

# OBTÉM O PREÇO DE UMA MOEDA EM UMA EXCHANGE
async def get_price(session, exchange, moeda):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={moeda.lower()}&vs_currencies=usd&include_market_cap=false&include_24hr_vol=false&include_24hr_change=false&include_last_updated_at=false"
        async with session.get(url) as resp:
            data = await resp.json()
            price = data[moeda.lower()]['usd']
            return Decimal(price)
    except Exception as e:
        logging.error(f"[ERRO] {exchange.upper()} - {moeda.upper()}: {e}")
        return None

# VARREDURA COMPLETA
async def scan_e_enviar(bot):
    global precos
    while True:
        async with aiohttp.ClientSession() as session:
            for moeda in MOEDAS:
                precos[moeda] = []
                for exchange in EXCHANGES:
                    preco = await get_price(session, exchange, moeda)
                    if preco:
                        precos[moeda].append((exchange, preco))

                if len(precos[moeda]) < 2:
                    continue

                maior = max(precos[moeda], key=lambda x: x[1])
                menor = min(precos[moeda], key=lambda x: x[1])
                lucro = ((maior[1] - menor[1]) / menor[1]) * 100

                if lucro >= lucro_minimo:
                    mensagem = (
                        f"📊 *Arbitragem Encontrada!*\n"
                        f"🪙 Moeda: *{moeda.upper()}*\n"
                        f"🔼 Comprar em: *{menor[0]}* a *${menor[1]:.4f}*\n"
                        f"🔽 Vender em: *{maior[0]}* a *${maior[1]:.4f}*\n"
                        f"💰 Lucro estimado: *{lucro:.2f}%*"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")

        await asyncio.sleep(30)  # Aguarda 30 segundos entre ciclos

# COMANDOS TELEGRAM
async def start(update, context):
    await update.message.reply_text("🤖 Bot de arbitragem de cripto ativo!")

async def set_porcentagem(update, context):
    global lucro_minimo
    try:
        nova = Decimal(context.args[0])
        lucro_minimo = nova
        await update.message.reply_text(f"✔️ Porcentagem mínima atualizada para {lucro_minimo:.2f}%")
    except:
        await update.message.reply_text("❌ Use assim: /porcentagem 2.5")

async def listar_pares(update, context):
    await update.message.reply_text(f"🪙 Pares monitorados:\n{', '.join(MOEDAS)}")

# MAIN
async def main():
    bot = telegram.Bot(token=TOKEN)
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("porcentagem", set_porcentagem))
    app.add_handler(CommandHandler("pares", listar_pares))

    # Inicia o scanner paralelo
    asyncio.create_task(scan_e_enviar(bot))

    await app.initialize()
    await app.start()
    logging.info("✅ Bot iniciado.")
    await app.updater.start_polling()
    await app.updater.idle()

# EXECUTA
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
