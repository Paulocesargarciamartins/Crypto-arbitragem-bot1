import os  # Importa a biblioteca os para acessar as variáveis de ambiente
import time
import asyncio
import aiohttp
import telegram

# --- CONFIGURAÇÕES DO BOT TELEGRAM ---
# Lê as variáveis de ambiente do Heroku
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

# --- CONFIGURAÇÕES GERAIS ---
INTERVALO_CHECAGEM = 60  # segundos
LUCRO_MINIMO = 1.0  # em %

# --- LISTA DE EXCHANGES ---
EXCHANGES = [
    'binance', 'kucoin', 'kraken', 'coinbase', 'okx', 'huobi',
    'gate', 'bitfinex', 'bitstamp', 'bybit', 'mexc', 'bitget',
    'poloniex', 'bittrex', 'coinex'
]

# --- LISTA DE PARES DE MOEDAS (AS 100 MAIORES) ---
# (Aqui você pode ajustar ou importar dinamicamente depois)
MOEDAS = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'AVAX', 'LINK', 'DOT']

# --- FUNÇÃO: Enviar mensagem para o Telegram ---
async def enviar_mensagem(mensagem):
    # Verifica se as variáveis foram lidas corretamente antes de continuar
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro: As variáveis de ambiente TOKEN ou CHAT_ID não foram encontradas.")
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensagem, parse_mode=telegram.constants.ParseMode.HTML)

# --- FUNÇÃO: Buscar preços de uma moeda em várias exchanges ---
async def buscar_preco_par(session, par):
    resultados = {}

    for ex in EXCHANGES:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={par}&vs_currencies=usd&exchange_ids={ex}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if par in data and 'usd' in data[par]:
                        resultados[ex] = data[par]['usd']
        except Exception as e:
            # Captura exceções para evitar que o loop pare
            print(f"Erro ao buscar preço em {ex}: {e}")
            continue

    return resultados

# --- FUNÇÃO: Verificar arbitragem em um par ---
def encontrar_arbitragem(precos):
    if not precos:
        return None

    try:
        menor = min(precos.items(), key=lambda x: x[1])
        maior = max(precos.items(), key=lambda x: x[1])
    except ValueError:
        return None

    preco_compra = menor[1]
    preco_venda = maior[1]

    if preco_compra == 0:
        return None

    lucro_percentual = ((preco_venda - preco_compra) / preco_compra) * 100

    if lucro_percentual >= LUCRO_MINIMO:
        return {
            'compra': menor,
            'venda': maior,
            'lucro': round(lucro_percentual, 2)
        }

    return None

# --- LOOP PRINCIPAL ---
async def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro crítico: As variáveis de ambiente TOKEN ou CHAT_ID não foram configuradas. O bot será encerrado.")
        return

    await enviar_mensagem("🟢 <b>Bot de Arbitragem Cripto iniciado.</b>")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                for moeda in MOEDAS:
                    par = moeda.lower()
                    precos = await buscar_preco_par(session, par)
                    arbitragem = encontrar_arbitragem(precos)

                    if arbitragem:
                        msg = (
                            f"💸 <b>ARBITRAGEM DETECTADA</b>\n\n"
                            f"🪙 Par: {moeda}/USD\n"
                            f"📉 Comprar em: {arbitragem['compra'][0]} por ${arbitragem['compra'][1]:.2f}\n"
                            f"📈 Vender em: {arbitragem['venda'][0]} por ${arbitragem['venda'][1]:.2f}\n"
                            f"💰 Lucro: <b>{arbitragem['lucro']}%</b>"
                        )
                        await enviar_mensagem(msg)

            await asyncio.sleep(INTERVALO_CHECAGEM)

        except Exception as e:
            await enviar_mensagem(f"❗️Erro no bot: {str(e)}")
            await asyncio.sleep(60)

# --- EXECUÇÃO ---
if __name__ == "__main__":
    asyncio.run(main())

