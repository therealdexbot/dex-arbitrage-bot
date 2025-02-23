import time
import requests
from web3 import Web3
from flask import Flask, render_template_string
from datetime import datetime
import threading

app = Flask(__name__)

# Connect to Ethereum network
eth_node = "https://mainnet.infura.io/v3/72b1b6ce4ced409ba27f157f9ed6b0fd"
web3_eth = Web3(Web3.HTTPProvider(eth_node))

if not web3_eth.is_connected():
    print("Failed to connect to Ethereum!")
    exit()

uniswap_router = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
uniswap_contract = web3_eth.eth.contract(address=uniswap_router, abi=[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}])

weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
wbtc = Web3.to_checksum_address("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599")

investment_usd = 1000  # Your investment amount in USD

# Global data storage
bot_data = {
    "timestamp": "",
    "uniswap_eth_btc": 0,
    "uniswap_bnb_btc": 0,
    "pancakeswap_bnb_btc": 0,
    "eth_bnb_rate": 0,
    "btc_amount": 0,
    "profit_direction": "",
    "profit_bnb": 0,
    "profit_usd": 0,
    "status": "Starting..."
}

def get_rates():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin&vs_currencies=usd"
        response = requests.get(url).json()
        btc_usd = response['bitcoin']['usd']
        eth_usd = response['ethereum']['usd']
        bnb_usd = response['binancecoin']['usd']
        return btc_usd, eth_usd / bnb_usd, bnb_usd
    except Exception as e:
        print(f"Error fetching rates: {e}")
        return 60000, 4, 420  # Fallbacks

def get_price(web3, contract, token_in, token_out):
    decimals = {weth: 18, wbtc: 8}
    path = [token_in, token_out]
    try:
        decimals_in = decimals[token_in]
        decimals_out = decimals[token_out]
        amount_in = 10**decimals_in
        amounts = contract.functions.getAmountsOut(amount_in, path).call()
        raw_amount = amounts[1]
        adjusted_amount = raw_amount / (10**decimals_out)
        return adjusted_amount
    except Exception as e:
        print(f"Error fetching price: {str(e)}")
        return None

def run_bot():
    fee_rate = 0.000  # 0.3% DEX fee
    rates_refresh_counter = 0
    btc_usd, eth_to_bnb_rate, bnb_usd = get_rates()
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uniswap_price_raw = get_price(web3_eth, uniswap_contract, weth, wbtc)
        
        rates_refresh_counter += 1
        if rates_refresh_counter >= 5:
            btc_usd, eth_to_bnb_rate, bnb_usd = get_rates()
            rates_refresh_counter = 0

        if uniswap_price_raw is None:
            bot_data["status"] = "Error fetching Uniswap price..."
        else:
            uniswap_eth_per_btc = 1 / uniswap_price_raw
            uniswap_bnb_per_btc = uniswap_eth_per_btc * eth_to_bnb_rate
            pancakeswap_bnb_per_btc = btc_usd / bnb_usd

            profit1_per_btc = pancakeswap_bnb_per_btc * (1 - fee_rate) - uniswap_bnb_per_btc * (1 + fee_rate)
            profit2_per_btc = uniswap_bnb_per_btc * (1 - fee_rate) - pancakeswap_bnb_per_btc * (1 + fee_rate)

            btc_amount = investment_usd / btc_usd
            if profit1_per_btc > 0:
                profit_bnb = profit1_per_btc * btc_amount
                profit_usd = profit_bnb * bnb_usd
                direction = "Buy Uniswap, Sell PancakeSwap"
            elif profit2_per_btc > 0:
                profit_bnb = profit2_per_btc * btc_amount
                profit_usd = profit_bnb * bnb_usd
                direction = "Buy PancakeSwap, Sell Uniswap"
            else:
                profit_bnb = 0
                profit_usd = 0
                direction = "No profit"

            bot_data.update({
                "timestamp": timestamp,
                "uniswap_eth_btc": round(uniswap_eth_per_btc, 2),
                "uniswap_bnb_btc": round(uniswap_bnb_per_btc, 2),
                "pancakeswap_bnb_btc": round(pancakeswap_bnb_per_btc, 2),
                "eth_bnb_rate": round(eth_to_bnb_rate, 2),
                "btc_amount": round(btc_amount, 6),
                "profit_direction": direction,
                "profit_bnb": round(profit_bnb, 4),
                "profit_usd": round(profit_usd, 2),
                "status": "Running"
            })
        time.sleep(30)

# HTML template
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto Arbitrage Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; margin: 20px; }
        h1 { color: #333; text-align: center; }
        table { width: 50%; margin: 20px auto; border-collapse: collapse; background-color: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .profit { color: green; font-weight: bold; }
        .no-profit { color: red; }
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <h1>Crypto Arbitrage Bot</h1>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Last Updated</td><td>{{ data.timestamp }}</td></tr>
        <tr><td>ETH/BNB Rate</td><td>{{ data.eth_bnb_rate }}</td></tr>
        <tr><td>Uniswap ETH/BTC</td><td>{{ data.uniswap_eth_btc }}</td></tr>
        <tr><td>Uniswap Price (BNB/BTC)</td><td>{{ data.uniswap_bnb_btc }}</td></tr>
        <tr><td>PancakeSwap Price (BNB/BTC)</td><td>{{ data.pancakeswap_bnb_btc }}</td></tr>
        <tr><td>Investment</td><td>$1000 USD = {{ data.btc_amount }} BTC</td></tr>
        <tr><td>Profit Direction</td><td>{{ data.profit_direction }}</td></tr>
        <tr><td>Profit (after 0.3% fees)</td><td class="{% if data.profit_bnb > 0 %}profit{% else %}no-profit{% endif %}">{{ data.profit_bnb }} BNB ≈ ${{ data.profit_usd }} USD</td></tr>
        <tr><td>Status</td><td>{{ data.status }}</td></tr>
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_template, data=bot_data)

if __name__ == "__main__":
    print("Starting DEX Arbitrage Bot...")
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    app.run(host="0.0.0.0", port=5000)