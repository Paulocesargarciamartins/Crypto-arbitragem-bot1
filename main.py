import asyncio
import logging
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# Configurações iniciais
TOKEN = "7218062934:AAFokGnqbOozHMLEB63IsTjxA8uZhfBoZj8"
CHAT_ID = 1093248456
LUCRO_MINIMO = 0.5  # Percentual de lucro mínimo para alertar (em %)
MOEDAS_MONITORADAS = [
    # Lista simplificada das 150 moedas em par USDC (exemplo)
    "BTC", "ETH", "XRP", "USDT", "BNB", "SOL", "USDC", "TRX", "DOGE", "ADA",
    # ... (adicione as 150 moedas que você listou)
]
EXCHANGES = [
    "binance", "coinbase", "kraken", "kucoin", "gateio", "bitstamp", "mexc",
    "bitmart", "okx", "bybit", "bingx", "huobi", "whitebit", "bitfinex",
    "poloniex", "bitflyer", "gemini", "hitbtc", "bittrex", "coinex"
]

# Configura o logger com DEBUG
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Variáveis de controle
monitorando = False
lucro_minimo_atual = LUCRO_MINIMO

# Funções do bot Telegram

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    if monitorando:
        await update.message.reply_text("Já estou monitorando as oportunidades!")
    else:
        monitorando = True
        await update.message.reply_text("Iniciando monitoramento de oportunidades...")
        asyncio.create_task(monitorar_oportunidades(context.application))
        
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    if monitorando:
        monitorando = False
        await update.message.reply_text("Monitoramento pausado.")
    else:
        await update.message.reply_text("O monitoramento já está parado.")
        
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        f"Monitorando: {'Sim' if monitorando else 'Não'}\n"
        f"Lucro mínimo configurado: {lucro_minimo_atual}%\n"
        f"Quantidade de moedas monitoradas: {len(MOEDAS_MONITORADAS)}\n"
        f"Exchanges monitoradas: {', '.join(EXCHANGES)}"
    )
    await update.message.reply_text(status_msg)

async def set_lucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global lucro_minimo_atual
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /setlucro <percentual>\nExemplo: /setlucro 1.0")
        return
    try:
        novo_lucro = float(context.args[0])
        if novo_lucro <= 0:
            await update.message.reply_text("Informe um percentual maior que zero.")
            return
        lucro_minimo_atual = novo_lucro
        await update.message.reply_text(f"Lucro mínimo alterado para {lucro_minimo_atual}%.")
    except ValueError:
        await update.message.reply_text("Por favor, informe um número válido.")

async def add_moeda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /addmoeda <símbolo>\nExemplo: /addmoeda DOGE")
        return
    moeda = context.args[0].upper()
    if moeda in MOEDAS_MONITORADAS:
        await update.message.reply_text(f"A moeda {moeda} já está na lista.")
    else:
        MOEDAS_MONITORADAS.append(moeda)
        await update.message.reply_text(f"Moeda {moeda} adicionada à lista.")

async def add_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /addexchange <nome>\nExemplo: /addexchange binance")
        return
    exchange = context.args[0].lower()
    if exchange in EXCHANGES:
        await update.message.reply_text(f"A exchange {exchange} já está na lista.")
    else:
        EXCHANGES.append(exchange)
        await update.message.reply_text(f"Exchange {exchange} adicionada à lista.")

# Função principal de monitoramento

async def monitorar_oportunidades(app):
    global monitorando
    logger.info("Monitoramento iniciado.")
    async with httpx.AsyncClient() as client:
        while monitorando:
            try:
                oportunidades = []
                for moeda in MOEDAS_MONITORADAS:
                    # Monta par moeda/USDC
                    pair = f"{moeda}USDC"
                    precos = {}
                    for exchange in EXCHANGES:
                        url = f"https://api.cryptorank.io/v0/markets/prices?pair={pair}&exchange={exchange}"
                        try:
                            r = await client.get(url, timeout=10)
                            if r.status_code == 200:
                                data = r.json()
                                price = data.get("data", {}).get("price")
                                if price:
                                    precos[exchange] = float(price)
                                    logger.debug(f"Preço {moeda} na {exchange}: {price}")
                            else:
                                logger.warning(f"Erro {r.status_code} para {pair} na {exchange}")
                        except Exception as e:
                            logger.warning(f"Erro ao consultar {pair} na {exchange}: {e}")
                    # Verifica arbitragem entre exchanges para essa moeda
                    if len(precos) < 2:
                        continue
                    max_ex = max(precos, key=precos.get)
                    min_ex = min(precos, key=precos.get)
                    max_price = precos[max_ex]
                    min_price = precos[min_ex]
                    lucro = (max_price - min_price) / min_price * 100
                    if lucro >= lucro_minimo_atual:
                        msg = (
                            f"Oportunidade em {pair}:\n"
                            f"Comprar em {min_ex} a {min_price:.6f} USDC\n"
                            f"Vender em {max_ex} a {max_price:.6f} USDC\n"
                            f"Lucro estimado: {lucro:.2f}%"
                        )
                        oportunidades.append(msg)
                if oportunidades:
                    texto = "⚡ Novas oportunidades de arbitragem:\n\n" + "\n\n".join(oportunidades)
                    await app.bot.send_message(chat_id=CHAT_ID, text=texto)
                else:
                    logger.debug("Nenhuma oportunidade encontrada no ciclo atual.")
            except Exception as e:
                logger.error(f"Erro geral no monitoramento: {e}")
            await asyncio.sleep(10)  # Espera 10 segundos antes do próximo ciclo
    logger.info("Monitoramento finalizado.")

# Função main para iniciar o bot

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("setlucro", set_lucro))
    app.add_handler(CommandHandler("addmoeda", add_moeda))
    app.add_handler(CommandHandler("addexchange", add_exchange))

    logger.info("Bot iniciado.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
