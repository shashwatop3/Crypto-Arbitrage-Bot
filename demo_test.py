#!/usr/bin/env python3
"""
Quick demo test of the trading bot
"""

import asyncio
import logging
import signal
import sys
from main import ArbitrageBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global bot instance for cleanup
bot = None

def signal_handler(sig, frame):
    """Handle interrupt signal"""
    logger.info("Received interrupt signal, shutting down...")
    if bot:
        asyncio.create_task(bot.cleanup())
    sys.exit(0)

async def demo_test():
    """Run a quick demo test"""
    global bot
    
    logger.info("🎭 Starting 30-second demo test...")
    
    # Create bot
    bot = ArbitrageBot()
    
    try:
        # Initialize
        await bot.initialize()
        
        # Run for 30 seconds
        bot.running = True
        
        # Check opportunities once
        logger.info("Checking for arbitrage opportunities...")
        opportunities = await bot.logic_engine.find_arbitrage_opportunities()
        
        if opportunities:
            logger.info(f"Found {len(opportunities)} opportunities:")
            for opp in opportunities:
                logger.info(f"  {opp['symbol']}: {opp.get('annualized_return', 0):.2f}% APR")
                
                # Test position sizing
                if opp.get('is_profitable'):
                    position_sizes = await bot.logic_engine.calculate_position_sizes(
                        opp['symbol'], 10000
                    )
                    logger.info(f"  Position sizing: {position_sizes}")
        else:
            logger.info("No profitable opportunities found")
        
        # Test individual API calls
        logger.info("Testing individual API calls...")
        for symbol in ['BTC/INR', 'ETH/INR']:
            spot_price = await bot.api_client.get_spot_price(symbol)
            futures_data = await bot.api_client.get_futures_data(symbol)
            funding_rate = await bot.api_client.get_funding_rate(symbol)
            
            logger.info(f"{symbol}:")
            logger.info(f"  Spot: ₹{spot_price:,.2f}")
            logger.info(f"  Futures: ₹{futures_data.get('mark_price', 0):,.2f}")
            logger.info(f"  Funding Rate: {funding_rate:.4f}% (8h)")
        
        # Test demo order placement
        logger.info("Testing demo order placement...")
        demo_order = await bot.api_client.place_order(
            symbol='BTC/INR',
            side='buy',
            quantity=0.001,
            price=4500000,
            exchange_type='spot'
        )
        logger.info(f"Demo order result: {demo_order}")
        
        logger.info("✅ Demo test completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo test failed: {e}")
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run demo
    asyncio.run(demo_test())
