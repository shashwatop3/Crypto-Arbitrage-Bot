#!/usr/bin/env python3
"""
Simple monitoring script to check bot status and recent activity
"""

import time
import logging
import asyncio
from api_client import CoinSwitchClient
from logic_engine import ArbitrageLogicEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def monitor_bot():
    """Monitor bot activity and show current market status"""
    logger.info("🔍 Bot Monitor - Checking current status...")
    
    try:
        # Initialize components
        client = CoinSwitchClient()
        engine = ArbitrageLogicEngine(client)
        
        # Check current market data
        symbols = ['BTC/INR', 'ETH/INR', 'MATIC/INR']
        
        logger.info("📊 Current Market Status:")
        logger.info("=" * 50)
        
        for symbol in symbols:
            try:
                spot_price = await client.get_spot_price(symbol)
                futures_data = await client.get_futures_data(symbol)
                futures_price = futures_data['mark_price'] if futures_data else 0
                funding_rate = await client.get_funding_rate(symbol)
                
                spread = ((futures_price - spot_price) / spot_price) * 100
                
                logger.info(f"{symbol}:")
                logger.info(f"  Spot: ₹{spot_price:,.2f}")
                logger.info(f"  Futures: ₹{futures_price:,.2f}")
                logger.info(f"  Spread: {spread:.4f}%")
                logger.info(f"  Funding: {funding_rate:.4f}%")
                logger.info("")
                
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
        
        # Check for opportunities
        opportunities = await engine.find_arbitrage_opportunities()
        if opportunities:
            logger.info(f"🎯 Found {len(opportunities)} arbitrage opportunities!")
            for opp in opportunities:
                logger.info(f"  {opp}")
        else:
            logger.info("⏳ No profitable opportunities at current market conditions")
        
        logger.info("=" * 50)
        logger.info("✅ Monitor check completed")
        
    except Exception as e:
        logger.error(f"Monitor error: {e}")
    
    finally:
        if 'client' in locals():
            await client.cleanup()

if __name__ == "__main__":
    asyncio.run(monitor_bot())
