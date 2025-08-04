import os
import asyncio
import aiohttp
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue, Defaults

# Configuração de Logs
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG if DEBUG else logging.INFO
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Configurações padrão
PROFIT_PERCENT_THRESHOLD = float(os.getenv("PROFIT_PERCENT_THRESHOLD", 1.0))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 60))

# Pares com USDC - 150 primeiras moedas Binance adaptadas
PAIRS = [
    "BTC/USDC", "ETH/USDC", "XRP/USDC", "USDT/USDC", "BNB/USDC", "SOL/USDC", "USDC/USDC",
    "TRX/USDC", "DOGE/USDC", "ADA/USDC", "SUI/USDC", "XLM/USDC", "BCH/USDC", "LINK/USDC",
    "HBAR/USDC", "AVAX/USDC", "LTC/USDC", "SHIB/USDC", "XMR/USDC", "UNI/USDC", "DOT/USDC",
    "PEPE/USDC", "AAVE/USDC", "CRO/USDC", "ETC/USDC", "NEAR/USDC", "OKB/USDC", "APT/USDC",
    "ICP/USDC", "ALGO/USDC", "ATOM/USDC", "TRUMP/USDC", "ENA/USDC", "WIF/USDC", "FTM/USDC",
    "FIL/USDC", "GRT/USDC", "IOTA/USDC", "MKR/USDC", "IMX/USDC", "INJ/USDC", "AR/USDC",
    "THETA/USDC", "NEO/USDC", "ASTR/USDC", "AXS/USDC", "ZEC/USDC", "STX/USDC", "KCS/USDC",
    "GALA/USDC", "CRV/USDC", "SAND/USDC", "CHZ/USDC", "CFX/USDC", "DYDX/USDC", "KLAY/USDC",
    "ENJ/USDC", "RNDR/USDC", "GNO/USDC", "WEMIX/USDC", "CAKE/USDC", "GMX/USDC", "MINA/USDC",
    "FLOW/USDC", "FXS/USDC", "USDE/USDC", "EOS/USDC", "DASH/USDC", "CELO/USDC", "EGLD/USDC",
    "APE/USDC", "SUSHI/USDC", "RPL/USDC", "ROSE/USDC", "XEC/USDC", "SNX/USDC", "1INCH/USDC",
    "ACA/USDC", "KAVA/USDC", "VET/USDC", "LRC/USDC", "GT/USDC", "TON/USDC", "BTT/USDC",
    "BAT/USDC", "ZIL/USDC", "MANA/USDC", "NEXO/USDC", "HNT/USDC", "QTUM/USDC", "TFUEL/USDC",
    "BICO/USDC", "DODO/USDC", "AXL/USDC", "SKL/USDC", "WAVES/USDC", "TWT/USDC", "COMP/USDC"
]

EXCHANGES = [
    'binance', 'bitfinex', 'kraken', 'kucoin', 'coinbase',
    'gateio', 'bitstamp', 'mexc', 'bitmart', 'okx',
    'bybit', 'bingx', 'huobi', 'whitebit'
]

# Variável global para armazenar o lucro mínimo ajustado via Telegram
current_profit_threshold = PROFIT_PERCENT_THRESHOLD


async def get_price(session, exchange, pair):
    try:
        base, quote = pair.split('/')
        url = f'https://api.cryptorank.io/v0/markets/prices?pair={base}{quote}&exchange={exchange}'
        async with session.get(url, timeout=10) as response:
            if response.status == 404:
                if DEBUG:
                    logger.debug(f"Par {pair} não encontrado na exchange {exchange} (404). Ignorando.")
                return None
            response.raise_for_status()
            data = await response.json()
            price = data.get('price', None)
            if DEBUG:
                logger.debug(f"Preço obtido: {pair} na {exchange} = {price}")
            return price
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Erro ao obter preço de {pair} na exchange {exchange}: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"Erro ao processar dados de {pair} na exchange {exchange}: {e}")
        return None


async def check_arbitrage_job(context: ContextTypes.DEFAULT_TYPE):
    global current_profit_threshold
    logger.info("Iniciando verificação de arbitragem...")
    async with aiohttp.ClientSession() as session:
        for pair in PAIRS:
            tasks = [get_price(session, exchange, pair) for exchange in EXCHANGES]
            prices_raw = await asyncio.gather(*tasks)

            prices = []
            for i, price in enumerate(prices_raw):
                if price is not None and price > 0:
                    prices.append((EXCHANGES[i], price))

            if len(prices) >= 2:
                min_ex, min_price = min(prices, key=lambda x: x[1])
                max_ex, max_price = max(prices, key=lambda x: x[1])

                profit_percent = ((max_price - min_price) / min_price) * 100

                if profit_percent >= current_profit_threshold:
                    msg = (
                        f"📈 *Oportunidade de Arbitragem detectada!*\n\n"
                        f"Par: {pair}\n"
                        f"Comprar em: {min_ex.upper()} a {min_price:.6f}\n"
                        f"Vender em: {max_ex.upper()} a {max_price:.6f}\n"
                        f"Lucro estimado: {profit_percent:.2f}%"
                    )
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')

    logger.info("Verificação de arbitragem finalizada.")


# --- Comandos do Telegram ---


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Olá! Eu sou o Crypto Arbitragem Bot.\n'
        'Use /run para iniciar a verificação periódica.\n'
        'Use /stop para parar.\n'
        'Use /status para ver o status atual.\n'
        'Use /setprofit <valor> para ajustar o lucro mínimo (%).\n'
        'Use /listpairs para listar os pares monitorados.'
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
            f'Verificação de arbitragem iniciada. Checando a cada {CHECK_INTERVAL_SECONDS} segundos.'
        )
    else:
        await update.message.reply_text(
            'A verificação de arbitragem já está em execução.'
        )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name('arbitrage_job')
    if jobs:
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text('Verificação de arbitragem parada.')
    else:
        await update.message.reply_text('A verificação não está em execução.')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name('arbitrage_job')
    if jobs:
        await update.message.reply_text(
            f'O bot está *ATIVO*.\nLucro mínimo configurado: {current_profit_threshold}%\n'
            f'Checando a cada {CHECK_INTERVAL_SECONDS} segundos.'
        , parse_mode='Markdown')
    else:
        await update.message.reply_text('O bot está *INATIVO*. Use /run para iniciar.', parse_mode='Markdown')


async def setprofit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_profit_threshold
    if context.args:
        try:
            valor = float(context.args[0].replace(',', '.'))
            if valor <= 0:
                await update.message.reply_text('Por favor, informe um valor maior que 0.')
                return
            current_profit_threshold = valor
            await update.message.reply_text(f'Lucro mínimo ajustado para {current_profit_threshold}%.')
        except ValueError:
            await update.message.reply_text('Por favor, informe um número válido.')
    else:
        await update.message.reply_text('Use /setprofit <valor>, por exemplo: /setprofit 0.5')


async def listpairs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "Pares monitorados:\n" + ", ".
