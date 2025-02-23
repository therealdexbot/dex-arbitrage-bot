import time
import requests
from web3 import Web3
from colorama import init, Fore, Style
from datetime import datetime

init(autoreset=True)

# Connect to Ethereum network
eth_node = "https://mainnet.infura.io/v3/72b1b6ce4ced409ba27f157f9ed6b0fd"
web3_eth = Web3(Web3.HTTPProvider(eth_node))

if not web3_eth.is_connected():
    print(f"{Fore.RED}Failed to connect to Ethereum!")
    exit()

uniswap_router = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
uniswap_contract = web3_eth.eth.contract(address=uniswap_router, abi=[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}])

weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
wbtc = Web3.to_checksum_address("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599")

investment_usd = 1000  # Change this to any USD amount

def get_rates():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin&vs_currencies=usd"
        response = requests.get(url).json()
        print(f"{Fore.CYAN}API Response: {response}")
        btc_usd = response['bitcoin']['usd']
        eth_usd = response['ethereum']['usd']
        bnb_usd = response['binancecoin']['usd']
        return btc_usd, eth_usd / bnb_usd, bnb_usd
    except Exception as e:
        print(f"{Fore.RED}Error fetching rates: {e}")
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
        print(f"{Fore.CYAN}Raw amount (WETH -> WBTC): {raw_amount}")
        print(f"{Fore.CYAN}Adjusted price (WBTC per 1 ETH): {adjusted_amount:.8f}")
        return adjusted_amount
    except Exception as e:
        print(f"{Fore.RED}Error fetching price: {str(e)}")
        return None

def check_arbitrage(investment_usd):
    fee_rate = 0.003  # 0.3% DEX fee
    rates_refresh_counter = 0
    btc_usd, eth_to_bnb_rate, bnb_usd = get_rates()  # Initial fetch
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Fore.YELLOW}=== Fetching Prices at {timestamp} ===")
        
        uniswap_price_raw = get_price(web3_eth, uniswap_contract, weth, wbtc)
        
        # Refresh rates every 5 cycles (~2.5 minutes) to avoid rate limits
        rates_refresh_counter += 1
        if rates_refresh_counter >= 5:
            btc_usd, eth_to_bnb_rate, bnb_usd = get_rates()
            rates_refresh_counter = 0

        if uniswap_price_raw is None:
            print(f"{Fore.RED}Skipping due to fetch error...")
            time.sleep(30)
            continue

        uniswap_eth_per_btc = 1 / uniswap_price_raw
        uniswap_bnb_per_btc = uniswap_eth_per_btc * eth_to_bnb_rate
        pancakeswap_bnb_per_btc = btc_usd / bnb_usd  # BTC/BNB direct

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

        print(f"{Fore.GREEN}ETH/BNB Rate: {eth_to_bnb_rate:.2f}")
        print(f"{Fore.CYAN}Uniswap ETH -> WBTC (ETH/BTC): {uniswap_eth_per_btc:.2f}")
        print(f"{Fore.CYAN}Uniswap Price (BNB/BTC): {uniswap_bnb_per_btc:.2f}")
        print(f"{Fore.YELLOW}PancakeSwap Price (BNB/BTC, via CoinGecko): {pancakeswap_bnb_per_btc:.2f}")
        print(f"{Fore.WHITE}Investment: ${investment_usd:.2f} USD = {btc_amount:.6f} BTC")
        if profit_bnb > 0:
            print(f"{Fore.GREEN}Profit Direction: {direction}")
            print(f"{Fore.GREEN}Profit (after 0.3% fees): {profit_bnb:.4f} BNB ≈ ${profit_usd:.2f} USD")
        else:
            print(f"{Fore.RED}No profit right now (after 0.3% fees).")
        print(f"{Fore.YELLOW}==================================")
        time.sleep(30)  # Slower to avoid rate limits

if __name__ == "__main__":
    print(f"{Fore.GREEN}Starting DEX Arbitrage Bot...")
    check_arbitrage(investment_usd)