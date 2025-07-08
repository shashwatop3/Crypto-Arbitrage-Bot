import asyncio
import logging
from api_client import CoinSwitchClient
import config

# Configure logging to see output from the client
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """
    A simple test script to verify that the CoinSwitchClient is receiving
    WebSocket data for spot and futures tickers.
    """
    logger.info("--- Starting api_client test ---")
    
    client = None
    try:
        client = CoinSwitchClient()
        await client.initialize()
        
        logger.info("Client initialized. Monitoring data for 20 seconds...")
        
        for i in range(20):
            await asyncio.sleep(1)
            spot_prices = await client.get_spot_price("SOL/INR")
            futures_data = await client.get_futures_data("SOL/INR")
            
            print(f"--- Second {i+1} ---")
            if spot_prices:
                print(f"Spot Prices (SOL/INR): {spot_prices}")
            else:
                print("Spot Prices (SOL/INR): No data yet")
                
            if futures_data:
                print(f"Futures Data (SOL/INR): {futures_data}")
            else:
                print("Futures Data (SOL/INR): No data yet")
            print("-" * 20)

    except Exception as e:
        logger.error(f"An error occurred during the test: {e}")
    finally:
        if client:
            await client.cleanup()
        logger.info("--- Test finished ---")

if __name__ == "__main__":
    asyncio.run(main())
