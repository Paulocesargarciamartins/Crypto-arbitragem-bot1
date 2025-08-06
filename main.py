import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.async_support as ccxt
import os
import nest_asyncio
from datetime import datetime, timedelta

# Aplica o patch para permitir loops aninhados,
# corrigindo o problema no ambiente Heroku
nest_asyncio.apply()

# --- Configurações básicas ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Alterado o lucro mínimo padrão para um valor baixo de diagnóstico
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 0.5 
DEFAULT_TRADE_AMOUNT_USD = 50.0  # Quantidade de USD para verificar liquidez

# Limite máximo de lucro bruto para validação de dados.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0

# Exchanges confiáveis para monitorar
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitfinex', 'bitget', 'mexc'
]

# Pares USDT
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
    "MKR/USDT", "FIL/USDT", "OP/USDT", "IOTA/USDT"
]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

global_exchanges_instances = {}
# Dicionário para rastrear se os mercados de uma exchange já foram carregados
markets_loaded = {}

async def fetch_all_market_data_for_pair(exchange_instances, pair):
    tasks = []
    for ex_id, exchange in exchange_instances.items():
        if pair in exchange.markets and exchange.has['fetchOrderBook']:
            tasks.append(
                asyncio.create_task(fetch_order_book_safe(exchange, pair, ex_id))
            )
    results = await asyncio.gather(*tasks, return_exceptions=True)

    market_data = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Erro durante a busca de dados: {result}")
        elif result:
            ex_id, data = result
            market_data[ex_id] = data
    return market_data

async def fetch_order_book_safe(exchange, pair, ex_id):
    try:
        order_book = await exchange.fetch_order_book(pair, limit=100)
        if order_book and order_book['bids'] and order_book['asks']:
            best_bid = order_book['bids'][0][0]
            best_bid_volume = order_book['bids'][0][1]
            best_ask = order_book['asks'][0][0]
            best_ask_volume = order_book['asks'][0][1]

            if best_bid > 0 and best_ask > 0 and best_ask >= best_bid:
                return (ex_id, {
                    'bid': best_bid,
                    'bid_volume': best_bid_volume,
                    'ask': best_ask,
                    'ask_volume': best_ask_volume,
                    'timestamp': order_book.get('timestamp')
                })
        else:
            pass
    except ccxt.NetworkError as e:
        logger.warning(f"Erro de rede ao buscar {pair} em {ex_id}: {e}")
    except ccxt.ExchangeError as e:
        logger.warning(f"Erro da exchange ao buscar {pair} em {ex_id}: {e}")
    except Exception as e:
        logger.warning(f"Erro inesperado ao buscar {pair} em {ex_id}: {e}")
    return None

# --- FUNÇÃO DE ARBITRAGEM CORRIGIDA E OTIMIZADA (IGNORANDO TAXAS) ---
async def check_arbitrage(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = context.bot_data.get('admin_chat_id')
    if not chat_id:
        logger.warning("Nenhum chat_id de administrador configurado.")
        return

    try:
        # A taxa de negociação é ignorada neste diagnóstico
        lucro_minimo = context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
        trade_amount_usd = context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)

        logger.info(f"Iniciando checagem de arbitragem. Lucro MÍNIMO BRUTO: {lucro_minimo}%, Volume de trade: {trade_amount_usd} USD")

        exchanges_to_scan = {}
        for ex_id in EXCHANGES_LIST:
            try:
                if ex_id not in global_exchanges_instances:
                    exchange_class = getattr(ccxt, ex_id)
                    global_exchanges_instances[ex_id] = exchange_class({'enableRateLimit': True, 'timeout': 3000})

                exchange = global_exchanges_instances[ex_id]
                if not markets_loaded.get(ex_id):
                    await exchange.load_markets()
                    markets_loaded[ex_id] = True
                
                exchanges_to_scan[ex_id] = exchange
            except Exception as e:
                logger.error(f"ERRO: Não foi possível carregar a exchange {ex_id}: {e}")
        
        if len(exchanges_to_scan) < 2:
            logger.error("Não há exchanges suficientes para checar arbitragem.")
            return

        for pair in PAIRS:
            market_data = await fetch_all_market_data_for_pair(exchanges_to_scan, pair)
            
            if len(market_data) < 2:
                continue

            best_buy_price = float('inf')
            buy_ex_id = None
            buy_data = None
            for ex_id, data in market_data.items():
                if data['ask'] < best_buy_price:
                    best_buy_price = data['ask']
                    buy_ex_id = ex_id
                    buy_data = data
            
            best_sell_price = 0
            sell_ex_id = None
            sell_data = None
            for ex_id, data in market_data.items():
                if data['bid'] > best_sell_price:
                    best_sell_price = data['bid']
                    sell_ex_id = ex_id
                    sell_data = data

            if not buy_ex_id or not sell_ex_id or buy_ex_id == sell_ex_id:
                continue

            gross_profit = (best_sell_price - best_buy_price) / best_buy_price
            gross_profit_percentage = gross_profit * 100

            if gross_profit_percentage > MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK:
                logger.warning(f"Lucro bruto irrealista para {pair} ({gross_profit_percentage:.2f}%). Pulando.")
                continue

            # O filtro agora se baseia apenas no lucro bruto
            if gross_profit_percentage >= lucro_minimo:
                required_buy_volume = trade_amount_usd / best_buy_price
                required_sell_volume = trade_amount_usd / best_sell_price

                has_sufficient_liquidity = (
                    buy_data['ask_volume'] >= required_buy_volume and
                    sell_data['bid_volume'] >= required_sell_volume
                )

                if has_sufficient_liquidity:
                    msg = (f"💰 Oportunidade de Arbitragem (Bruta) para {pair}!\n"
                        f"Compre em {buy_ex_id}: {best_buy_price:.8f}\n"
                        f"Venda em {sell_ex_id}: {best_sell_price:.8f}\n"
                        f"Lucro Bruto: {gross_profit_percentage:.2f}%\n"
                        f"Volume de Liquidez: ${trade_amount_usd:.2f}"
                    )
                    logger.info(msg)
                    await bot.send_message(chat_id=chat_id, text=msg)

    except Exception as e:
        logger.error(f"Erro geral na checagem de arbitragem: {e}", exc_info=True)
        if chat_id:
            await bot.send_message(chat_id=chat_id, text=f"Erro crítico na checagem de arbitragem: {e}")
    finally:
        logger.info("Fechando conexões...")
        tasks = [ex.close() for ex in global_exchanges_instances.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Ativado.\n"
        "Monitorando oportunidades de arbitragem de criptomoedas.\n"
        f"Lucro mínimo bruto atual: {context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)}%\n"
        f"Volume de trade para liquidez: ${context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD):.2f}\n"
        "OBS: As taxas de negociação estão sendo ignoradas para diagnóstico.\n\n"
        "Use /setlucro <valor> para definir o lucro mínimo em %.\n"
        "Exemplo: /setlucro 1\n\n"
        "Use /setvolume <valor> para definir o volume de trade em USD para checagem de liquidez.\n"
        "Exemplo: /setvolume 100\n\n"
        "Use /stop para parar de receber alertas."
    )
    logger.info(f"Bot iniciado por chat_id: {update.message.chat_id}")

# As funções setvolume e stop_arbitrage permanecem inalteradas
# A função setfee foi removida, já que as taxas são ignoradas.
async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("O lucro mínimo não pode ser negativo.")
            return
        context.bot_data['lucro_minimo_porcentagem'] = valor
        await update.message.reply_text(f"Lucro mínimo (bruto) atualizado para {valor:.2f}%")
        logger.info(f"Lucro mínimo definido para {valor}% por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setlucro 2.5")

async def setvolume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor <= 0:
            await update.message.reply_text("O volume de trade deve ser um valor positivo.")
            return
        context.bot_data['trade_amount_usd'] = valor
        await update.message.reply_text(f"Volume de trade para checagem de liquidez atualizado para ${valor:.2f} USD")
        logger.info(f"Volume de trade definido para ${valor} por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setvolume 100")

async def stop_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_name = "check_arbitrage"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if not current_jobs:
        await update.message.reply_text("A checagem de arbitragem já está parada.")
        return

    for job in current_jobs:
        job.schedule_removal()
    
    await update.message.reply_text("Checagem de arbitragem parada. Você não receberá mais alertas.")
    logger.info(f"Checagem de arbitragem parada por {update.message.chat_id}")


async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    logger.info("Inicializando exchanges...")
    for ex_id in EXCHANGES_LIST:
        try:
            exchange_class = getattr(ccxt, ex_id)
            global_exchanges_instances[ex_id] = exchange_class({
                'enableRateLimit': True,
                'timeout': 3000,
            })
            logger.info(f"Exchange {ex_id} inicializada.")
        except Exception as e:
            logger.error(f"ERRO CRÍTICO: Não foi possível inicializar a exchange {ex_id}. Ela será ignorada. Erro: {e}")

    if len(global_exchanges_instances) < 2:
        logger.error("ERRO CRÍTICO: Menos de 2 exchanges foram inicializadas com sucesso. O bot não pode operar.")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("stop", stop_arbitrage))

    application.job_queue.run_repeating(check_arbitrage, interval=90, first=5, name="check_arbitrage")

    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot e ver configurações"),
        BotCommand("setlucro", "Definir lucro mínimo bruto em % (Ex: /setlucro 2.5)"),
        BotCommand("setvolume", "Definir volume de trade em USD para liquidez (Ex: /setvolume 100)"),
        BotCommand("stop", "Parar a checagem de arbitragem")
    ])

    logger.info("Bot iniciado com sucesso e aguardando mensagens...")
    try:
        await application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
    finally:
        logger.info("Fechando conexões das exchanges...")
        tasks = [ex.close() for ex in global_exchanges_instances.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())

