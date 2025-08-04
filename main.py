import asyncio
import aiohttp
import telegram

TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'
LUCRO_MINIMO = 0.5  # em porcentagem
PAIRES_MONITORADOS = 100

# Lista de moedas para monitorar (pode expandir até 100)
MOEDAS = [
    'BTC', 'ETH', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'AVAX', 'TRX', 'MATIC',
    'LTC', 'LINK', 'BCH', 'UNI', 'ATOM', 'XLM', 'NEAR', 'APE', 'ETC', 'FIL',
    'EOS', 'XTZ', 'AAVE', 'SUSHI', 'COMP', 'VET', 'HBAR', 'FTM', 'RUNE', 'ZEC', 'MKR',
    'ALGO', 'SNX', 'CRV', 'ENJ', 'KSM', 'KNC', 'LRC', 'ZRX', 'CHZ', 'ANKR',
    'BAT', 'OMG', 'DASH', 'QTUM', 'ICX', 'ONT', 'WAVES', 'NANO', 'BNT', 'SC',
    '1INCH', 'YFI', 'GRT', 'CKB', 'BAND', 'REEF', 'RSR', 'STORJ', 'DGB', 'REN',
    'SRM', 'CELR', 'CVC', 'ARDR', 'SYS', 'XEM', 'FUN', 'POWR', 'NMR', 'LPT',
    'RLC', 'STMX', 'XVG', 'SNT', 'OXT', 'ELF', 'NKN', 'POLY', 'STPT', 'TOMO',
    'TRB', 'REQ', 'BTS', 'STEEM', 'STRAX', 'PERL', 'BLZ', 'MFT', 'DNT', 'PHA',
    'FORTH', 'ORN', 'DATA', 'UTK', 'DOCK', 'MDT', 'CTSI', 'MIR', 'FET', 'LINA'
]

EXCHANGES = {
    "binance": "https://api.binance.com/api/v3/ticker/price?symbol={}USDT",
    "gateio": "https://api.gate.io/api2/1/ticker/{}_usdt",
    "kucoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={}USDT"
}

bot = telegram.Bot(token=TOKEN)

async def pegar_preco(session, exchange, moeda):
    url = EXCHANGES[exchange].format(moeda.lower() if exchange == "gateio" else moeda.upper())
    try:
        async with session.get(url, timeout=10) as resp:
            data = await resp.json()
            if exchange == "binance":
                return float(data["price"])
            elif exchange == "gateio":
                return float(data["last"])
            elif exchange == "kucoin":
                return float(data["price"])
    except Exception as e:
        print(f"[ERRO] {exchange.upper()} - {moeda}: {e}")
        return None

async def verificar_oportunidade(session, moeda):
    precos = {}
    for exchange in EXCHANGES:
        preco = await pegar_preco(session, exchange, moeda)
        if preco:
            precos[exchange] = preco

    if len(precos) >= 2:
        maior = max(precos, key=precos.get)
        menor = min(precos, key=precos.get)
        preco_maior = precos[maior]
        preco_menor = precos[menor]
        lucro_percentual = ((preco_maior - preco_menor) / preco_menor) * 100

        if lucro_percentual >= LUCRO_MINIMO:
            mensagem = f"📈 *Arbitragem encontrada!* 💰\n\n" \
                       f"Moeda: *{moeda}*\n" \
                       f"Comprar: *{menor.upper()}* a *{preco_menor:.2f} USDT*\n" \
                       f"Vender: *{maior.upper()}* a *{preco_maior:.2f} USDT*\n" \
                       f"Lucro: *{lucro_percentual:.2f}%*"
            await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode=telegram.constants.ParseMode.MARKDOWN)

async def loop_arbitragem():
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [verificar_oportunidade(session, moeda) for moeda in MOEDAS[:PAIRES_MONITORADOS]]
            await asyncio.gather(*tasks)
        await asyncio.sleep(60)  # verifica a cada 1 minuto

if __name__ == "__main__":
    print("Bot iniciado e rodando no Heroku...")
    asyncio.run(loop_arbitragem())
