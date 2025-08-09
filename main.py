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

# Intervalo de tempo entre cada busca (polling) em segundos
POLLING_INTERVAL_SECONDS = 5

# Lista de exchanges confiáveis.
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitget', 'huobi', 'gateio'
]

# Todas as 10 exchanges são de alta prioridade para os pares selecionados
HIGH_PRIORITY_EXCHANGES = EXCHANGES_LIST
LOW_PRIORITY_EXCHANGES = []

# Lista de 160 pares de moedas, ordenados por capitalização de mercado e sem duplicatas
ALL_PAIRS_WITH_DUPLICATES = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT",
    "TON/USDT", "ADA/USDT", "TRX/USDT", "SHIB/USDT", "AVAX/USDT", "DOT/USDT",
    "BCH/USDT", "LINK/USDT", "LTC/USDT", "MATIC/USDT", "UNI/USDT", "ETC/USDT",
    "WIF/USDT", "NEAR/USDT", "ICP/USDT", "PEPE/USDT", "SEI/USDT", "XLM/USDT",
    "APT/USDT", "IMX/USDT", "GRT/USDT", "ATOM/USDT", "AAVE/USDT", "JUP/USDT",
    "ARB/USDT", "MNT/USDT", "FIL/USDT", "OP/USDT", "STX/USDT", "FTM/USDT",
    "THETA/USDT", "INJ/USDT", "MKR/USDT", "CHZ/USDT", "SAND/USDT", "AXS/USDT",
    "TIA/USDT", "ENJ/USDT", "LDO/USDT", "MANA/USDT", "GALA/USDT", "COMP/USDT",
    "PYTH/USDT", "EOS/USDT", "SNX/USDT", "KAS/USDT", "CRV/USDT", "WLD/USDT",
    "FET/USDT", "ZEC/USDT", "QNT/USDT", "XMR/USDT", "ALGO/USDT", "RUNE/USDT",
    "BAT/USDT", "OMG/USDT", "KSM/USDT", "EGLD/USDT", "ZIL/USDT", "OCEAN/USDT",
    "LRC/USDT", "KAVA/USDT", "WAVES/USDT", "GNO/USDT", "PAXG/USDT", "SC/USDT",
    "VET/USDT", "XVG/USDT", "XTZ/USDT", "ZRX/USDT", "BAL/USDT", "C98/USDT",
    "LINA/USDT", "IOST/USDT", "ONE/USDT", "CELR/USDT", "PHA/USDT", "ALPHA/USDT",
    "SFP/USDT", "TOMO/USDT", "IRIS/USDT", "CTK/USDT", "REEF/USDT", "DGB/USDT",
    "AR/USDT", "HNT/USDT", "CHR/USDT", "OGN/USDT", "RLY/USDT", "MASK/USDT",
    "AUDIO/USDT", "FIS/USDT", "LPT/USDT", "NKN/USDT", "ANKR/USDT", "DENT/USDT",
    "BADGER/USDT", "BOND/USDT", "DODO/USDT", "FIO/USDT", "FORTH/USDT", "LUNA/USDT",
    "JASMY/USDT", "MDX/USDT", "SCRT/USDT", "SKL/USDT", "UMA/USDT", "VITE/USDT",
    "YGG/USDT", "ALICE/USDT", "BICO/USDT", "CITY/USDT", "ILV/USDT", "PYR/USDT",
    "SLP/USDT", "WTC/USDT", "CVC/USDT", "SUSHI/USDT", "1INCH/USDT", "YFI/USDT",
    "KNC/USDT", "BAND/USDT", "RLC/USDT", "DASH/USDT", "DCR/USDT", "ZRX/USDT",
    "BTT/USDT", "VTC/USDT", "FLOKI/USDT", "BONK/USDT", "FLUX/USDT", "CELO/USDT",
    "AR/USDT", "STG/USDT", "AGIX/USDT", "FXS/USDT", "DYDX/USDT", "MINA/USDT",
    "GMX/USDT", "TUSD/USDT", "USDP/USDT", "PAXG/USDT", "USDC/USDT", "USDS/USDT",
    "CFX/USDT", "SUI/USDT", "ASTR/USDT", "ROSE/USDT", "MOVR/USDT", "AKT/USDT",
    "WOO/USDT", "CSPR/USDT", "NMR/USDT", "GTC/USDT", "HBAR/USDT", "CELO/USDT",
    "AIOZ/USDT", "CTSI/USDT", "TFUEL/USDT"
]

ALL_PAIRS = list(dict.fromkeys(ALL_PAIRS_WITH_DUPLICATES))

# 10 pares de alta prioridade para o teste
HIGH_PRIORITY_PAIRS = ALL_PAIRS[:10]
LOW_PRIORITY_PAIRS = ALL_PAIRS[10:]

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

global_exchanges_instances = {}
GLOBAL_MARKET_DATA = {pair: {} for pair in ALL_PAIRS}
markets_loaded = {}


async def fetch_market_data_for_low_priority_pairs():
    """
    Busca dados para pares de baixa prioridade via polling (REST API).
    """
    while True:
        try:
            fetch_tasks = []
            for ex_id in EXCHANGES_LIST:
                exchange = global_exchanges_instances.get(ex_id)
                if not exchange or not markets_loaded.get(ex_id):
                    continue
                
                # Para exchanges de alta prioridade, buscamos os de baixa prioridade
                # para completar os dados.
                pairs_to_fetch = [pair for pair in LOW_PRIORITY_PAIRS if pair in exchange.markets]

                if pairs_to_fetch:
                    fetch_tasks.append(
                        asyncio.create_task(
                            fetch_tickers_safe(exchange, ex_id, pairs_to_fetch)
                        )
                    )
            
            await asyncio.gather(*fetch_tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Erro no loop de busca de dados de baixa prioridade: {e}", exc_info=True)
        
        await asyncio.sleep(POLLING_INTERVAL_SECONDS)


async def fetch_tickers_safe(exchange, ex_id, pairs_to_fetch):
    """
    Busca tickers de forma segura para evitar erros.
    """
    try:
        tickers = await exchange.fetch_tickers(pairs_to_fetch)
        for pair in pairs_to_fetch:
            ticker = tickers.get(pair)
            if ticker and ticker.get('bid') is not None and ticker.get('ask') is not None:
                GLOBAL_MARKET_DATA[pair][ex_id] = {
                    'bid': ticker.get('bid'),
                    'bid_volume': ticker.get('bidVolume'),
                    'ask': ticker.get('ask'),
                    'ask_volume': ticker.get('askVolume')
                }
    except Exception as e:
        logger.error(f"Erro ao buscar tickers de {ex_id}: {e}")

async def check_arbitrage_opportunities(application):
    """
    Checa oportunidades de arbitragem em loop.
    """
    bot = application.bot
    while True:
        try:
            chat_id = application.bot_data.get('admin_chat_id')
            if not chat_id:
                await asyncio.sleep(5)
                continue

            lucro_minimo = application.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
            trade_amount_usd = application.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
            
            for pair in ALL_PAIRS:
                market_data = GLOBAL_MARKET_DATA.get(pair, {})
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

                net_profit_percentage = gross_profit_percentage - (2 * DEFAULT_FEE_PERCENTAGE)
                
                if net_profit_percentage >= lucro_minimo:
                    required_buy_volume = trade_amount_usd / best_buy_price
                    required_sell_volume = trade_amount_usd / best_sell_price

                    buy_volume = buy_data.get('ask_volume', 0) if buy_data else 0
                    sell_volume = sell_data.get('bid_volume', 0) if sell_data else 0

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

        except Exception as e:
            logger.error(f"Erro na checagem de arbitragem: {e}", exc_info=True)
        
        await asyncio.sleep(1)


async def watch_order_book_for_pair(exchange, pair, ex_id):
    """
    Função que atualiza os dados de mercado com reconexão automática.
    """
    reconnect_delay = 1
    max_reconnect_delay = 60

    while True:
        try:
            order_book = await exchange.watch_order_book(pair)
            
            best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
            best_bid_volume = order_book['bids'][0][1] if order_book['bids'] else 0
            best_ask = order_book['asks'][0][0] if order_book['asks'] else float('inf')
            best_ask_volume = order_book['asks'][0][1] if order_book['asks'] else 0

            if best_bid > 0 and best_ask > 0:
                GLOBAL_MARKET_DATA[pair][ex_id] = {
                    'bid': best_bid,
                    'bid_volume': best_bid_volume,
                    'ask': best_ask,
                    'ask_volume': best_ask_volume
                }
            reconnect_delay = 1

        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Erro no WebSocket para {pair} em {ex_id}: {e}. Tentando reconectar em {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            
        except Exception as e:
            logger.error(f"Erro inesperado no WebSocket para {pair} em {ex_id}: {e}. Tentando reconectar em {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


async def setup_exchanges():
    """
    Prepara as exchanges para uso, carregando os mercados.
    """
    tasks = []
    for ex_id in EXCHANGES_LIST:
        try:
            exchange_class = getattr(ccxt, ex_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 10000,
            })
            global_exchanges_instances[ex_id] = exchange
            
            tasks.append(asyncio.create_task(exchange.load_markets()))
            
        except Exception as e:
            logger.error(f"ERRO ao instanciar ou carregar mercados de {ex_id}: {e}")
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    for ex_id, exchange in global_exchanges_instances.items():
        if exchange.markets:
            markets_loaded[ex_id] = True


async def start_monitoring_tasks():
    """
    Inicia as tarefas de monitoramento para ambos os grupos.
    """
    tasks = []
    for ex_id in HIGH_PRIORITY_EXCHANGES:
        exchange = global_exchanges_instances.get(ex_id)
        if not exchange or not markets_loaded.get(ex_id):
            continue
        
        for pair in HIGH_PRIORITY_PAIRS:
            if pair in exchange.markets:
                tasks.append(asyncio.create_task(
                    watch_order_book_for_pair(exchange, pair, ex_id)
                ))
            else:
                logger.warning(f"Par {pair} não disponível em {ex_id}. Ignorando na alta prioridade...")

    logger.info("Iniciando monitoramento híbrido (WebSockets + Polling)...")
    await asyncio.gather(*tasks)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['admin_chat_id'] = update.message.chat_id
    await update.message.reply_text(
        "Olá! Bot de Arbitragem Híbrido Ativado.\n"
        "Monitorando 10 pares em tempo real (WebSockets) nas 10 exchanges.\n"
        f"e os {len(LOW_PRIORITY_PAIRS)} pares restantes por polling (a cada 5s).\n"
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
    context.bot_data['admin_chat_id'] = None
    await update.message.reply_text("Alertas desativados. Use /start para reativar.")
    logger.info(f"Alertas de arbitragem desativados por {update.message.chat_id}")

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("setlucro", setlucro))
    application.add_handler(CommandHandler("setvolume", setvolume))
    application.add_handler(CommandHandler("setfee", setfee))
    application.add_handler(CommandHandler("stop", stop_arbitrage))
    
    await application.bot.set_my_commands([
        BotCommand("start", "Iniciar o bot e ver configurações"),
        BotCommand("setlucro", "Definir lucro mínimo em % (Ex: /setlucro 2.5)"),
        BotCommand("setvolume", "Definir volume de trade em USD para liquidez (Ex: /setvolume 100)"),
        BotCommand("setfee", "Definir taxa de negociação por lado em % (Ex: /setfee 0.075)"),
        BotCommand("stop", "Parar de receber alertas")
    ])

    logger.info("Bot iniciado com sucesso e aguardando mensagens...")

    try:
        await setup_exchanges()
        
        asyncio.create_task(fetch_market_data_for_low_priority_pairs())
        asyncio.create_task(check_arbitrage_opportunities(application))
        asyncio.create_task(start_monitoring_tasks())
        
        await application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

    except Exception as e:
        logger.error(f"Erro no loop principal do bot: {e}", exc_info=True)
    finally:
        logger.info("Fechando conexões das exchanges...")
        tasks = [ex.close() for ex in global_exchanges_instances.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
