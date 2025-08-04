import os
import asyncio
import aiohttp
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# Configuração de Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PROFIT_PERCENT_THRESHOLD = float(os.getenv("PROFIT_PERCENT_THRESHOLD", 1.0))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 60))

EXCHANGES = [
    'binance', 'bitfinex', 'kraken', 'kucoin', 'coinbase',
    'gateio', 'bitstamp', 'mexc', 'bitmart', 'okx',
    'bybit', 'bingx', 'huobi', 'whitebit'
]

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'ADA/USDT', 'BNB/USDT', 'XRP/USDT',
    'SOL/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'TRX/USDT',
    'MATIC/USDT', 'SHIB/USDT', 'ATOM/USDT', 'LTC/USDT', 'BCH/USDT',
    'FTM/USDT', 'NEAR/USDT', 'APE/USDT', 'CHZ/USDT', 'ALGO/USDT',
    'XLM/USDT', 'EGLD/USDT', 'VET/USDT', 'SAND/USDT', 'AAVE/USDT',
    'GALA/USDT', 'AXS/USDT', 'THETA/USDT', 'RUNE/USDT', 'ZIL/USDT',
    'CRV/USDT', '1INCH/USDT', 'COMP/USDT', 'KSM/USDT', 'ENJ/USDT',
    'XTZ/USDT', 'LRC/USDT', 'SNX/USDT', 'DYDX/USDT', 'YFI/USDT',
    'UNI/USDT', 'REN/USDT', 'ZEC/USDT', 'DASH/USDT', 'WAVES/USDT',
    'ICX/USDT', 'OMG/USDT', 'STORJ/USDT', 'SUSHI/USDT', 'QTUM/USDT',
    'ANKR/USDT', 'RSR/USDT', 'XEM/USDT', 'BAND/USDT', 'SKL/USDT',
    'LUNA/USDT', 'SRM/USDT', 'CVC/USDT', 'STMX/USDT', 'TOMO/USDT',
    'KAVA/USDT', 'AR/USDT', 'GLMR/USDT', 'ACA/USDT', 'FET/USDT',
    'INJ/USDT', 'CFX/USDT', 'OP/USDT', 'LDO/USDT', 'RNDR/USDT',
    'XNO/USDT', 'PEPE/USDT', 'BONK/USDT', 'WLD/USDT', 'TURBO/USDT',
    'SEI/USDT', 'PYTH/USDT', 'TIA/USDT', 'AEVO/USDT', 'PENDLE/USDT',
    'DOGAI/USDT', 'JASMY/USDT', 'HOOK/USDT', 'BLUR/USDT', 'ID/USDT',
    'SUI/USDT', 'ARB/USDT', 'GMX/USDT', 'CRO/USDT', 'BICO/USDT',
    'MASK/USDT', 'ZRX/USDT', 'RLC/USDT', 'CELR/USDT', 'NKN/USDT',
    'NMR/USDT', 'ILV/USDT', 'AGIX/USDT', 'HIGH/USDT', 'OCEAN/USDT'
]

async def get_price(session, exchange, pair):
    try:
        base, quote = pair.split('/')
        url = f'https://api.cryptorank.io/v0/markets/prices?pair={base}{quote}&exchange={exchange}'
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get('price', None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Erro ao obter preço de {pair} na exchange {exchange}: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"Erro ao processar dados de {pair} na exchange {exchange}: {e}")
        return None

async def check_arbitrage_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Iniciando verificação de arbitragem...")
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            tasks = [get_price(session, exchange, pair) for exchange in EXCHANGES]
            prices_raw = await asyncio.gather(*tasks)

            prices = []
            for i, price in enumerate(prices_raw):
                if price is not None:
                    prices.append((EXCHANGES[i], price))

            if len(prices) >= 2:
                min_ex, min_price = min(prices, key=lambda x: x[1])
                max_ex, max_price = max(prices, key=lambda x: x[1])
                
                if min_price == 0:
                    continue
                
                profit_percent = ((max_price - min_price) / min_price) * 100
                
                if profit_percent >= PROFIT_PERCENT_THRESHOLD:
                    msg = (
                        f"📈 Oportunidade de Arbitragem:\n\n"
                        f"Par: {pair}\n"
                        f"Comprar em: {min_ex.upper()} a {min_price:.2f}\n"
                        f"Vender em: {max_ex.upper()} a {max_price:.2f}\n"
                        f"Lucro estimado: {profit_percent:.2f}%"
                    )
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg)

    logger.info("Verificação de arbitragem finalizada.")

# --- Comandos do Telegram ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Olá! Eu sou o Crypto Arbitragem Bot. Para iniciar as verificações, use o comando /run.'
    )

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not any(j.name == 'arbitrage_job' for j in context.job_queue.jobs()):
        context.job_queue.run_repeating(
            check_arbitrage_job, 
            interval=CHECK_INTERVAL_SECONDS, 
            first=1, 
            name='arbitrage_job'
        )
        await update.message.reply_text(
            f'Verificação de arbitragem iniciada. Verificando a cada {CHECK_INTERVAL_SECONDS} segundos.'
        )
    else:
        await update.message.reply_text(
            'A verificação de arbitragem já está em execução.'
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job = context.job_queue.get_jobs_by_name('arbitrage_job')
    if job:
        job[0].schedule_removal()
        await update.message.reply_text('Verificação de arbitragem parada.')
    else:
        await update.message.reply_text('A verificação não está em execução.')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job = context.job_queue.get_jobs_by_name('arbitrage_job')
    if job:
        await update.message.reply_text('O bot está ATIVO e verificando arbitragem.')
    else:
        await update.message.reply_text('O bot está INATIVO. Use /run para iniciar.')

def main():
    if not TOKEN or not CHAT_ID:
        logger.error("TOKEN ou CHAT_ID não estão definidos. Verifique seu arquivo .env")
        return

    application = Application.builder().token(TOKEN).build()
    job_queue = application.job_queue

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    
    application.run_polling()

if __name__ == "__main__":
    main()
