import os
import asyncio
import aiohttp
import logging
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurações iniciais
TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID") or "1093248456"

# Setup logging
logging.basicConfig(
    format='[%(levelname)s] %(asctime)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Inicializa bot Telegram
bot = Bot(token=TOKEN)

# Configuráveis pelo usuário via Telegram (padrões)
lucro_minimo = 1.0  # % mínimo para enviar alerta

# Exchanges e URL base para consultar preço
exchanges = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}",
    "coinbase": "https://api.coinbase.com/v2/prices/{}-USDT/spot",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}",
    "bitstamp": "https://www.bitstamp.net/api/v2/ticker/{}",
    "bittrex": "https://api.bittrex.com/v3/markets/{}/ticker",
    "gateio": "https://api.gate.io/api2/1/tickers",
    "okx": "https://www.okx.com/api/v5/market/ticker?instId={}",
    "bybit": "https://api.bybit.com/v2/public/tickers?symbol={}",
    "poloniex": "https://poloniex.com/public?command=returnTicker",
    "huobi": "https://api.huobi.pro/market/detail/merged?symbol={}",
    "bitfinex": "https://api-pub.bitfinex.com/v2/tickers?symbols=t{}",
    "mercadobitcoin": "https://www.mercadobitcoin.net/api/{}/ticker/",
    "kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
    "bitmex": "https://www.bitmex.com/api/v1/instrument?symbol={}",
    "bitflyer": "https://api.bitflyer.com/v1/ticker?product_code={}",
    "hitbtc": "https://api.hitbtc.com/api/2/public/ticker/{}",
    "bitstamp2": "https://www.bitstamp.net/api/v2/ticker/{}",
    "deribit": "https://www.deribit.com/api/v2/public/ticker?instrument_name={}",
    "ftx": "https://ftx.com/api/markets/{}",
    "liquid": "https://api.liquid.com/products/{}",
}

# Lista simplificada das top 100 pares USDT para exemplo (você pode atualizar)
pares_usdt = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "SHIBUSDT", "TRXUSDT", "AVAXUSDT", "UNIUSDT", "LINKUSDT",
    "ALGOUSDT", "ATOMUSDT", "XLMUSDT", "VETUSDT", "ICPUSDT",
    # ... complete até 100 pares
]

async def fetch_price(session, exchange, symbol):
    url = None
    symbol_api = symbol
    try:
        if exchange == "binance":
            url = exchanges[exchange].format(symbol)
            async with session.get(url) as r:
                data = await r.json()
                return float(data['price'])
        elif exchange == "coinbase":
            url = exchanges[exchange].format(symbol[:-4])  # Exemplo: BTCUSDT -> BTC
            async with session.get(url) as r:
                data = await r.json()
                return float(data['data']['amount'])
        elif exchange == "kucoin":
            url = exchanges[exchange].format(symbol)
            async with session.get(url) as r:
                data = await r.json()
                return float(data['data']['price'])
        elif exchange == "bitstamp":
            symbol_bs = symbol[:-4].lower() + "usd"  # BTCUSDT -> btcusd (bitstamp usa USD)
            url = exchanges[exchange].format(symbol_bs)
            async with session.get(url) as r:
                data = await r.json()
                return float(data['last'])
        elif exchange == "bittrex":
            symbol_br = symbol[:-4] + "-USDT"
            url = exchanges[exchange].format(symbol_br)
            async with session.get(url) as r:
                data = await r.json()
                return float(data['lastTradeRate'])
        elif exchange == "gateio":
            # gate.io retorna todos, precisamos parsear
            url = exchanges[exchange]
            async with session.get(url) as r:
                data = await r.json()
                ticker = data.get(symbol.lower() + "_usdt")
                if ticker:
                    return float(ticker['last'])
                return None
        elif exchange == "okx":
            url = exchanges[exchange].format(symbol)
            async with session.get(url) as r:
                data = await r.json()
                if 'data' in data and len(data['data'])>0:
                    return float(data['data'][0]['last'])
                return None
        elif exchange == "bybit":
            url = exchanges[exchange].format(symbol)
            async with session.get(url) as r:
                data = await r.json()
                if 'result' in data and len(data['result'])>0:
                    return float(data['result'][0]['last_price'])
                return None
        # ... Você pode adicionar os outros exchanges aqui com seu parsing correto
        else:
            return None
    except Exception as e:
        logger.error(f"[Erro] {exchange}: {e} url={url}")
        return None

async def check_arbitrage():
    async with aiohttp.ClientSession() as session:
        for pair in pares_usdt:
            prices = {}
            for ex in exchanges.keys():
                price = await fetch_price(session, ex, pair)
                if price:
                    prices[ex] = price

            if len(prices) >= 2:
                min_ex = min(prices, key=prices.get)
                max_ex = max(prices, key=prices.get)
                min_price = prices[min_ex]
                max_price = prices[max_ex]
                lucro = ((max_price - min_price) / min_price) * 100

                logger.debug(f"{pair} preços: {prices}")

                if lucro >= lucro_minimo:
                    texto = (
                        f"💰 Oportunidade de Arbitragem!\n"
                        f"🪙 Par: {pair}\n"
                        f"🔻 Comprar: {min_ex} a {min_price:.6f}\n"
                        f"🔺 Vender: {max_ex} a {max_price:.6f}\n"
                        f"📈 Lucro estimado: {lucro:.2f}%"
                    )
                    try:
                        await bot.send_message(chat_id=CHAT_ID, text=texto)
                    except Exception as e:
                        logger.error(f"Erro ao enviar mensagem Telegram: {e}")

# Comandos Telegram para configurar e obter status

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Bot de Arbitragem iniciado.\n"
        "Use /lucro para ver ou definir lucro mínimo para alertas.\n"
        "Exemplo: /lucro 1.5\n"
        "Use /pares para listar alguns pares.\n"
        "Use /exchanges para listar exchanges monitoradas."
    )

async def cmd_lucro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global lucro_minimo
    args = context.args
    if args and len(args) == 1:
        try:
            novo_valor = float(args[0])
            lucro_minimo = novo_valor
            await update.message.reply_text(f"Lucro mínimo atualizado para {lucro_minimo}%")
        except ValueError:
            await update.message.reply_text("Use um número válido. Exemplo: /lucro 1.5")
    else:
        await update.message.reply_text(f"Lucro mínimo atual: {lucro_minimo}%")

async def cmd_pares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lista = ", ".join(pares_usdt[:20])
    await update.message.reply_text(f"Pares monitorados (top 20):\n{lista}")

async def cmd_exchanges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lista = ", ".join(exchanges.keys())
    await update.message.reply_text(f"Exchanges monitoradas:\n{lista}")

async def loop_arbitragem(application):
    while True:
        logger.info("Verificando arbitragem...")
        await check_arbitrage()
        await asyncio.sleep(60)

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("lucro", cmd_lucro))
    application.add_handler(CommandHandler("pares", cmd_pares))
    application.add_handler(CommandHandler("exchanges", cmd_exchanges))

    # Start arbitrage loop in background
    asyncio.create_task(loop_arbitragem(application))

    # Run bot until interrupted
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot finalizado")
