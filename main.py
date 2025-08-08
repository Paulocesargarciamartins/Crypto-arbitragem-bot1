import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.pro as ccxt
import os
import nest_asyncio
from typing import Dict

nest_asyncio.apply()

# --- Configurações básicas ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_LUCRO_MINIMO_PORCENTAGEM = 2.0
DEFAULT_TRADE_AMOUNT_USD = 50.0
DEFAULT_FEE_PERCENTAGE = 0.1

# Limite máximo de lucro bruto para validação de dados.
MAX_GROSS_PROFIT_PERCENTAGE_SANITY_CHECK = 100.0

# Exchanges confiáveis para monitorar
EXCHANGES_LIST = [
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'kucoin', 'bitstamp', 'bitget', 'mexc'
]

# Pares USDT (sua lista)
PAIRS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "USDT/USDT", "BNB/USDT", "SOL/USDT",
    "USDC/USDT", "TRX/USDT", "DOGE/USDT", "ADA/USDT", "WBTC/USDT", "STETH/USDT",
    "XLM/USDT", "SUI/USDT", "BCH/USDT", "LINK/USDT", "HBAR/USDT", "AVAX/USDT",
    "LTC/USDT", "USDS/USDT", "TON/USDT", "SHIB/USDT", "UNI/USDT", "DOT/USDT",
    "XMR/USDT", "CRO/USDT", "PEPE/USDT", "AAVE/USDT", "ENA/USDT", "DAI/USDT",
    "TAO/USDT", "NEAR/USDT", "ETC/USDT", "MNT/USDT", "ONDO/USDT", "APT/USDT",
    "ICP/USDT", "JITOSOL/USDT", "KAS/USDT", "PENGU/USDT", "ALGO/USDT", "ARB/USDT",
    "POL/USDT", "ATOM/USDT", "BONK/USDT", "WBETH/USDT", "RENDER/USDT", "WLD/USDT",
    "STORY/USDT", "TRUMP/USDT", "MATIC/USDT", "OP/USDT", "IMX/USDT", "TIA/USDT",
    "INJ/USDT", "PYTH/USDT", "STRK/USDT", "MANTLE/USDT", "WIF/USDT", "JUP/USDT",
    "FET/USDT", "STX/USDT", "GRT/USDT", "LDO/USDT", "FLOW/USDT", "FTM/USDT",
    "SAND/USDT", "MANA/USDT", "GALA/USDT", "AXS/USDT", "ENJ/USDT", "CHZ/USDT",
    "THETA/USDT", "EOS/USDT", "MKR/USDT", "CRV/USDT", "BAT/USDT", "COMP/USDT",
    "SUSHI/USDT", "1INCH/USDT", "YFI/USDT", "KNC/USDT", "BAND/USDT", "RLC/USDT"
]

# logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Globals
global_exchanges_instances: Dict[str, ccxt.Exchange] = {}   # atualizado pelo exchange_manager
GLOBAL_MARKET_DATA: Dict[str, Dict[str, dict]] = {pair: {} for pair in PAIRS}
markets_loaded = {}

# --- Função que checa oportunidades (mantive sua lógica) ---
async def check_arbitrage_opportunities(application):
    bot = application.bot
    while True:
        try:
            chat_id = application.bot_data.get('admin_chat_id')
            if not chat_id:
                logger.warning("Nenhum chat_id de administrador definido. O bot não enviará alertas.")
                await asyncio.sleep(5)
                continue

            lucro_minimo = application.bot_data.get('lucro_minimo_porcentagem', DEFAULT_LUCRO_MINIMO_PORCENTAGEM)
            trade_amount_usd = application.bot_data.get('trade_amount_usd', DEFAULT_TRADE_AMOUNT_USD)
            fee = application.bot_data.get('fee_percentage', DEFAULT_FEE_PERCENTAGE) / 100.0

            logger.info("Executando checagem de arbitragem...")

            for pair in PAIRS:
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
                    if data is None:
                        continue
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

                # cálculo de lucros
                try:
                    gross_profit = (best_sell_price - best_buy_price) / best_buy_price
                except Exception:
                    continue
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
                               f"Volume: ${trade_amount_usd:.2f}")
                        logger.info(msg)
                        await bot.send_message(chat_id=chat_id, text=msg)

        except Exception as e:
            logger.error(f"Erro na checagem de arbitragem: {e}", exc_info=True)

        await asyncio.sleep(5)


# --- Função de watch por par (resiliente) ---
async def watch_order_book_for_pair(ex_id: str, pair: str):
    """
    Essa versão pega a instância atual da exchange em cada iteração a partir
    de global_exchanges_instances[ex_id]. Se a exchange for recriada pelo
    exchange_manager, as tasks vão automaticamente começar a usar a nova instância.
    """
    backoff = 1.0
    while True:
        exchange = global_exchanges_instances.get(ex_id)
        if exchange is None:
            # exchange ainda não criada ou em reconexão: espera e tenta novamente
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        try:
            order_book = await exchange.watch_order_book(pair)

            best_bid = order_book['bids'][0][0] if order_book.get('bids') else 0
            best_bid_volume = order_book['bids'][0][1] if order_book.get('bids') else 0
            best_ask = order_book['asks'][0][0] if order_book.get('asks') else float('inf')
            best_ask_volume = order_book['asks'][0][1] if order_book.get('asks') else 0

            # atualiza mercado — isso substitui o dado antigo para esse pair/exchange
            GLOBAL_MARKET_DATA.setdefault(pair, {})[ex_id] = {
                'bid': best_bid,
                'bid_volume': best_bid_volume,
                'ask': best_ask,
                'ask_volume': best_ask_volume
            }

            # sucesso — reset no backoff para reconexões futuras
            backoff = 1.0

        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Erro no WebSocket para {pair} em {ex_id}: {type(e).__name__}: {e}")
            # remove temporariamente os dados desta exchange para esse par para não causar falsos positivos
            GLOBAL_MARKET_DATA.setdefault(pair, {}).pop(ex_id, None)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

        except AttributeError as e:
            # tratado por causa do _buffer / conexões internas da lib
            logger.error(f"AttributeError no WebSocket para {pair} em {ex_id}: {e}")
            GLOBAL_MARKET_DATA.setdefault(pair, {}).pop(ex_id, None)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

        except Exception as e:
            logger.error(f"Erro inesperado no WebSocket para {pair} em {ex_id}: {e}", exc_info=True)
            GLOBAL_MARKET_DATA.setdefault(pair, {}).pop(ex_id, None)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


# --- Manager por exchange: cria a instância, carrega mercados e dispara tasks por par ---
async def exchange_manager(ex_id: str):
    """
    Roda em loop: cria a instância da exchange, carrega mercados e cria tasks para cada par disponível.
    Se a criação/carregamento falhar, faz backoff e tenta de novo. Cada par tem sua própria task resiliente.
    """
    backoff = 1.0
    while True:
        try:
            logger.info(f"[{ex_id}] Criando instância da exchange...")
            exchange_class = getattr(ccxt, ex_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'timeout': 10000,
            })
            global_exchanges_instances[ex_id] = exchange

            logger.info(f"[{ex_id}] Carregando mercados...")
            await exchange.load_markets()
            markets_loaded[ex_id] = True
            logger.info(f"[{ex_id}] Mercados carregados: {len(exchange.markets)}")

            # cria tasks por par disponível nesta exchange
            tasks = []
            for pair in PAIRS:
                if pair in exchange.markets:
                    tasks.append(asyncio.create_task(watch_order_book_for_pair(ex_id, pair)))
                else:
                    logger.debug(f"[{ex_id}] Par {pair} não disponível")

            # aguarda as tasks (normalmente as tasks rodam indefinidamente).
            # usamos gather com return_exceptions=True para evitar propagação de exceções aqui.
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # se não criou nenhuma task (nenhum par disponível), esperar e recriar
                logger.warning(f"[{ex_id}] Nenhum par criado — esperando antes de tentar novamente.")
                await asyncio.sleep(5)

            # se alguma coisa terminar, caímos aqui e vamos recriar a exchange (log acima será preenchido se necessário)
        except Exception as e:
            logger.error(f"[{ex_id}] Erro no manager da exchange: {e}", exc_info=True)
            # tenta fechar a instância se existir
            try:
                ex = global_exchanges_instances.get(ex_id)
                if ex:
                    await ex.close()
            except Exception:
                pass

            # remove instância e espera antes de tentar novamente
            global_exchanges_instances.pop(ex_id, None)
            markets_loaded.pop(ex_id, None)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)  # backoff exponencial, limitando a 60s
            continue


# --- Comandos Telegram (mantive suas funções originais) ---
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
    context.bot_data['admin_chat_id'] = None
    await update.message.reply_text("Alertas desativados. Use /start para reativar.")
    logger.info(f"Alertas de arbitragem desativados por {update.message.chat_id}")


# --- Main: cria managers por exchange + checador de arbitragem ---
async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
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
        BotCommand("stop", "Parar de receber alertas")
    ])

    logger.info("Iniciando managers de exchanges e checador de arbitragem...")

    try:
        # cria uma task manager por exchange (cada uma roda em loop independente)
        for ex_id in EXCHANGES_LIST:
            asyncio.create_task(exchange_manager(ex_id))

        # task de checagem de arbitragem (usa GLOBAL_MARKET_DATA)
        asyncio.create_task(check_arbitrage_opportunities(application))

        # start polling do Telegram (isso bloqueia até Ctrl+C)
        await application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

    except Exception as e:
        logger.error(f"Erro no loop principal do bot: {e}", exc_info=True)
    finally:
        logger.info("Fechando conexões das exchanges...")
        close_tasks = []
        for ex in list(global_exchanges_instances.values()):
            try:
                close_tasks.append(ex.close())
            except Exception:
                pass
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
