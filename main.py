import asyncio
import logging
import os
from telegram import Update, BotCommand, Bot
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
    'bitfinex', 'gate', 'bitstamp', 'crypto_com', 'huobi', 'mexc', 'bitget'
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
global_exchanges_instances = {}
GLOBAL_MARKET_DATA = {pair: {} for pair in PAIRS}
markets_loaded = {}
GLOBAL_MARKET_DATA_LOCK = asyncio.Lock()

# Telegram bot
bot = None


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

    # Cria e agenda a tarefa de verificação de arbitragem
    app.add_startup_tasks(check_arbitrage_opportunities(app))

    # Cria e agenda as tarefas para todos os WebSockets
    for ex_id in EXCHANGES_LIST:
        for pair in PAIRS:
            app.add_startup_tasks(
                watch_order_book_for_pair_robust(None, pair, ex_id)
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
