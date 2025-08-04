import os
import asyncio
import aiohttp
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIGURAÇÕES DO BOT TELEGRAM ---
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = int(os.getenv('CHAT_ID')) # Garante que o CHAT_ID seja um inteiro

# --- VARIÁVEIS DE CONTROLE DO BOT ---
is_running = False
arbitrage_task = None
LUCRO_MINIMO = 1.0  # em % (valor padrão)

# --- LISTA DE EXCHANGES (TOP 20) ---
EXCHANGES = [
    'binance', 'coinbase', 'kraken', 'bybit', 'okx', 'kucoin',
    'bitfinex', 'gate', 'bitstamp', 'mexc', 'huobi', 'bitget',
    'poloniex', 'coinex', 'upbit', 'crypto.com', 'gemini', 'lbank',
    'bithumb', 'phemex'
]

# --- FUNÇÃO: Enviar mensagem para o Telegram ---
async def enviar_mensagem(mensagem: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro: As variáveis de ambiente TOKEN ou CHAT_ID não foram configuradas.")
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensagem, parse_mode=telegram.constants.ParseMode.HTML)

# --- FUNÇÃO: Buscar pares de moedas de alta liquidez ---
async def buscar_moedas_liquidas():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    moedas = [coin['symbol'].upper() for coin in data]
                    return moedas
        except Exception as e:
            print(f"Erro ao buscar moedas da API: {e}")
            return []

# --- FUNÇÃO: Buscar preços de uma moeda em várias exchanges ---
async def buscar_preco_par(session, par):
    resultados = {}
    for ex in EXCHANGES:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={par.lower()}&vs_currencies=usd&exchange_ids={ex}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if par.lower() in data and 'usd' in data[par.lower()]:
                        resultados[ex] = data[par.lower()]['usd']
        except Exception as e:
            print(f"Erro ao buscar preço em {ex}: {e}")
            continue
    return resultados

# --- FUNÇÃO: Verificar arbitragem em um par ---
def encontrar_arbitragem(precos):
    global LUCRO_MINIMO
    if not precos:
        return None
    try:
        menor = min(precos.items(), key=lambda x: x[1])
        maior = max(precos.items(), key=lambda x: x[1])
    except ValueError:
        return None
    preco_compra = menor[1]
    preco_venda = maior[1]
    if preco_compra == 0:
        return None
    lucro_percentual = ((preco_venda - preco_compra) / preco_compra) * 100
    if lucro_percentual >= LUCRO_MINIMO:
        return {
            'compra': menor,
            'venda': maior,
            'lucro': round(lucro_percentual, 2)
        }
    return None

# --- LOOP PRINCIPAL DE ARBITRAGEM ---
async def arbitrage_loop():
    global is_running
    await enviar_mensagem("🟢 **Bot de Arbitragem iniciado.**")
    
    moedas = await buscar_moedas_liquidas()
    if not moedas:
        await enviar_mensagem("❗️ Não foi possível buscar a lista de moedas. O loop será encerrado.")
        is_running = False
        return

    while is_running:
        try:
            async with aiohttp.ClientSession() as session:
                for moeda in moedas:
                    if not is_running:
                        break
                    precos = await buscar_preco_par(session, moeda)
                    arbitragem = encontrar_arbitragem(precos)
                    if arbitragem:
                        msg = (
                            f"💸 **ARBITRAGEM DETECTADA**\n\n"
                            f"🪙 Par: {moeda}/USD\n"
                            f"📉 Comprar em: {arbitragem['compra'][0]} por ${arbitragem['compra'][1]:.2f}\n"
                            f"📈 Vender em: {arbitragem['venda'][0]} por ${arbitragem['venda'][1]:.2f}\n"
                            f"💰 Lucro: **{arbitragem['lucro']}%**"
                        )
                        await enviar_mensagem(msg)

            await asyncio.sleep(60) # Espera 60 segundos entre as checagens
        
        except asyncio.CancelledError:
            print("Loop de arbitragem cancelado.")
            break
        except Exception as e:
            await enviar_mensagem(f"❗️ Erro no bot durante o loop: {str(e)}")
            await asyncio.sleep(60)
            
    await enviar_mensagem("🔴 **Bot de Arbitragem parado.**")

# --- COMANDOS DO TELEGRAM ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running, arbitrage_task
    if is_running:
        await update.message.reply_text("O bot já está rodando.")
    else:
        is_running = True
        arbitrage_task = asyncio.create_task(arbitrage_loop())
        await update.message.reply_text("Iniciando bot de arbitragem...")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running, arbitrage_task
    if not is_running:
        await update.message.reply_text("O bot já está parado.")
    else:
        is_running = False
        if arbitrage_task:
            arbitrage_task.cancel()
        await update.message.reply_text("Parando bot de arbitragem...")

async def setlucro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LUCRO_MINIMO
    try:
        if not context.args or not len(context.args) == 1:
            await update.message.reply_text("Uso: /setlucro <valor>")
            return
        
        novo_lucro = float(context.args[0])
        if novo_lucro <= 0:
            await update.message.reply_text("O lucro mínimo deve ser um valor positivo.")
            return

        LUCRO_MINIMO = novo_lucro
        await update.message.reply_text(f"Lucro mínimo de arbitragem alterado para {LUCRO_MINIMO}%")

    except ValueError:
        await update.message.reply_text("Por favor, insira um valor numérico válido.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running, LUCRO_MINIMO
    status = "rodando" if is_running else "parado"
    await update.message.reply_text(f"Status do bot: **{status}**\nLucro mínimo atual: **{LUCRO_MINIMO}%**", parse_mode=telegram.constants.ParseMode.MARKDOWN)

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("Erro: TOKEN do Telegram não configurado. O bot não pode ser iniciado.")
    else:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("stop", stop_command))
        application.add_handler(CommandHandler("setlucro", setlucro_command))
        application.add_handler(CommandHandler("status", status_command))
        print("Bot pronto para receber comandos...")
        application.run_polling()
