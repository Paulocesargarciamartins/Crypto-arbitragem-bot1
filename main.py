import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.pro as ccxt
import os
import nest_asyncio

nest_asyncio.apply()

# Token do Bot (via variável de ambiente)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("A variável de ambiente TELEGRAM_BOT_TOKEN não está definida.")

DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0
DEFAULT_FEE_PERCENTAGE = 0.1
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0

# Exchanges confiáveis (13 principais com suporte a WebSocket)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit', 'kucoin',
    'bitstamp', 'bitget', 'mexc', 'gateio', 'bitfinex', 'huobi', 'poloniex'
]

# 100 principais moedas pareadas com USDT
PAIRS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
    "TON/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT", "LINK/USDT", "MATIC/USDT", "BCH/USDT",
    "TRX/USDT", "LTC/USDT", "ICP/USDT", "DAI/USDT", "UNI/USDT", "ETC/USDT", "XLM/USDT",
    "APT/USDT", "NEAR/USDT", "INJ/USDT", "FIL/USDT", "STX/USDT", "LDO/USDT", "IMX/USDT",
    "HBAR/USDT", "VET/USDT", "RUNE/USDT", "MKR/USDT", "RNDR/USDT", "AR/USDT", "SUI/USDT",
    "ALGO/USDT", "QNT/USDT", "EGLD/USDT", "FTM/USDT", "FLOW/USDT", "THETA/USDT", "GRT/USDT",
    "AAVE/USDT", "AXS/USDT", "KAVA/USDT", "CFX/USDT", "KLAY/USDT", "ZEC/USDT", "ROSE/USDT",
    "BAT/USDT", "ENJ/USDT", "ONE/USDT", "RVN/USDT", "XEM/USDT", "SCRT/USDT", "WAVES/USDT",
    "IOTA/USDT", "ZIL/USDT", "CVC/USDT", "OMG/USDT", "COMP/USDT", "ANKR/USDT", "LRC/USDT",
    "YFI/USDT", "CHZ/USDT", "SAND/USDT", "GALA/USDT", "CRV/USDT", "ENS/USDT", "DYDX/USDT",
    "OP/USDT", "ARB/USDT", "PEPE/USDT", "WLD/USDT", "FET/USDT", "TOMO/USDT", "CELR/USDT",
    "BEL/USDT", "ZEN/USDT", "PYR/USDT", "RLC/USDT", "CKB/USDT", "LUNC/USDT", "KSM/USDT",
    "JASMY/USDT", "MASK/USDT", "SKL/USDT", "BAND/USDT", "NKN/USDT", "XNO/USDT", "ACA/USDT",
    "MINA/USDT", "STG/USDT", "GMT/USDT", "GAL/USDT", "NMR/USDT", "SPELL/USDT", "RAD/USDT",
    "ACH/USDT", "ID/USDT", "BICO/USDT", "ASTR/USDT"
]

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

global_exchanges_instances = {}
GLOBAL_MARKET_DATA = {pair: {} for pair in PAIRS}
markets_loaded = {}
last_alerts = {}

async def check_arbitrage_opportunities(application):
    bot = application.bot
    while True:
        try:
            chat_id = application.bot_data.get('admin_chat_id')
            if not chat_id:
                logger.warning("Nenhum chat_id de administrador definido.")
                await asyncio.sleep(5)
                continue

            logger.info("Checando oportunidades de arbitragem...")

            lucro_minimo = application.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
            trade_amount_usd = application.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
            fee = application.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE) / 100.0

            for pair in PAIRS:
                market_data = GLOBAL_MARKET_DATA[pair]
                if len(market_data) < 2:
                    continue

                best_buy_price = float('inf')
                buy_ex_id = None
                buy_data = None

                best_sell_price = 0
                sell_ex_id = None
                sell_data = None

                for ex_id, data in market_data.items():
                    if data.get('ask') and data['ask'] < best_buy_price:
                        best_buy_price = data['ask']
                        buy_ex_id = ex_id
                        buy_data = data
                    if data.get('bid') and data['bid'] > best_sell_price:
                        best_sell_price = data['bid']
                        sell_ex_id = ex_id
                        sell_data = data

                if not buy_ex_id or not sell_ex_id or buy_ex_id == sell_ex_id:
                    continue

                gross_profit = (best_sell_price - best_buy_price) / best_buy_price
                gross_profit_percentage = gross_profit * 100

                if gross_profit_percentage > MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK:
                    continue

                net_profit_percentage = gross_profit_percentage - (2 * fee * 100)

                if net_profit_percentage >= lucro_minimo:
                    required_buy_volume = trade_amount_usd / best_buy_price
                    required_sell_volume = trade_amount_usd / best_sell_price

                    buy_volume = buy_data.get('ask_volume', 0)
                    sell_volume = sell_data.get('bid_volume', 0)

                    has_liquidity = buy_volume >= required_buy_volume and sell_volume >= required_sell_volume

                    key = f"{pair}_{buy_ex_id}_{sell_ex_id}"
                    now = asyncio.get_event_loop().time()
                    if key in last_alerts and now - last_alerts[key] < 60:
                        continue
                    last_alerts[key] = now

                    if has_liquidity:
                        msg = (
                            f"💰 Arbitragem para {pair}!\n"
                            f"Compre em {buy_ex_id}: {best_buy_price:.8f}\n"
                            f"Venda em {sell_ex_id}: {best_sell_price:.8f}\n"
                            f"Lucro Líquido: {net_profit_percentage:.2f}%\n"
                            f"Volume: ${trade_amount_usd:.2f}"
                        )
                        await bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            logger.error(f"Erro na checagem de arbitragem: {e}", exc_info=True)
        await asyncio.sleep(5)

async def watch_order_book_for_pair(exchange, pair, ex_id):
    while True:
        try:
            order_book = await exchange.watch_order_book(pair)
            best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
            best_bid_volume = order_book['bids'][0][1] if order_book['bids'] else 0
            best_ask = order_book['asks'][0][0] if order_book['asks'] else float('inf')
            best_ask_volume = order_book['asks'][0][1] if order_book['asks'] else 0

            GLOBAL_MARKET_DATA[pair][ex_id] = {
                'bid': best_bid,
                'bid_volume': best_bid_volume,
                'ask': best_ask,
                'ask_volume': best_ask_volume
            }
        except Exception as e:
            logger.error(f"Erro WebSocket {pair} @ {ex_id}: {e}")
            await asyncio.sleep(10)

async def watch_all_exchanges():
    tasks = []
    for ex_id in EXCHANGES_LIST:
        exchange_class = getattr(ccxt, ex_id)
        exchange = exchange_class({'enableRateLimit': True, 'timeout': 10000})
        global_exchanges_instances[ex_id] = exchange

        try:
            logger.info(f"Carregando mercados: {ex_id}")
            await exchange.load_markets()
            markets_loaded[ex_id] = True

            for pair in PAIRS:
                if pair in exchange.markets:
                    tasks.append(asyncio.create_task(watch_order_book_for_pair(exchange, pair, ex_id)))
                else:
                    logger.warning(f"{pair} não disponível em {ex_id}")
        except Exception as e:
            logger.error(f"Erro ao carregar {ex_id}: {e}")
    await asyncio.gather(*tasks, return_exceptions=True)

# --- Comandos Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text(
        "🔔 Bot de Arbitragem Ativado!\n"
        f"Lucro mínimo: {context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)}%\n"
        f"Volume: ${context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)}\n"
        f"Taxa: {context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE)}%\n\n"
        "Use /setlucro, /setvolume, /setfee ou /stop."
    )

async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        context.bot_data['lucro_minimo_porcentagem'] = valor
        await update.message.reply_text(f"Lucro mínimo definido: {valor:.2f}%")
    except:
        await update.message.reply_text("Uso: /setlucro 2.5")

async def setvolume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        context.bot_data['trade_amount_usd'] = valor
        await update.message.reply_text(f"Volume definido: ${valor:.2f}")
    except:
        await update.message.reply_text("Uso: /setvolume 100")

async def setfee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        context.bot_data['fee_percentage'] = valor
        await update.message.reply_text(f"Taxa definida: {valor:.3f}%")
    except:
        await update.message.reply_text("Uso: /setfee 0.075")

async def stop_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = None
    await update.message.reply_text("🔕 Alertas desativados.")

# --- Main ---
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("setfee", setfee))
    application.add_handler(CommandHandler("stop", stop_arbitrage))

    await application.bot.set_my_commands([
        BotCommand("start", "Ativar bot"),
        BotCommand("setlucro", "Definir lucro mínimo (%)"),
        BotCommand("setvolume", "Definir volume em USD"),
        BotCommand("setfee", "Definir taxa por lado (%)"),
        BotCommand("stop", "Parar alertas"),
    ])

    logger.info("Iniciando WebSockets e monitoramento...")
    asyncio.create_task(watch_all_exchanges())
    asyncio.create_task(check_arbitrage_opportunities(application))

    await application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
