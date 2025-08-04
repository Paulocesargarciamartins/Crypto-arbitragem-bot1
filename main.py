import asyncio
import aiohttp
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
from decimal import Decimal, InvalidOperation

# ==================== CONFIGURAÇÕES ====================
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'  # <-- Seu token
CHAT_ID = '1093248456'  # <-- Seu chat_id
PORCENTAGEM_MINIMA = Decimal("0.5")  # Pode ser alterada por comando
PAUSADO = False

EXCHANGES = [
    'binance', 'kucoin', 'bitget', 'coinbase', 'bybit', 'mexc',
    'gate', 'huobi', 'bitmart', 'okx', 'bitfinex', 'lbank',
    'crypto_com', 'bigone'
]

PARES = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT',
    'DOGE/USDT', 'SHIB/USDT', 'AVAX/USDT', 'MATIC/USDT', 'DOT/USDT',
    'TRX/USDT', 'LTC/USDT', 'BCH/USDT', 'UNI/USDT', 'ETC/USDT',
    'XLM/USDT', 'ATOM/USDT', 'VET/USDT', 'ICP/USDT', 'FIL/USDT',
    'AAVE/USDT', 'ALGO/USDT', 'NEAR/USDT', 'EOS/USDT', 'MANA/USDT',
    'XTZ/USDT', 'EGLD/USDT', 'RUNE/USDT', 'HBAR/USDT', 'SAND/USDT',
    'AXS/USDT', 'GRT/USDT', 'CRV/USDT', '1INCH/USDT', 'ZIL/USDT',
    'ZRX/USDT', 'YFI/USDT', 'ENJ/USDT', 'FLOW/USDT', 'GALA/USDT',
    'IMX/USDT', 'LDO/USDT', 'DYDX/USDT', 'OP/USDT', 'ARB/USDT',
    'SUSHI/USDT', 'STX/USDT', 'SNX/USDT', 'REN/USDT', 'RSR/USDT',
    'OMG/USDT', 'OCEAN/USDT', 'NKN/USDT', 'MINA/USDT', 'MASK/USDT',
    'KNC/USDT', 'KAVA/USDT', 'JOE/USDT', 'INJ/USDT', 'ICX/USDT',
    'HOT/USDT', 'GLMR/USDT', 'ENS/USDT', 'CTSI/USDT', 'COTI/USDT',
    'COMP/USDT', 'CELR/USDT', 'CAKE/USDT', 'BNT/USDT', 'BEL/USDT',
    'BAL/USDT', 'ANKR/USDT', 'ANT/USDT', 'ALICE/USDT', 'AGLD/USDT',
    'ACH/USDT', '1000SHIB/USDT', '1000FLOKI/USDT', 'LUNA/USDT',
    'USTC/USDT', 'WOO/USDT', 'TWT/USDT', 'TON/USDT', 'PEPE/USDT',
    'FET/USDT', 'PYR/USDT', 'FXS/USDT', 'DODO/USDT', 'DENT/USDT',
    'CTK/USDT', 'BLUR/USDT', 'BTG/USDT', 'ZEC/USDT', 'QTUM/USDT',
    'SC/USDT', 'WAVES/USDT', 'STORJ/USDT', 'SXP/USDT', 'TOMO/USDT',
    'VTHO/USDT', 'ZEN/USDT', 'ZRX/USDT', 'WRX/USDT', 'YGG/USDT'
]

async def buscar_oportunidades():
    global PAUSADO
    async with aiohttp.ClientSession() as session:
        while not PAUSADO:
            for par in PARES:
                url = f'https://api.coingecko.com/api/v3/simple/price?ids={par.split("/")[0].lower()}&vs_currencies=usdt&include_market_cap=false&include_24hr_vol=false&include_24hr_change=false&include_last_updated_at=false'
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue
                        data = await response.json()
                        preco = data.get(par.split("/")[0].lower(), {}).get('usdt')
                        if preco:
                            preco_decimal = Decimal(str(preco))
                            for exchange in EXCHANGES:
                                preco_simulado = preco_decimal * (Decimal("1.01"))  # simulação
                                diferenca = abs(preco_decimal - preco_simulado)
                                lucro_percentual = (diferenca / preco_decimal) * 100
                                if lucro_percentual >= PORCENTAGEM_MINIMA:
                                    mensagem = (
                                        f"💸 Oportunidade de Arbitragem 💸\n\n"
                                        f"Par: {par}\n"
                                        f"Exchange A: {exchange}\n"
                                        f"Exchange B: Simulada\n"
                                        f"Preço A: {preco_decimal:.4f} USDT\n"
                                        f"Preço B: {preco_simulado:.4f} USDT\n"
                                        f"Lucro: {lucro_percentual:.2f}%"
                                    )
                                    await enviar_telegram(mensagem)
                except Exception as e:
                    print(f"Erro: {e}")
            await asyncio.sleep(30)

async def enviar_telegram(mensagem):
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mensagem)

# ==================== COMANDOS TELEGRAM ====================
async def set_percent(update, context: ContextTypes.DEFAULT_TYPE):
    global PORCENTAGEM_MINIMA
    try:
        valor = context.args[0]
        PORCENTAGEM_MINIMA = Decimal(valor)
        await update.message.reply_text(f"🔧 Porcentagem mínima atualizada para {valor}%")
    except (IndexError, InvalidOperation):
        await update.message.reply_text("❌ Uso: /set 0.5")

async def pause(update, context: ContextTypes.DEFAULT_TYPE):
    global PAUSADO
    PAUSADO = True
    await update.message.reply_text("⏸️ Bot pausado.")

async def resume(update, context: ContextTypes.DEFAULT_TYPE):
    global PAUSADO
    PAUSADO = False
    await update.message.reply_text("▶️ Bot retomado.")
    asyncio.create_task(buscar_oportunidades())

# ==================== INICIAR BOT ====================
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("set", set_percent))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    asyncio.create_task(buscar_oportunidades())
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
