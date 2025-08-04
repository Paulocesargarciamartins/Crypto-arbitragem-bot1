import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = '7218062934:AAECGNPQN3ITPQ-GZOTVTR_EQC7G9FYNBZQ'
CHAT_ID = '1093248456'

class ArbitragemMonitor:
    def __init__(self, application):
        self.application = application
        self.monitorando = True
        self.percentual_lucro = 1.5
        self.moedas_monitoradas = ['BTC', 'ETH', 'LTC']
        self.exchanges_monitoradas = ['binance', 'coinbase', 'kraken', 'bitstamp']
        self.arbitragem_task = None

    async def verificar_arbitragem(self):
        async with aiohttp.ClientSession() as session:
            while self.monitorando:
                try:
                    oportunidades = []
                    # Simulação ou lógica real de arbitragem
                    # oportunidades.append("Exemplo de oportunidade!")

                    if oportunidades:
                        mensagem = "\n".join(oportunidades)
                        await self.application.bot.send_message(chat_id=CHAT_ID, text=mensagem)

                except asyncio.CancelledError:
                    print("Tarefa cancelada.")
                    break
                except Exception as e:
                    print(f"Erro no monitoramento: {e}")
                
                await asyncio.sleep(30)

    async def start_monitoramento(self):
        self.monitorando = True
        if self.arbitragem_task and not self.arbitragem_task.done():
            return
        self.arbitragem_task = asyncio.create_task(self.verificar_arbitragem())

    async def stop_monitoramento(self):
        self.monitorando = False
        if self.arbitragem_task:
            self.arbitragem_task.cancel()
            try:
                await self.arbitragem_task
            except asyncio.CancelledError:
                pass

# Comandos do bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monitor = context.bot_data['monitor']
    await monitor.start_monitoramento()
    await update.message.reply_text("✅ Monitoramento iniciado!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monitor = context.bot_data['monitor']
    await monitor.stop_monitoramento()
    await update.message.reply_text("🛑 Monitoramento parado!")

async def porcentagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monitor = context.bot_data['monitor']
    try:
        nova = float(context.args[0])
        monitor.percentual_lucro = nova
        await update.message.reply_text(f"✅ Novo percentual de lucro: {nova}%")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Use: /porcentagem 2.5")

async def moeda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monitor = context.bot_data['monitor']
    if context.args:
        monitor.moedas_monitoradas = [moeda.upper() for moeda in context.args]
        await update.message.reply_text(f"✅ Moedas atualizadas: {', '.join(monitor.moedas_monitoradas)}")
    else:
        await update.message.reply_text("❌ Use: /moeda BTC ETH LTC")

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monitor = context.bot_data['monitor']
    if context.args:
        monitor.exchanges_monitoradas = [ex.lower() for ex in context.args]
        await update.message.reply_text(f"✅ Exchanges atualizadas: {', '.join(monitor.exchanges_monitoradas)}")
    else:
        await update.message.reply_text("❌ Use: /exchange binance coinbase kraken")

# Inicialização do app com função assíncrona correta
async def post_init(application):
    monitor = application.bot_data['monitor']
    await monitor.start_monitoramento()

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    monitor = ArbitragemMonitor(app)
    app.bot_data['monitor'] = monitor

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("porcentagem", porcentagem))
    app.add_handler(CommandHandler("moeda", moeda))
    app.add_handler(CommandHandler("exchange", exchange))

    # ✅ Função post_init corrigida
    app.post_init = post_init

    app.run_polling()

if __name__ == '__main__':
    main()
