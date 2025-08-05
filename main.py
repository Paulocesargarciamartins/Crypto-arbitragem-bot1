import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurações
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
lucro_minimo = 1.0

EXCHANGES = [
    'binance', 'kucoin', 'coinbasepro', 'kraken', 'bitfinex',
    'bittrex', 'bitstamp', 'okx', 'bybit', 'gate',
    'poloniex', 'mexc', 'bitget', 'ascendex', 'cryptocom',
    'lbank', 'huobi', 'p2pb2b', 'bibox', 'bigone'
]

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
    'SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'AVAX/USDT', 'TRX/USDT',
    'MATIC/USDT', 'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'NEAR/USDT',
    'XLM/USDT', 'FIL/USDT', 'ETC/USDT', 'EGLD/USDT', 'APE/USDT'
]

# Função para pegar preços simulados (substitua por uma API real, se quiser)
async def get_price(session, exchange, pair):
    try:
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={pair.split("/")[0].lower()}&vs_currencies=usdt'
        async with session.get(url) as resp:
            data = await resp.json()
            return data[pair.split("/")[0].lower()]['usdt']
    except Exception:
        return None

# Envia mensagem via app do Telegram (Application)
async def send_telegram_message(app, msg):
    await app.bot.send_message(chat_id=CHAT_ID, text=msg)

# Loop de arbitragem
async def verificar_arbitragem(app):
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                price = await get_price(session, exchange, pair)
                if price: prices[exchange] = price

            if len(prices) < 2:
                continue

            menor = min(prices.values())
            maior = max(prices.values())
            lucro = ((maior - menor) / menor) * 100

            if lucro >= lucro_minimo:
                menor_ex = min(prices, key=prices.get)
                maior_ex = max(prices, key=prices.get)
                msg = (
                    f"📈 Oportunidade de arbitragem!\n\n"
                    f"{pair}\n"
                    f"Comprar em: {menor_ex} (💰 {menor:.2f})\n"
                    f"Vender em: {maior_ex} (💰 {maior:.2f})\n"
                    f"Lucro: {lucro:.2f}%"
                )
                await send_telegram_message(app, msg)

# Comando /set para alterar lucro mínimo
async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global lucro_minimo
    try:
        novo_valor = float(context.args[0])
        lucro_minimo = novo_valor
        await update.message.reply_text(f"Lucro mínimo alterado para {lucro_minimo:.2f}%")
    except:
        await update.message.reply_text("Uso correto: /set 2.5")

# Inicialização
async def loop_arbitragem(app):
    while True:
        try:
            await verificar_arbitragem(app)
        except Exception as e:
            await send_telegram_message(app, f"Erro: {str(e)}")
        await asyncio.sleep(60)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("set", set_command))

    # Inicia o loop de arbitragem em paralelo
    app.job_queue.run_repeating(lambda _: asyncio.create_task(loop_arbitragem(app)), interval=60, first=1)

    # Inicia o bot (bloqueante, já controla o loop de eventos)
    app.run_polling()

if __name__ == "__main__":
    main()
