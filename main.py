import asyncio
import aiohttp
import telegram

TOKEN = 'SEU_TOKEN_DO_BOT'
CHAT_ID = 'SEU_CHAT_ID'
INTERVALO = 60  # segundos

EXCHANGES = {
    "Binance": "https://api.binance.com/api/v3/ticker/price",
    "Coinbase": "https://api.pro.coinbase.com/products/{}/ticker",
    "Kraken": "https://api.kraken.com/0/public/Ticker?pair={}",
}

PARES = [
    "ADAUSDC", "AVAXUSDC", "BCHUSDC", "BNBUSDC", "BTCUSDC", "COMPUSDC", "DOGEUSDC", "DOTUSDC",
    "DYDXUSDC", "ENAUSDC", "ENJUSDC", "ENSUSDC", "ETCUSDC", "ETHUSDC", "FILUSDC", "FTMUSDC",
    "GALAUSDC", "IMXUSDC", "INJUSDC", "ICPUSDC", "JASMYUSDC", "KAVAUSDC", "KLAYUSDC", "LINKUSDC",
    "LDOUSDC", "LTCUSDC", "MATICUSDC", "MKRUSDC", "NEARUSDC", "OCEANUSDC", "OPUSDC", "ORDIUSDC",
    "PEPEUSDC", "PYTHUSDC", "QNTUSDC", "RAYUSDC", "RNDRUSDC", "RUNEUSDC", "SANDUSDC", "SEIUSDC",
    "SHIBUSDC", "SNXUSDC", "SOLUSDC", "STGUSDC", "STXUSDC", "SUIUSDC", "TIAUSDC", "TONUSDC",
    "TRXUSDC", "TUSDUSDC", "UNIUSDC", "VETUSDC", "WAVESUSDC", "WLDUSDC", "XLMUSDC", "XMRUSDC",
    "XRPUSDC", "XTZUSDC", "ZILUSDC", "ZRXUSDC", "1INCHUSDC", "AAVEUSDC", "ACHUSDC", "AKROUSDC",
    "ALGOUSDC", "ALICEUSDC", "ANKRUSDC", "ARBUSDC", "ARDRUSDC", "ATOMUSDC", "AUDIOUSDC", "BAKEUSDC",
    "BALUSDC", "BANDUSDC", "BATUSDC", "BELUSDC", "BETAUSDC", "BLZUSDC", "BNTUSDC", "BRISEUSDC",
    "BSWUSDC", "C98USDC", "CELOUSDC", "CHRUSDC", "CHZUSDC", "CKBUSDC", "CLVUSDC", "COTIUSDC",
    "CVCUSDC", "DASHUSDC", "DENTUSDC", "DEXEUSDC", "DGBUSDC", "DOCKUSDC", "DODOUSDC", "EGLDUSDC",
    "ELFUSDC", "ERNUSDC", "FETUSDC", "FLMUSDC", "FLOWUSDC", "FOOTBALLUSDC", "FXSUSDC", "GRTUSDC",
    "GTCUSDC", "HBARUSDC", "HNTUSDC", "HOTUSDC", "ICPUSDC", "ICXUSDC", "IOSTUSDC", "IOTAUSDC",
    "JSTUSDC", "KNCUSDC", "LINAUSDC", "LOOMUSDC", "LPTUSDC", "LSKUSDC", "LTOUSDC", "MANAUSDC",
    "MINAUSDC", "MTLUSDC", "NANOUSDC", "NKNUSDC", "NMRUSDC", "OCEANUSDC", "OGNUSDC", "OMGUSDC",
    "ONEUSDC", "ONTUSDC", "OXTUSDC", "PAXGUSDC", "PERLUSDC", "PHAUSDC", "POLSUSDC", "QKCUSDC",
    "QTUMUSDC", "REEFUSDC", "RENUSDC", "REPUSDC", "REQUSDC", "RSRUSDC", "RLCUSDC", "RVNUSDC",
    "SKLUSDC", "SNTUSDC", "SPELLUSDC", "SRMUSDC", "STEEMUSDC", "STMXUSDC", "STORJUSDC", "SUNUSDC",
    "SUPERUSDC", "SUSHIUSDC", "SXPUSDC", "THETAUSDC", "TOMOUSDC", "TROYUSDC", "TWTUSDC", "UMAUSDC",
    "VTHOUSDC", "WAXPUSDC", "WINUSDC", "WRXUSDC", "XEMUSDC", "XVSUSDC", "YFIUSDC", "ZECUSDC",
]

bot = telegram.Bot(token=TOKEN)

async def obter_preco_binance(session, par):
    try:
        async with session.get(EXCHANGES["Binance"]) as resp:
            data = await resp.json()
            for p in data:
                if p["symbol"] == par:
                    return float(p["price"])
    except Exception as e:
        print(f"Erro Binance ({par}): {e}")
    return None

async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        for par in PARES:
            preco_binance = await obter_preco_binance(session, par)
            if preco_binance:
                mensagem = f"🪙 Oportunidade: {par}\nPreço Binance: {preco_binance:.4f}"
                await bot.send_message(chat_id=CHAT_ID, text=mensagem)

        texto = "Pares monitorados:\n" + ", ".join(PARES[:20]) + "..."
        await bot.send_message(chat_id=CHAT_ID, text=texto)

async def main():
    while True:
        await verificar_arbitragem()
        await asyncio.sleep(INTERVALO)

if __name__ == "__main__":
    asyncio.run(main())
