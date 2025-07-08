import requests
import os
import config

BASE_URL = "https://coinswitch.co"
API_KEY = os.getenv("COINSWITCH_API_KEY", config.API_KEY)
API_SECRET = os.getenv("COINSWITCH_API_SECRET", config.API_SECRET)

headers = {
    'Content-Type': 'application/json',
    'X-AUTH-APIKEY': API_KEY or 'demo',
}

def test_rest_routes():
    print("\n--- Testing REST API routes ---\n")
    # 1. Spot ticker
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/24hr/ticker", params={"exchange": "coinswitchx", "symbol": "BTC/INR"}, headers=headers)
        print("Spot ticker:", r.status_code, r.text[:200])
    except Exception as e:
        print("Spot ticker ERROR:", e)
    # 2. Spot order book
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/depth", params={"exchange": "coinswitchx", "symbol": "BTC/INR"}, headers=headers)
        print("Spot order book:", r.status_code, r.text[:200])
    except Exception as e:
        print("Spot order book ERROR:", e)
    # 3. Spot trades
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/trades", params={"exchange": "coinswitchx", "symbol": "BTC/INR"}, headers=headers)
        print("Spot trades:", r.status_code, r.text[:200])
    except Exception as e:
        print("Spot trades ERROR:", e)
    # 4. Futures ticker
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/futures/ticker", params={"exchange": "EXCHANGE_2", "symbol": "BTCUSDT"}, headers=headers)
        print("Futures ticker:", r.status_code, r.text[:200])
    except Exception as e:
        print("Futures ticker ERROR:", e)
    # 5. Futures order book
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/futures/order_book", params={"exchange": "EXCHANGE_2", "symbol": "BTCUSDT"}, headers=headers)
        print("Futures order book:", r.status_code, r.text[:200])
    except Exception as e:
        print("Futures order book ERROR:", e)
    # 6. Futures trades
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/futures/trades", params={"exchange": "EXCHANGE_2", "symbol": "BTCUSDT"}, headers=headers)
        print("Futures trades:", r.status_code, r.text[:200])
    except Exception as e:
        print("Futures trades ERROR:", e)
    # 7. Account balance
    try:
        r = requests.get(f"{BASE_URL}/trade/api/v2/user/portfolio", headers=headers)
        print("Account balance:", r.status_code, r.text[:200])
    except Exception as e:
        print("Account balance ERROR:", e)
    print("\n--- Done ---\n")

if __name__ == "__main__":
    test_rest_routes()
