import os
import asyncio
import aiohttp
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# Configuração de Logs com DEBUG ativado
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # DEBUG para logs detalhados
)
logger = logging.getLogger(__name__)

# Carrega variáveis do arquivo .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PROFIT_PERCENT_THRESHOLD = float(os.getenv("PROFIT_PERCENT_THRESHOLD", 0.5))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 60))

# Exchanges confiáveis já presentes no seu código base
EXCHANGES = [
    'binance', 'bitfinex', 'kraken', 'kucoin', 'coinbase',
    'gateio', 'bitstamp', 'mexc', 'bitmart', 'okx',
    'bybit', 'bingx', 'huobi', 'whitebit', 'coinex',
    'poloniex', 'bittrex', 'hitbtc', 'gemini', 'bitflyer'
]

# Lista das 150 primeiras moedas da Binance em pares USDC
PAIRS = [
    'BTC/USDC', 'ETH/USDC', 'XRP/USDC', 'USDT/USDC', 'BNB/USDC', 'SOL/USDC', 'USDC/USDC',
    'TRX/USDC', 'DOGE/USDC', 'ADA/USDC', 'SUI/USDC', 'XLM/USDC', 'BCH/USDC', 'LINK/USDC',
    'HBAR/USDC', 'AVAX/USDC', 'LTC/USDC', 'SHIB/USDC', 'XMR/USDC', 'UNI/USDC', 'DOT/USDC',
    'PEPE/USDC', 'AAVE/USDC', 'CRO/USDC', 'ETC/USDC', 'NEAR/USDC', 'OKB/USDC', 'APT/USDC',
    'ICP/USDC', 'ALGO/USDC', 'ATOM/USDC', 'TRUMP/USDC', 'ENA/USDC', 'WIF/USDC', 'FTM/USDC',
    'FIL/USDC', 'GRT/USDC', 'IOTA/USDC', 'MKR/USDC', 'IMX/USDC', 'INJ/USDC', 'AR/USDC',
    'THETA/USDC', 'NEO/USDC', 'ASTR/USDC', 'AXS/USDC', 'ZEC/USDC', 'STX/USDC', 'KCS/USDC',
    'GALA/USDC', 'CRV/USDC', 'SAND/USDC', 'CHZ/USDC', 'CFX/USDC', 'DYDX/USDC', 'KLAY/USDC',
    'ENJ/USDC', 'RNDR/USDC', 'GNO/USDC', 'WEMIX/USDC', 'CAKE/USDC', 'GMX/USDC', 'MINA/USDC',
    'FLOW/USDC', 'FXS/USDC', 'USDE/USDC', 'EOS/USDC', 'DASH/USDC', 'CELO/USDC', 'EGLD/USDC',
    'APE/USDC', 'SUSHI/USDC', 'RPL/USDC', 'ROSE/USDC', 'XEC/USDC', 'SNX/USDC', '1INCH/USDC',
    'ACA/USDC', 'KAVA/USDC', 'VET/USDC', 'LRC/USDC', 'GT/USDC', 'TON/USDC', 'BTT/USDC',
    'BAT/USDC', 'ZIL/USDC', 'MANA/USDC', 'NEXO/USDC', 'HNT/USDC', 'QTUM/USDC', 'TFUEL/USDC',
    'BICO/USDC', 'DODO/USDC', 'AXL/USDC', 'SKL/USDC', 'WAVES/USDC', 'TWT/USDC', 'COMP/USDC',
    'TWT/USDC', 'MATIC/USDC', 'XNO/USDC', 'PEPE/USDC', 'BONK/USDC', 'WLD/USDC', 'TURBO/USDC',
    'SEI/USDC', 'PYTH/USDC', 'TIA/USDC', 'AEVO/USDC', 'PENDLE/USDC', 'DOGAI/USDC', 'JASMY/USDC',
    'HOOK/USDC', 'BLUR/USDC', 'ID/USDC', 'ARB/USDC', 'CRO/USDC', 'BICO/USDC', 'MASK/USDC',
    'ZRX/USDC', 'RLC/USDC', 'CELR/USDC', 'NKN/USDC', 'NMR/USDC', 'ILV/USDC', 'AGIX/USDC',
    'HIGH/USDC', 'OCEAN/USDC'
]

async def get_price(session, exchange, pair):
    try:
        base, quote = pair.split('/')
        url = f'https://api.cryptorank.io/v0/markets/prices?pair={base}{quote}&exchange={exchange}'
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            price = data.get('price', None)
            logger.debug(f"Preço {pair} na {exchange}: {price}")
            return price
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            logger.warning(f"Preço não encontrado para {pair} na {exchange} (404)")
        else:
            logger.warning(f"Erro HTTP para {pair} na {exchange}: {e}")
        return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Erro ao obter preço de {pair} na exchange {exchange}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao processar {pair} na {exchange}: {e}")
        return None

async def check_arbitrage_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Iniciando verificação de arbitragem...")
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            tasks = [get_price(session, exchange, pair) for exchange in EXCHANGES]
            prices_raw = await asyncio.gather(*tasks)

            prices = [(EXCHANGES[i], price) for i, price in enumerate(prices_raw) if price is not None]

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
                        f"Comprar em: {min_ex.upper()} a {min_price:.6f}\n"
                        f"Vender em: {max_ex.upper()} a {max_price:.6f}\n"
                        f"Lucro estimado: {profit_percent:.2f}%"
                    )
                    logger.info(f"Enviando mensagem: {msg}")
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            else:
                logger.debug(f"Pares insuficientes para arbitragem em {pair}: {len(prices)} preços encontrados")

    logger.info("Verificação de arbitragem finalizada.")

# --- Comandos Telegram ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Olá! Eu sou o Crypto Arbitragem Bot. Para iniciar as verificações, use /run. Para alterar o lucro mínimo use /setprofit <valor_em_percent>'
    )

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not any(j.name == 'arbitrage_job' for j in context.job_queue.jobs()):
        context.job_queue.run_repeating(
            check_arbitrage_job,
            interval=CHECK_INTERVAL_SECONDS,
            first=1,
            name='arbitrage_job'
        )
        await update.message.reply_text(f'Verificação de arbitragem iniciada. Intervalo: {CHECK_INTERVAL_SECONDS} segundos.')
    else:
        await update.message.reply_text('A verificação de arbitragem já está em execução.')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name('arbitrage_job')
    if jobs:
        jobs[0].schedule_removal()
        await update.message.reply_text('Verificação de arbitragem parada.')
    else:
        await update.message.reply_text('A verificação não está em execução.')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name('arbitrage_job')
    if jobs:
        await update.message.reply_text('O bot está ATIVO e verificando arbitragem.')
    else:
        await update.message.reply_text('O bot está INATIVO. Use /run para iniciar.')

async def setprofit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        novo_valor = float(context.args[0])
        global PROFIT_PERCENT_THRESHOLD
        PROFIT_PERCENT_THRESHOLD = novo_valor
        await update.message.reply_text(f'Lucro mínimo alterado para {novo_valor:.2f}%')
    except (IndexError, ValueError):
        await update.message.reply_text('Uso correto: /setprofit <valor_em_percent>')

def main():
    if not TOKEN or not CHAT_ID:
        logger.error("TOKEN ou CHAT_ID não definidos no arquivo .env")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("setprofit", setprofit_command))

    application.job_queue.run_repeating(check_arbitrage_job, interval=CHECK_INTERVAL_SECONDS, first=1, name='arbitrage_job')

    application.run_polling()

if __name__ == "__main__":
    main()
