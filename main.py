import asyncio
import aiohttp
import time
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Configuração ---
# Utilize variáveis de ambiente para tokens em produção!
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'

class ArbitragemMonitor:
    def __init__(self, bot):
        self.bot = bot
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

                    for moeda in self.moedas_monitoradas:
                        for ex1 in self.exchanges_monitoradas:
                            for ex2 in self.exchanges_monitoradas:
                                if ex1 == ex2:
                                    continue
                                preco_compra = 100
                                preco_venda = 100 + self.percentual_lucro
                                lucro = preco_venda - preco_compra
                                percentual = (lucro / preco_compra) * 100

                                if percentual >= self.percentual_lucro:
                                    oportunidades.append(
                                        f'Arbitragem detectada: {moeda} | Comprar em {ex1} a {preco_compra}, Vender em {ex2} a {preco_venda} | Lucro: {percentual:.2f}%'
                                    )

                    if oportunidades:
                        mensagem = "\n".join(oportunidades)
                        await self.bot.send_message(chat_id=CHAT_ID, text=mensagem)
                    
                except Exception as e:
                    print(f"Erro no monitoramento de arbitragem: {e}")

                await asyncio.sleep(30)
    
    async def start_monitoramento(self):
        self.monitorando = True
        if self.arbitragem_task and not self.arbitragem_task.done():
            # A tarefa já está rodando, não faça nada.
            return
        
        # Cria a tarefa e armazena a referência para poder cancelá-la depois.
        self.arbitragem_task = asyncio.create_task(self.verificar_arbitragem())

    async def stop_monitoramento(self):
        self.monitorando = False
        if self.arbitragem_task:
            self.arbitragem_task.cancel()
            try:
                await self.arbitragem_task
            except asyncio.CancelledError:
                print("Monitoramento de arbitragem cancelado.")

# HANDLERS COMANDOS
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

# Inicialização do bot com comandos
async def main():
    bot = telegram.Bot(token=TOKEN)
    monitor = ArbitragemMonitor(bot)
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Armazena a instância do monitor nos dados do bot para acesso nos handlers
    app.bot_data['monitor'] = monitor

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("porcentagem", porcentagem))
    app.add_handler(CommandHandler("moeda", moeda))
    app.add_handler(CommandHandler("exchange", exchange))

    # Inicia o monitoramento de arbitragem ao iniciar o bot
    await monitor.start_monitoramento()

    # Registra o hook de shutdown para cancelar a tarefa de arbitragem
    app.add_shutdown_handler(monitor.stop_monitoramento)

    # Executa o bot
    await app.run_polling()

# Início
if __name__ == '__main__':
    asyncio.run(main())
