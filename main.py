import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import httpx
import time

# Configurações iniciais (deixe as suas credenciais)
TOKEN = "7218062934:AAFokGnqbOozHMLEB63IsTjxA8uZhfBoZj8"
CHAT_ID = 1093248456  # seu chat id

# Variáveis globais para controle
monitorar = False
percentual_minimo = 0.5  # % lucro mínimo padrão
moedas = ["BTC", "ETH", "USDT", "BNB", "DOGE"]  # inicial, pode expandir
exchanges = ["binance", "kucoin", "gateio", "okx", "bybit"]  # inicial, pode expandir

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# Função para simular fetch de preços (você pode adaptar com sua API real)
async def obter_preco(moeda, exchange):
    # Exemplo: URL fictícia, substitua pela sua API real
    url = f"https://api.exemplo.com/preco?moeda={moeda}usdt&exchange={exchange}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return float(data["preco"])
    except Exception as e:
        logger.warning(f"Erro ao obter preço de {moeda} na {exchange}: {e}")
        return None

# Função principal de varredura e envio de alertas
async def monitorar_oportunidades(app: ApplicationBuilder.application):
    global monitorar, percentual_minimo, moedas, exchanges

    while True:
        if monitorar:
            for moeda in moedas:
                precos = {}
                for exchange in exchanges:
                    preco = await obter_preco(moeda, exchange)
                    if preco:
                        precos[exchange] = preco

                if len(precos) >= 2:
                    # Calcula arbitragem simples
                    min_ex = min(precos, key=precos.get)
                    max_ex = max(precos, key=precos.get)
                    min_preco = precos[min_ex]
                    max_preco = precos[max_ex]
                    lucro = ((max_preco - min_preco) / min_preco) * 100

                    if lucro >= percentual_minimo:
                        texto = (f"Oportunidade de arbitragem detectada!\n"
                                 f"Moeda: {moeda}\n"
                                 f"Comprar em: {min_ex} por {min_preco:.4f} USDT\n"
                                 f"Vender em: {max_ex} por {max_preco:.4f} USDT\n"
                                 f"Lucro estimado: {lucro:.2f}%")
                        await app.bot.send_message(chat_id=CHAT_ID, text=texto)

        await asyncio.sleep(60)  # aguarda 1 minuto entre varreduras

# Comandos Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorar
    monitorar = True
    await update.message.reply_text("Monitoramento iniciado.")
    logger.info("Monitoramento iniciado via comando /start.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorar
    monitorar = False
    await update.message.reply_text("Monitoramento pausado.")
    logger.info("Monitoramento pausado via comando /stop.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = "rodando" if monitorar else "parado"
    await update.message.reply_text(f"Monitoramento está {status_text}.\n"
                                    f"% mínimo: {percentual_minimo}%\n"
                                    f"Moedas: {', '.join(moedas)}\n"
                                    f"Exchanges: {', '.join(exchanges)}")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (f"Pares monitorados:\nMoedas: {', '.join(moedas)}\n"
             f"Exchanges: {', '.join(exchanges)}\n"
             f"Lucro mínimo: {percentual_minimo}%")
    await update.message.reply_text(texto)

async def addmoeda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /addmoeda SYMBOL")
        return
    nova_moeda = context.args[0].upper()
    if nova_moeda not in moedas:
        moedas.append(nova_moeda)
        await update.message.reply_text(f"Moeda {nova_moeda} adicionada.")
    else:
        await update.message.reply_text(f"Moeda {nova_moeda} já está na lista.")

async def addexchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /addexchange nome_da_exchange")
        return
    nova_exchange = context.args[0].lower()
    if nova_exchange not in exchanges:
        exchanges.append(nova_exchange)
        await update.message.reply_text(f"Exchange {nova_exchange} adicionada.")
    else:
        await update.message.reply_text(f"Exchange {nova_exchange} já está na lista.")

async def porcentagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global percentual_minimo
    if not context.args:
        await update.message.reply_text("Uso: /porcentagem valor (ex: /porcentagem 1.5)")
        return
    try:
        valor = float(context.args[0])
        if valor <= 0:
            raise ValueError()
        percentual_minimo = valor
        await update.message.reply_text(f"Lucro mínimo alterado para {percentual_minimo}%.")
    except ValueError:
        await update.message.reply_text("Valor inválido. Use um número maior que 0.")

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comandos = (
        "/start - Inicia monitoramento\n"
        "/stop - Para monitoramento\n"
        "/status - Status atual\n"
        "/listar - Lista moedas, exchanges e %\n"
        "/addmoeda SYMBOL - Adiciona moeda\n"
        "/addexchange nome - Adiciona exchange\n"
        "/porcentagem VALOR - Define lucro mínimo\n"
        "/ajuda - Mostra essa ajuda"
    )
    await update.message.reply_text(comandos)

# Função principal que inicializa o bot e os handlers
async def main():
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("listar", listar))
    application.add_handler(CommandHandler("addmoeda", addmoeda))
    application.add_handler(CommandHandler("addexchange", addexchange))
    application.add_handler(CommandHandler("porcentagem", porcentagem))
    application.add_handler(CommandHandler("ajuda", ajuda))

    # Inicia a tarefa assíncrona do monitoramento
    asyncio.create_task(monitorar_oportunidades(application))

    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
