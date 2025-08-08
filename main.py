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

# Exchanges confiáveis para monitorar (13)
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitget', 'mexc', 'gateio',
    'huobi', 'lbank', 'crypto_com'
]

# Pares USDT - OTIMIZADA para o plano Eco Dynos (100 principais moedas)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "USDT/USDT", "BNB/USDT", "SOL/USDT", "USDC/USDT", "TRX/USDT", "DOGE/USDT", "ADA/USDT",
    "WBTC/USDT", "STETH/USDT", "XLM/USDT", "SUI/USDT", "BCH/USDT", "LINK/USDT", "HBAR/USDT", "AVAX/USDT", "LTC/USDT", "USDS/USDT",
    "TON/USDT", "SHIB/USDT", "UNI/USDT", "DOT/USDT", "XMR/USDT", "CRO/USDT", "PEPE/USDT", "AAVE/USDT", "ENA/USDT", "DAI/USDT",
    "TAO/USDT", "NEAR/USDT", "ETC/USDT", "MNT/USDT", "ONDO/USDT", "APT/USDT", "ICP/USDT", "JITOSOL/USDT", "KAS/USDT", "PENGU/USDT",
    "ALGO/USDT", "ARB/USDT", "POL/USDT", "ATOM/USDT", "BONK/USDT", "WBETH/USDT", "RENDER/USDT", "WLD/USDT", "STORY/USDT", "TRUMP/USDT",
    "SEI/USDT", "IMX/USDT", "STRK/USDT", "OP/USDT", "FIL/USDT", "TIA/USDT", "VET/USDT", "MINA/USDT", "FET/USDT", "INJ/USDT",
    "GRT/USDT", "FTM/USDT", "RNDR/USDT", "AXS/USDT", "EOS/USDT", "MANA/USDT", "SAND/USDT", "QNT/USDT", "GALA/USDT", "EGLD/USDT",
    "WIF/USDT", "THETA/USDT", "FLOW/USDT", "LDO/USDT", "BTT/USDT", "GNO/USDT", "KSM/USDT", "DYDX/USDT", "WEMIX/USDT", "TUSD/USDT",
    "CELO/USDT", "ENS/USDT", "ZEC/USDT", "CHZ/USDT", "SUSHI/USDT", "MKR/USDT", "IOTA/USDT", "STX/USDT", "FXS/USDT", "BUSD/USDT",
    "FLOKI/USDT", "PYTH/USDT", "XAI/USDT", "AGIX/USDT", "OCEAN/USDT", "BONE/USDT", "CFX/USDT", "SATS/USDT", "NMR/USDT", "RPL/USDT"
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


async def check_arbitrage_opportunities(application):
    """
    Função que checa oportunidades de arbitragem em loop.
    """
    bot = application.bot
    while True:
        try:
            chat_id = application.bot_data.get('admin_chat_id')
            if not chat_id:
                logger.warning("Nenhum chat_id de administrador definido. O bot não enviará alertas.")
                await asyncio.sleep(5)
                continue

            logger.info("Executando checagem de arbitragem...")

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
                else:
                    logger.debug(f"Oportunidade para {pair}: Lucro Líquido {net_profit_percentage:.2f}% (abaixo do mínimo de {lucro_minimo:.2f}%)")

        except Exception as e:
            logger.error(f"Erro na checagem de arbitragem: {e}", exc_info=True)
        
        await asyncio.sleep(5)


async def watch_order_book_for_pair(exchange, pair, ex_id):
    """
    Função que apenas atualiza os dados de mercado.
    """
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
    except ccxt.NetworkError as e:
        logger.error(f"Erro de rede no WebSocket para {pair} em {ex_id}: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Erro da exchange no WebSocket para {pair} em {ex_id}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado no WebSocket para {pair} em {ex_id}: {e}")
    finally:
        await exchange.close()


async def watch_all_exchanges():
    tasks = []
    for ex_id in EXCHANGES_LIST:
        exchange_class = getattr(ccxt, ex_id)
        exchange = exchange_class({
            'enableRateLimit': True,
