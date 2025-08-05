import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import ccxt.async_support as ccxt
import os
import nest_asyncio

# Aplica o patch para permitir loops aninhados,
# corrigindo o problema no ambiente Heroku
nest_asyncio.apply()

# Configurações básicas
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LUCRO_MINIMO_PORCENTAGEM = 2.0

# Exchanges confiáveis para monitorar (20)
EXCHANGES_LIST = [
    'binance', 'coinbasepro', 'kraken', 'bitfinex', 'bittrex',
    'huobipro', 'okex', 'bitstamp', 'gateio', 'kucoin',
    'poloniex', 'ftx', 'bitmart', 'bybit', 'coinex',
    'bitget', 'ascendex', 'bibox', 'bitflyer', 'digifinex'
]

# 150 Pares USDT (com base em dados de mercado recentes)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "USDT/USDT", "BNB/USDT", "SOL/USDT", 
    "USDC/USDT", "STETH/USDT", "DOGE/USDT", "TRX/USDT", "ADA/USDT", "XLM/USDT", 
    "BCH/USDT", "SUI/USDT", "LINK/USDT", "HBAR/USDT", "AVAX/USDT", "LTC/USDT", 
    "SHIB/USDT", "UNI/USDT", "XMR/USDT", "DOT/USDT", "PEPE/USDT", "AAVE/USDT", 
    "CRO/USDT", "DAI/USDT", "ETC/USDT", "ONDO/USDT", "NEAR/USDT", "OKB/USDT", 
    "APT/USDT", "ICP/USDT", "ALGO/USDT", "ATOM/USDT", "WBTC/USDT", "TON/USDT", 
    "USDS/USDT", "ENA/USDT", "TAO/USDT", "MNT/USDT", "JITOSOL/USDT", "KAS/USDT", 
    "PENGU/USDT", "ARB/USDT", "BONK/USDT", "RENDER/USDT", "POL/USDT", "WLD/USDT", 
    "STORY/USDT", "TRUMP/USDT", "SEI/USDT", "SKY/USDT", "HYPE/USDT", "WBETH/USDT", 
    "MKR/USDT", "FIL/USDT", "OP/USDT", "IOTA/USDT", "DASH/USDT", "NEXO/USDT", 
    "SUSHI/USDT", "BGB/USDT", "WIF/USDT", "FLOW/USDT", "IMX/USDT", "RUNE/USDT", 
    "LDO/USDT", "FET/USDT", "GRT/USDT", "FTM/USDT", "QNT/USDT", "STRK/USDT", 
    "VET/USDT", "INJ/USDT", "DYDX/USDT", "EGLD/USDT", "JUP/USDT", "GALA/USDT", 
    "AXS/USDT", "THETA/USDT", "MINA/USDT", "ENJ/USDT", "CHZ/USDT", "YFI/USDT", 
    "GMX/USDT", "ZEC/USDT", "ZIL/USDT", "GMT/USDT", "WAVES/USDT", "KLAY/USDT", 
    "KAVA/USDT", "CELO/USDT", "XEC/USDT", "HNT/USDT", "RSR/USDT", "RVN/USDT", 
    "BAT/USDT", "DCR/USDT", "DGB/USDT", "XEM/USDT", "SC/USDT", "ZEN/USDT", 
    "COMP/USDT", "SNX/USDT", "UMA/USDT", "CRV/USDT", "KNC/USDT", "BAL/USDT", 
    "ZRX/USDT", "OGN/USDT", "RLC/USDT", "BAND/USDT", "TOMO/USDT", "AR/USDT", 
    "PERP/USDT", "LINA/USDT", "ANKR/USDT", "OCEAN/USDT", "SFP/USDT", "ONE/USDT", 
    "PHA/USDT", "CKB/USDT", "CTK/USDT", "YFII/USDT", "BOND/USDT", "UTK/USDT", 
    "CVC/USDT", "IRIS/USDT", "NULS/USDT", "NKN/USDT", "STX/USDT", "DODO/USDT", 
    "NMR/USDT", "MCO/USDT", "LPT/USDT", "SKL/USDT", "REQ/USDT", "CQT/USDT", 
    "WTC/USDT", "TCT/USDT", "COTI/USDT", "MDT/USDT", "TFUEL/USDT", "TUSD/USDT", 
    "SRM/USDT", "GLM/USDT", "MANA/USDT", "SAND/USDT", "ICP/USDT", "APE/USDT"
]

logging.basicConfig(
    format='[%(levelname)s] %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Função para checar arbitragem entre exchanges
async def check_arbitrage(bot):
    try:
        exchanges = {}
        for ex_id in EXCHANGES_LIST:
            exchange = getattr(ccxt, ex_id)({
                'enableRateLimit': True,
            })
            await exchange.load_markets()
            exchanges[ex_id] = exchange

        for pair in PAIRS:
            prices = {}
            for ex_id, exchange in exchanges.items():
                if pair in exchange.markets:
                    ticker = await exchange.fetch_ticker(pair)
                    prices[ex_id] = ticker['last']
            if len(prices) < 2:
                continue

            min_ex = min(prices, key=prices.get)
            max_ex = max(prices, key=prices.get)
            min_price = prices[min_ex]
            max_price = prices[max_ex]

            lucro = (max_price - min_price) / min_price * 100

            if lucro >= LUCRO_MINIMO_PORCENTAGEM:
                msg = (f"🟢 Arbitragem encontrada para {pair}!\n"
                       f"Comprar em {min_ex}: {min_price}\n"
                       f"Vender em {max_ex}: {max_price}\n"
                       f"Lucro estimado: {lucro:.2f}%")
                logger.info(msg)
                await bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text=msg)

        for exchange in exchanges.values():
            await exchange.close()

    except Exception as e:
        logger.error(f"Erro na checagem de arbitragem: {e}")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Ativado.\n"
        "Use /setlucro <valor> para definir lucro mínimo em %.\n"
        "Exemplo: /setlucro 3"
    )

# Comando /setlucro
async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LUCRO_MINIMO_PORCENTAGEM
    try:
        valor = float(context.args[0])
        LUCRO_MINIMO_PORCENTAGEM = valor
        await update.message.reply_text(f"Lucro mínimo atualizado para {valor}%")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setlucro 2.5")

# FUNÇÃO PRINCIPAL DO BOT
async def main():
    application = ApplicationBuilder().token(TOKEN).job_queue(JobQueue()).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))

    async def periodic_arbitrage_task(context: ContextTypes.DEFAULT_TYPE):
        await check_arbitrage(application.bot)

    application.job_queue.run_repeating(periodic_arbitrage_task, interval=60, first=5)

    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot"),
        BotCommand("setlucro", "Definir lucro mínimo em %")
    ])

    logger.info("Bot iniciado com sucesso.")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
