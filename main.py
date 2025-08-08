import asyncio
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.pro as ccxt
import nest_asyncio

nest_asyncio.apply()

# Configuração básica de logging (warnings e errors)
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Configurações
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0
DEFAULT_FEE_PERCENTAGE = 0.1
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0

# Exchanges confiáveis (13)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'kucoin', 'okx', 'bybit',
    'bitfinex', 'gate', 'bitstamp', 'cryptocom', 'huobi', 'mexc', 'bitget'
]

# Lista fixa das 100 moedas principais (você pode ajustar)
PAIRS_BASE = [
    "BTC", "ETH", "USDT", "BNB", "XRP", "ADA", "SOL", "DOT", "DOGE", "AVAX",
    "SHIB", "LTC", "TRX", "UNI", "MATIC", "ATOM", "LINK", "ETC", "XLM", "ALGO",
    "VET", "FIL", "ICP", "HBAR", "EGLD", "AAVE", "THETA", "MKR", "XTZ", "CAKE",
    "EOS", "FTT", "GRT", "KSM", "SAND", "CHZ", "NEAR", "ZIL", "CRO", "DASH",
    "ENJ", "ZRX", "COMP", "LRC", "BAT", "1INCH", "CEL", "FTM", "GLM", "WAVES",
    "MANA", "YFI", "SNX", "KNC", "REN", "CRV", "BNT", "RSR", "SUSHI", "SRM",
    "NANO", "ZEC", "CELO", "STX", "IOTA", "QTUM", "ANKR", "BAL", "OCEAN", "HNT",
    "DCR", "OMG", "LUNA", "XEM", "ICX", "KAVA", "NKN", "BTG", "SRM", "WBTC",
    "AR", "HOT", "BAND", "ZEN", "IOST", "XVG", "HUSD", "XDC", "GNO", "BTT",
    "STMX", "ANKR", "CVC", "CHSB", "MATIC"
]

# Criar pares completos: ex: BTC/USDT, ETH/USDT
PAIRS = [f"{coin}/USDT" for coin in PAIRS_BASE]

# Variáveis globais
GLOBAL_MARKET_DATA = {pair: {} for pair in PAIRS}
GLOBAL_MARKET_DATA_LOCK = asyncio.Lock()

# --- FUNÇÕES DE HANDLER DO TELEGRAM ---

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
    logger.warning(f"Bot iniciado por chat_id: {update.message.chat_id}")


async def setlucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0])
        if valor < 0:
            await update.message.reply_text("O lucro mínimo não pode ser negativo.")
            return
        context.bot_data['lucro_minimo_porcentagem'] = valor
        await update.message.reply_text(f"Lucro mínimo atualizado para {valor:.2f}%")
        logger.warning(f"Lucro mínimo definido para {valor}% por {update.message.chat_id}")
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
        logger.warning(f"Volume de trade definido para ${valor} por {update.message.chat_id}")
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
        logger.warning(f"Taxa de negociação definida para {valor}% por {update.message.chat_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Exemplo: /setfee 0.075")


async def stop_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = None
    await update.message.reply_text("Alertas desativados. Use /start para reativar.")
    logger.warning(f"Alertas de arbitragem desativados por {update.message.chat_id}")

# --- FUNÇÕES DE LÓGICA DO BOT ---

async def check_arbitrage_opportunities(application):
    bot = application.bot
    while True:
        try:
            chat_id = application.bot_data.get('admin_chat_id')
            if not chat_id:
                await asyncio.sleep(5)
                continue

            lucro_minimo = application.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
            trade_amount_usd = application.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
            fee = application.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE) / 100.0

            async with GLOBAL_MARKET_DATA_LOCK:
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

                        buy_volume = buy_data.get('ask_volume', 0) or 0
                        sell_volume = sell_data.get('bid_volume', 0) or 0

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
                            try:
                                await bot.send_message(chat_id=chat_id, text=msg)
                                logger.warning(f"Alerta enviado: {msg.replace(chr(10), ' | ')}")
                            except Exception as e:
                                logger.error(f"Erro ao enviar mensagem Telegram: {e}")
                    else:
                        # lucro abaixo do mínimo, não logar para evitar muito log
                        pass
        except Exception as e:
            logger.error(f"Erro na checagem de arbitragem: {e}", exc_info=True)
        
        # Reduzindo a latência para 0.1 segundos para reagir mais rápido
        await asyncio.sleep(0.1)


async def watch_order_book_for_pair_robust(exchange, pair, ex_id):
    while True:
        try:
            exchange_class = getattr(ccxt, ex_id)
            exchange_instance = exchange_class({
                'enableRateLimit': True,
                'timeout': 10000,
            })
            await exchange_instance.load_markets()
            if pair not in exchange_instance.markets:
                logger.warning(f"Par {pair} não disponível em {ex_id}. Ignorando...")
                return

            logger.warning(f"Iniciando WebSocket para {pair} em {ex_id}...")
            while True:
                order_book = await exchange_instance.watch_order_book(pair)
                
                best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
                best_bid_volume = order_book['bids'][0][1] if order_book['bids'] else 0
                best_ask = order_book['asks'][0][0] if order_book['asks'] else float('inf')
                best_ask_volume = order_book['asks'][0][1] if order_book['asks'] else 0

                async with GLOBAL_MARKET_DATA_LOCK:
                    if pair not in GLOBAL_MARKET_DATA:
                        GLOBAL_MARKET_DATA[pair] = {}
                    GLOBAL_MARKET_DATA[pair][ex_id] = {
                        'bid': best_bid,
                        'bid_volume': best_bid_volume,
                        'ask': best_ask,
                        'ask_volume': best_ask_volume
                    }
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.warning(f"Erro no WebSocket {ex_id} {pair}: {e}. Tentando reconectar em 30 segundos...")
            # Limpa os dados antigos para evitar alertas com dados desatualizados
            async with GLOBAL_MARKET_DATA_LOCK:
                if pair in GLOBAL_MARKET_DATA and ex_id in GLOBAL_MARKET_DATA[pair]:
                    del GLOBAL_MARKET_DATA[pair][ex_id]
            await asyncio.sleep(30) # Espera antes de tentar novamente
        except Exception as e:
            logger.error(f"Erro inesperado no WebSocket {ex_id} {pair}: {e}. Tentando reconectar em 30 segundos...")
            await asyncio.sleep(30)
        finally:
            if 'exchange_instance' in locals() and hasattr(exchange_instance, 'close') and callable(exchange_instance.close):
                try:
                    await exchange_instance.close()
                except Exception as close_error:
                    logger.error(f"Erro ao fechar conexão com {ex_id}: {close_error}")


async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlucro", setlucro))
    app.add_handler(CommandHandler("setvolume", setvolume))
    app.add_handler(CommandHandler("setfee", setfee))
    app.add_handler(CommandHandler("stop", stop_arbitrage))

    # Cria e agenda a tarefa de verificação de arbitragem usando run_once
    app.job_queue.run_once(
        lambda context: asyncio.create_task(check_arbitrage_opportunities(app)),
        0
    )

    # Cria e agenda as tarefas para todos os WebSockets
    for ex_id in EXCHANGES_LIST:
        for pair in PAIRS:
            app.job_queue.run_once(
                lambda context, ex_id=ex_id, pair=pair: asyncio.create_task(
                    watch_order_book_for_pair_robust(None, pair, ex_id)
                ),
                0
            )

    logger.warning("Iniciando o bot de Telegram...")
    await app.run_polling()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Bot desligado manualmente.")
    except Exception as e:
        logger.error(f"Erro fatal no loop principal: {e}", exc_info=True)
