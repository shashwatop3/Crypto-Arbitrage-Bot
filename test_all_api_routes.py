import asyncio
from api_client import CoinSwitchClient
import config

async def test_all():
    client = CoinSwitchClient()
    print("\n--- Testing CoinSwitchClient API routes ---\n")
    for symbol in config.TARGET_SYMBOLS:
        print(f"\nTesting symbol: {symbol}")
        try:
            spot = await client.get_spot_price(symbol)
            print(f"  get_spot_price: {spot}")
        except Exception as e:
            print(f"  get_spot_price ERROR: {e}")
        try:
            fut = await client.get_futures_data(symbol)
            print(f"  get_futures_data: {fut}")
        except Exception as e:
            print(f"  get_futures_data ERROR: {e}")
        try:
            fund = await client.get_funding_rate(symbol)
            print(f"  get_funding_rate: {fund}")
        except Exception as e:
            print(f"  get_funding_rate ERROR: {e}")
    try:
        bal = await client.get_account_balance()
        print(f"\nget_account_balance: {bal}")
    except Exception as e:
        print(f"get_account_balance ERROR: {e}")
    await client.cleanup()
    print("\n--- Done ---\n")

if __name__ == "__main__":
    asyncio.run(test_all())
