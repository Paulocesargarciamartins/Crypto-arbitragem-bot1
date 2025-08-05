import asyncio
import aiohttp
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler

# --- CONFIGURAÇÃO DO BOT ---
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
lucro_minimo = 1.0  # % mínima para alertar

# --- LISTA DE EXCHANGES CONFIÁVEIS ---
EXCHANGES = [
    'binance', 'kucoin', 'coinbasepro', 'kraken', 'bitfinex',
    'bittrex', 'bitstamp', 'okx', 'bybit', 'gate',
    'poloniex', 'mexc', 'bitget', 'ascendex', 'cryptocom',
    'lbank', 'huobi', 'p2pb2b', 'bibox', 'bigone'
]

# --- PAR DE MOEDAS USDT ---
PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
    'SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'AVAX/USDT', 'TRX/USDT',
    'MATIC/USDT', 'LTC/USDT', 'LINK/USDT', 'ATOM/USDT', 'NEAR/USDT',
    'XLM/USDT', 'FIL/USDT', 'ETC/USDT', 'EGLD/USDT', 'APE/USDT'
]

# --- FUNÇÃO PARA CONSULTAR PREÇOS ---
async def get_price(session, exchange, pair):
    try:
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={pair.split("/")[0].lower()}&vs_currencies=usdt'
        async with session.get(url) as resp:
            data = await resp.json()
            return data[pair.split("/")[0].lower()]['usdt']
    except:
        return None

# --- FUNÇÃO PARA CALCULAR ARBITRAGEM ---
async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                price = await get_price(session, exchange, pair)
                if price: prices[exchange] = price

            if len(prices) < 2: continue

            menor = min(prices.values())
            maior = max(prices.values())
            lucro = ((maior - menor) / menor) * 100

            if lucro >= lucro_minimo:
                menor_ex = min(prices, key=prices.get)
                maior_ex = max(prices, key=prices.get)
                msg = (
                    f"📈 Oportunidade de arbitragem detectada!\n\n"
                    f"Par: {pair}\n"
                    f"Comprar em: {menor_ex} (💰 {menor:.2f})\n"
                    f"Vender em: {maior_ex} (💰 {maior:.2f})\n"
                    f"Lucro estimado: {lucro:.2f}%"
                )
                await send_telegram_message(msg)

# --- ENVIAR MENSAGEM PARA O TELEGRAM ---
async def send_telegram_message(msg):
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg)

# --- COMANDO /set PARA AJUSTAR % PELO TELEGRAM ---
async def set_command(update, context):
    global lucro_minimo
    try:
        novo_valor = float(context.args[0])
        lucro_minimo = novo_valor
        await update.message.reply_text(f"Novo valor de lucro mínimo definido para {lucro_minimo:.2f}%")
    except:
        await update.message.reply_text("Uso correto: /set 2.5")

# --- MAIN LOOP COM VERIFICAÇÃO CONTÍNUA ---
async def main_loop():
    while True:
        try:
            await verificar_arbitragem()
        except Exception as e:
            await send_telegram_message(f"Erro no bot: {str(e)}")
        await asyncio.sleep(60)

# --- INICIALIZAÇÃO DO BOT ---
def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("set", set_command))
    app.run_polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main_loop())
    start_bot()
