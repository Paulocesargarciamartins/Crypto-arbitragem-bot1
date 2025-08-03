import asyncio
import aiohttp
import telegram

# Configurações do Telegram
TOKEN = '7218062934:AAFokGnqbOozHMLEB63IsTjxA8uZhfBoZj8'
CHAT_ID = '1093248456'

# Lista de casas de apostas simuladas
casas = ["Binance", "Coinbase", "Kraken", "OKX", "Kucoin", "Bybit", "Gate.io"]

# Lista de criptomoedas simuladas
moedas = ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP", "DOGE"]

# Simulação de odds (preços) diferentes
async def buscar_precos():
    precos = {}
    async with aiohttp.ClientSession() as session:
        for casa in casas:
            precos[casa] = {}
            for moeda in moedas:
                # Simulando preço aleatório para teste (depois pode ser trocado por API real)
                async with session.get(f'https://api.coingecko.com/api/v3/simple/price?ids={moeda.lower()}&vs_currencies=usd') as resp:
                    data = await resp.json()
                    preco = data.get(moeda.lower(), {}).get("usd", 0)
                    if preco == 0:
                        preco = 100.0
                    precos[casa][moeda] = preco * (1 + (0.01 * casas.index(casa)))  # Simula variação por casa
    return precos

# Verifica arbitragem
def detectar_arbitragem(precos):
    oportunidades = []
    for moeda in moedas:
        menor_preco = min(precos[casa][moeda] for casa in casas)
        maior_preco = max(precos[casa][moeda] for casa in casas)
        lucro = (maior_preco - menor_preco) / menor_preco * 100
        if lucro > 1.5:
            casa_compra = [c for c in casas if precos[c][moeda] == menor_preco][0]
            casa_venda = [c for c in casas if precos[c][moeda] == maior_preco][0]
            oportunidades.append({
                "moeda": moeda,
                "lucro": round(lucro, 2),
                "comprar_em": casa_compra,
                "vender_em": casa_venda,
                "preco_compra": round(menor_preco, 2),
                "preco_venda": round(maior_preco, 2)
            })
    return oportunidades

# Envia alerta para o Telegram
async def enviar_telegram(oportunidades):
    if not oportunidades:
        return
    bot = telegram.Bot(token=TOKEN)
    for opp in oportunidades:
        msg = (
            f"🚨 *Oportunidade de Arbitragem Cripto!*\n\n"
            f"💰 Moeda: *{opp['moeda']}*\n"
            f"🔽 Comprar em: *{opp['comprar_em']}* a ${opp['preco_compra']}\n"
            f"🔼 Vender em: *{opp['vender_em']}* a ${opp['preco_venda']}\n"
            f"📈 Lucro estimado: *{opp['lucro']}%*\n"
        )
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=telegram.constants.ParseMode.MARKDOWN)

# Loop principal
async def main():
    while True:
        try:
            precos = await buscar_precos()
            oportunidades = detectar_arbitragem(precos)
            await enviar_telegram(oportunidades)
            await asyncio.sleep(60)  # Espera 1 minuto entre cada verificação
        except Exception as e:
            print(f"Erro: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
