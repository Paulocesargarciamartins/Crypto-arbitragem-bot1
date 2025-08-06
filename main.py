import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.pro as ccxt
import os
import nest_asyncio

# Aplica o patch para permitir loops aninhados
nest_asyncio.apply()

# --- Configurações básicas ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0
DEFAULT_FEE_PERCENTAGE = 0.1

# Limite máximo de lucro bruto para validação de dados.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0

# Exchanges confiáveis para monitorar (BITFINEX REMOVIDA)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitget', 'mexc'
]

# Pares USDT - OTIMIZADA para o plano Eco Dynos (50 principais moedas)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "USDT/USDT", "BNB/USDT", "SOL/USDT",
    "USDC/USDT", "TRX/USDT", "DOGE/USDT", "ADA/USDT", "WBTC/USDT", "STETH/USDT",
    "XLM/USDT", "SUI/USDT", "BCH/USDT", "LINK/USDT", "HBAR/USDT", "AVAX/USDT",
    "LTC/USDT", "USDS/USDT", "TON/USDT", "SHIB/USDT", "UNI/USDT", "DOT/USDT",
    "XMR/USDT", "CRO/USDT", "PEPE/USDT", "AAVE/USDT", "ENA/USDT", "DAI/USDT",
    "TAO/USDT", "NEAR/USDT", "ETC/USDT", "MNT/USDT", "ONDO/USDT", "APT/USDT",
    "ICP/USDT", "JITOSOL/USDT", "KAS/USDT", "PENGU/USDT", "ALGO/USDT", "ARB/USDT",
    "POL/USDT", "ATOM/USDT", "BONK/USDT", "WBETH/USDT", "RENDER/USDT", "WLD/USDT",
    "STORY/USDT", "TRUMP/USDT"
]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

global_exchanges_instances = {}
GLOBAL_MARKET_DATA = {pair: {} for pair in PAIRS}
markets_loaded = {}

last_alert_time = {}
ALERT_COOLDOWN = 60

async def handle_websocket_data(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = context.bot_data.get('admin_chat_id')
    if not chat_id:
        return

    try:
        lucro_minimo = context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
        trade_amount_usd = context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
        fee = context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE) / 100.0

        for pair in PAIRS:
            market_data = GLOBAL_MARKET_DATA[pair]
            if len(market_data) < 2:
                continue

            now = asyncio.get_event_loop().time()
            if pair in last_alert_time and now - last_alert_time[pair] < ALERT_COOLDOWN:
                continue

            best_buy_price = float('inf')
            buy_ex_id = None
            buy_data = None
            
            best_sell_price = 0
            sell_ex_id = None
            sell_data = None

            for ex_id, data in market_data.items():
                if data.get('ask') is not None and data['ask'] < best_buy_price:
                    best_buy_price = data['ask']
                    buy_ex_id = ex_id
                    buy_data = data
                
                if data.get('bid') is not None and data['bid'] > best_sell_price:
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

                buy_volume = buy_data.get('ask_volume', 0) if buy_data.get('ask_volume') is not None else 0
                sell_volume = sell_data.get('bid_volume', 0) if sell_data.get('bid_volume') is not None else 0

                has_sufficient_liquidity = (
                    buy_volume >= required_buy_volume and
                    sell_volume >= required_sell_volume
                )

                if has_sufficient_liquidity:
                    msg = (f"💰 Arbitragem para {pair}!\n"
                        f"Compre em {buy_ex_id}: {best_buy_price:.8f}\n"
                        f"Venda em {sell_ex_id}: {best_sell_price:.8f}\n"
                        f"Lucro Líquido: {net_profit_percentage:.2f}%\n"
                        f"Volume: ${trade_amount_usd:.2f}"
                    )
                    logger.info(msg)
                    await bot.send_message(chat_id=chat_id, text=msg)
                    last_alert_time[pair] = now

    except Exception as e:
        logger.error(f"Erro na checagem de arbitragem por WebSocket: {e}", exc_info=True)


async def watch_order_book_for_pair(exchange, pair, ex_id, context):
    try:
        while True:
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
            await handle_websocket_data(context)

    except ccxt.NetworkError as e:
        logger.error(f"Erro de rede no WebSocket para {pair} em {ex_id}: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Erro da exchange no WebSocket para {pair} em {ex_id}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado no WebSocket para {pair} em {ex_id}: {e}")
    finally:
        await exchange.close()


async def watch_all_exchanges(context: ContextTypes.DEFAULT_TYPE):
    tasks = []
    for ex_id in EXCHANGES_LIST:
        exchange_class = getattr(ccxt, ex_id)
        exchange = exchange_class({
            'enableRateLimit': True,
            'timeout': 10000,
        })
        global_exchanges_instances[ex_id] = exchange
        
        try:
            logger.info(f"Carregando mercados para {ex_id}...")
            await exchange.load_markets()
            markets_loaded[ex_id] = True
            logger.info(f"Mercados de {ex_id} carregados. Total de pares: {len(exchange.markets)}")

            for pair in PAIRS:
                if pair in exchange.markets:
                    tasks.append(asyncio.create_task(
                        watch_order_book_for_pair(exchange, pair, ex_id, context)
                    ))
                else:
                    logger.warning(f"Par {pair} não está disponível em {ex_id}. Ignorando...")
        except Exception as e:
            logger.error(f"ERRO ao carregar mercados de {ex_id}: {e}")
    
    logger.info("Iniciando WebSockets para todas as exchanges e pares válidos...")
    await asyncio.gather(*tasks, return_exceptions=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Ativado (Modo WebSocket).\n"
        "Monitorando oportunidades de arbitragem em tempo real.\n"
        f"Lucro mínimo atual: {context.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)}%\n"
        f"Volume de trade para liquidez: ${context.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD):.2f}\n"
        f"Taxa de negociação por lado: {context.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE)}%\n\n"
        "Use /setlucro <valor> para definir o lucro mínimo em %.\n"
        "Exemplo: /setlucro 3\n\n"
        "Use /setvolume <valor> para definir o volume de trade em USD para checagem de liquidez.\n"
        "Exemplo: /setvolume 100\n\n"
        "Use /setfee <valor> para definir a taxa de negociação por lado em %.\n"
        "Exemplo: /setfee 0.075\n\n"
        "Use /stop para parar de receber alertas."
    )
    logger.info(f"Bot iniciado por chat_id: {update.message.chat_id}")

async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("O lucro mínimo não pode ser negativo.")
            return
        context.bot_data['lucro_minimo_porcentagem'] = valor
        await update.message.reply_text(f"Lucro mínimo atualizado para {valor:.2f}%")
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

async def setfee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("A taxa de negociação não pode ser negativa.")
            return
        context.bot_data['fee_percentage'] = valor
        await update.message.reply_text(f"Taxa de negociação por lado atualizada para {valor:.3f}%")
        logger.info(f"Taxa de negociação definida para {valor}% por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setfee 0.075")

async def stop_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Modo WebSocket: O bot continuará a checar, mas não enviará mais alertas. Reinicie o bot para voltar a receber alertas.")
    logger.info(f"Alertas de arbitragem desativados por {update.message.chat_id}")

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    asyncio.create_task(watch_all_exchanges(application))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("setfee", setfee))
    application.add_handler(CommandHandler("stop", stop_arbitrage))
    
    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot e ver configurações"),
        BotCommand("setlucro", "Definir lucro mínimo em % (Ex: /setlucro 2.5)"),
        BotCommand("setvolume", "Definir volume de trade em USD para liquidez (Ex: /setvolume 100)"),
        BotCommand("setfee", "Definir taxa de negociação por lado em % (Ex: /setfee 0.075)"),
        BotCommand("stop", "Parar de receber alertas (modo WebSocket)")
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
