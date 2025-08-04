import os
import asyncio
import aiohttp
import telegram
from telegram import Bot

# 🔐 Variáveis de ambiente do Heroku (adicionadas em Config Vars)
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("TOKEN ou CHAT_ID não está definido nas Config Vars do Heroku.")

bot = Bot(token=TOKEN)

# 🔁 Lista de pares e exchanges — você pode expandir isso à vontade
MOEDAS = ['BTC/USDT', 'ETH/USDT', 'LTC/USDT']
EXCHANGES = ['Binance', 'Coinbase', 'Kraken']

async def buscar_oportunidades():
    while True:
        try:
            texto = "✅ Oportunidade encontrada:\n"
            for moeda in MOEDAS:
                for i in range(len(EXCHANGES)):
                    for j in range(i + 1, len(EXCHANGES)):
                        ex1 = EXCHANGES[i]
                        ex2 = EXCHANGES[j]

                        # ⚠️ Exemplo de simulação (substitua pelas suas APIs reais)
                        preco_ex1 = 100.0  # simulado
                        preco_ex2 = 105.0  # simulado
                        lucro_percentual = ((preco_ex2 - preco_ex1) / preco_ex1) * 100

                        if lucro_percentual > 2:
                            texto += f"\n🔁 {moeda}\n{ex1}: ${preco_ex1:.2f}\n{ex2}: ${preco_ex2:.2f}\nLucro: {lucro_percentual:.2f}%\n"

            if "Lucro" in texto:
                await bot.send_message(chat_id=CHAT_ID, text=texto)

        except Exception as e:
            print(f"Erro ao buscar oportunidades: {e}")

        await asyncio.sleep(60)  # ⏱ Intervalo de 1 minuto entre buscas

async def main():
    print("🤖 Bot iniciado...")
    await buscar_oportunidades()

if __name__ == "__main__":
    asyncio.run(main())
