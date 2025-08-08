import asyncio
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuração básica de logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Configurações do bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- FUNÇÕES DE HANDLER DO TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text("Olá! Bot de arbitragem de teste. Estou online e respondendo.")
    logger.warning(f"Bot iniciado por chat_id: {update.message.chat_id}")

async def test_bot_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comando de teste recebido! O bot está funcionando corretamente.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_bot_function))

    logger.warning("Iniciando o bot de Telegram...")
    await app.run_polling()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Bot desligado manualmente.")
    except Exception as e:
        logger.error(f"Erro fatal no loop principal: {e}", exc_info=True)
