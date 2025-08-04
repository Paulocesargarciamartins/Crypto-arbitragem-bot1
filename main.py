import asyncio
import aiohttp
import time
import telegram

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"
MIN_LUCRO = 0.5  # 0.5% de lucro mínimo para alertar

moedas = [
    "BTC", "ETH", "LTC", "XRP", "DOGE", "ADA", "TRX", "SOL", "MATIC",
    "BCH", "DOT", "AVAX", "ATOM", "NEAR", "UNI", "XLM", "ALGO", "APE",
    "SAND", "AXS", "GMT", "FTM", "GALA", "CHZ", "RNDR", "HBAR", "AR",
    "WAVES", "BAND", "STMX", "STORJ", "SC", "REEF", "KNC", "CTSI", "SYS"
]

exchanges = {
    "BINANCE": "https://api.binance.com/api/v3/ticker/price?symbol={moeda}USDT",
    "KUCOIN": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={moeda}-USDT"
}

bot = telegram.Bot(token=TOKEN)

async def get_price(session, url, exchange, moeda):
    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()

            if exchange == "BINANCE":
                return float(data["price"])

            elif exchange == "KUCOIN":
                if "data" in data and "price" in data["data"]:
                    return float(data["data"]["price"])
                else:
                    print(f"[ERRO] {exchange} - {moeda}: 'price' ausente")
                    return None
    except Exception as e:
        print(f"[ERRO] {exchange} - {moeda}: {e}")
        return None

async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        for moeda in moedas:
            tasks = []
            for exchange, url in exchanges.items():
                full_url = url.format(moeda=moeda)
                tasks.append(get_price(session, full_url, exchange, moeda))

            try:
                resultados = await asyncio.gather(*tasks)
                if None in resultados or len(resultados) != 2:
                    continue

                preco_binance, preco_kucoin = resultados

                maior = max(preco_binance, preco_kucoin)
                menor = min(preco_binance, preco_kucoin)

                if menor == 0:
                    continue

                lucro_percent = ((maior - menor) / menor) * 100

                if lucro_percent >= MIN_LUCRO:
                    exchange_compra = "BINANCE" if preco_binance == menor else "KUCOIN"
                    exchange_venda = "BINANCE" if preco_binance == maior else "KUCOIN"
                    mensagem = (
                        f"💰 *Oportunidade de Arbitragem*\n"
                        f"Moeda: *{moeda}*\n"
                        f"Comprar em: *{exchange_compra}* a *${menor:.4f}*\n"
                        f"Vender em: *{exchange_venda}* a *${maior:.4f}*\n"
                        f"Lucro estimado: *{lucro_percent:.2f}%*"
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
                    print(f"[ALERTA ENVIADO] {mensagem}")

            except Exception as e:
                print(f"[ERRO geral] {moeda}: {e}")

async def arbitrage_loop():
    print("Bot pronto para receber comandos...")
    while True:
        await verificar_arbitragem()
        await asyncio.sleep(30)  # verifica a cada 30 segundos

if __name__ == "__main__":
    try:
        asyncio.run(arbitrage_loop())
    except Exception as e:
        print(f"[ERRO FATAL] {e}")
