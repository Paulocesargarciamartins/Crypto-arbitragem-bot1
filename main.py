import asyncio
import aiohttp
import telegram
import time

# Configurações do seu bot e chat do Telegram
TOKEN = '7218062934:AAEcgNpqN3itPQ-GzotVtR_eQc7g9FynbzQ'
CHAT_ID = '1093248456'

# Lista das exchanges com URL da API pública
exchanges = {
    "Binance": "https://api.binance.com/api/v3/ticker/price",
    "Coinbase": "https://api.coinbase.com/v2/exchange-rates?currency=USDT",
    "Bitstamp": "https://www.bitstamp.net/api/v2/ticker/btcusdt/",
    "MercadoBitcoin": "https://www.mercadobitcoin.net/api/BTC/ticker/",
}

# Lista de pares que o bot irá monitorar
moedas = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LTCUSDT"]

# Configuração do limite de arbitragem para alertas
LIMITE_ARBITRAGEM = 0.8  # 0.8%

# Formata os valores de preço
def formatar(valor):
    return f'{valor:,.2f}'

# Envia a mensagem formatada para o Telegram
async def enviar_telegram(mensagem):
    bot = telegram.Bot(token=TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode=telegram.constants.ParseMode.HTML)
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")

# Busca os preços das exchanges
async def obter_preco(session, exchange, url, moeda):
    try:
        async with session.get(url, timeout=10) as resp:
            data = await resp.json()
            if exchange == "Binance":
                for par in data:
                    if par["symbol"] == moeda:
                        return float(par["price"])
            elif exchange == "Coinbase":
                return 1 / float(data["data"]["rates"].get(moeda.replace("USDT", ""), 0))
            elif exchange == "Bitstamp":
                return float(data["last"]) if moeda == "BTCUSDT" else None
            elif exchange == "MercadoBitcoin":
                return float(data["ticker"]["last"]) if moeda == "BTCUSDT" else None
    except:
        return None

# Verifica arbitragem entre todas as exchanges e pares
async def verificar_arbitragem():
    async with aiohttp.ClientSession() as session:
        while True:
            for moeda in moedas:
                precos = {}
                for exchange, url in exchanges.items():
                    preco = await obter_preco(session, exchange, url, moeda)
                    if preco:
                        precos[exchange] = preco

                if len(precos) >= 2:
                    menor = min(precos.values())
                    maior = max(precos.values())
                    diferenca = ((maior - menor) / menor) * 100

                    if diferenca >= LIMITE_ARBITRAGEM:
                        msg = f"💰 <b>ARBITRAGEM DETECTADA</b>\n\n<b>Par:</b> <code>{moeda}</code>\n<b>Lucro:</b> <code>{diferenca:.2f}%</code>\n"
                        for ex, val in precos.items():
                            msg += f"{ex}: <b>R${formatar(val)}</b>\n"
                        await enviar_telegram(msg)

                # DEBUG
                print(f"[DEBUG] {moeda} - Preços: {precos}")

            await asyncio.sleep(30)  # Espera 30 segundos antes da próxima verificação

# Início
if __name__ == "__main__":
    asyncio.run(verificar_arbitragem())
