import os
import asyncio
import aiohttp
import telegram

# Pegando variáveis de ambiente do Heroku
TOKEN = os.getenv('TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Lista de exchanges simuladas (substitua com API real se necessário)
EXCHANGES = [
    'Binance', 'Coinbase', 'Kraken', 'Bitstamp', 'Huobi', 'KuCoin',
    'Gate.io', 'Poloniex', 'OKX', 'Bitfinex', 'Bittrex', 'Bybit',
    'Crypto.com', 'MEXC'
]

# Lista de moedas simuladas (substitua com pares reais)
PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'LTC/USDT', 'XRP/USDT', 'ADA/USDT',
    'SOL/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'AVAX/USDT',
    'SHIB/USDT', 'TRX/USDT', 'LINK/USDT', 'ATOM/USDT', 'BCH/USDT'
]

async def buscar_arquivo_ficticio_de_arbitragem():
    oportunidades = []
    for par in PAIRS:
        for i in range(len(EXCHANGES)):
            for j in range(i + 1, len(EXCHANGES)):
                preco_a = 100 + i  # simulação
                preco_b = 100 + j  # simulação
                diferenca = abs(preco_a - preco_b)
                if diferenca >= 5:  # margem mínima de arbitragem fictícia
                    oportunidades.append(f'Oportunidade: {par} em {EXCHANGES[i]} e {EXCHANGES[j]} | Diferença: {diferenca}')
    return oportunidades

async def enviar_mensagem(mensagem):
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mensagem)

async def verificar_arbitragem():
    oportunidades = await buscar_arquivo_ficticio_de_arbitragem()
    if oportunidades:
        for oportunidade in oportunidades:
            await enviar_mensagem(oportunidade)
    else:
        await enviar_mensagem('Nenhuma oportunidade de arbitragem encontrada.')

async def main():
    while True:
        try:
            await verificar_arbitragem()
            await asyncio.sleep(60)  # espera 60 segundos para nova análise
        except Exception as e:
            await enviar_mensagem(f'Erro detectado: {e}')
            await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
