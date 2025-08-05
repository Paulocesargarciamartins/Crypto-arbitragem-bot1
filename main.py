import requests

# Exchanges e seus endpoints públicos para o par ADA/USDC
exchanges = {
    "Binance": "https://api.binance.com/api/v3/ticker/price?symbol=ADAUSDC",
    "Coinbase": "https://api.pro.coinbase.com/products/ADA-USDC/ticker",
    "KuCoin": "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=ADA-USDC",
    "Kraken": "https://api.kraken.com/0/public/Ticker?pair=ADAUSDC",
}

precos = {}

for nome, url in exchanges.items():
    try:
        response = requests.get(url, timeout=5)
        data = response.json()

        if nome == "Binance":
            preco = float(data["price"])
        elif nome == "Coinbase":
            preco = float(data["price"])
        elif nome == "KuCoin":
            preco = float(data["data"]["price"])
        elif nome == "Kraken":
            par = list(data["result"].keys())[0]
            preco = float(data["result"][par]["c"][0])
        else:
            continue

        precos[nome] = preco

    except Exception as e:
        print(f"Erro ao obter dados da {nome}: {e}")

# Exibir resultados
if precos:
    menor_exchange = min(precos, key=precos.get)
    maior_exchange = max(precos, key=precos.get)
    menor_preco = precos[menor_exchange]
    maior_preco = precos[maior_exchange]

    diferenca = ((maior_preco - menor_preco) / menor_preco) * 100
    ada_compradas = 20 / menor_preco

    print(f"Menor preço: {menor_preco:.4f} USDC ({menor_exchange})")
    print(f"Maior preço: {maior_preco:.4f} USDC ({maior_exchange})")
    print(f"🔁 Diferença percentual: {diferenca:.2f}%")
    print(f"💰 Simulação: com 20 USDT você compra {ada_compradas:.4f} ADA na {menor_exchange}")
else:
    print("Não foi possível obter os preços.")
