import asyncio
import logging
from api_client import CoinSwitchClient

# Configure basic logging
logging.basicConfig(level=logging.INFO)

async def main():
    """
    Initializes the CoinSwitchClient, allows it to run for a short period,
    and then gracefully cleans up resources.
    """
    print("Initializing client and starting WebSocket connections...")
    try:
        async with CoinSwitchClient() as client:
            print("Client initialized. Waiting for 30 seconds to monitor WebSocket activity...")
            await asyncio.sleep(30)
            print("30 seconds have passed. Shutting down.")
    except Exception as e:
        logging.error(f"An error occurred during the test: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    







