#!/usr/bin/env python3
"""
Test script to verify real API connection
"""

import asyncio
import logging
from api_client import CoinSwitchClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_real_api():
    """Test real API connection and data retrieval"""
    logger.info("🌐 Testing real API connection...")
    
    client = CoinSwitchClient()
    
    try:
        # Test connection
        await client.initialize()
        
        # Test API connection
        connection_ok = await client.test_connection()
        if not connection_ok:
            logger.error("❌ API connection failed")
            return False
        
        # Test account balance
        logger.info("📊 Testing account balance...")
        balance = await client.get_account_balance()
        if balance:
            logger.info(f"✓ Account balance retrieved: {balance}")
        else:
            logger.warning("⚠️ Could not retrieve account balance")
        
        # Test market data
        logger.info("📈 Testing market data...")
        for symbol in ['BTC/INR', 'ETH/INR']:
            try:
                spot_price = await client.get_spot_price(symbol)
                if spot_price:
                    logger.info(f"✓ {symbol} spot price: ₹{spot_price:,.2f}")
                else:
                    logger.warning(f"⚠️ Could not get {symbol} spot price")
                
                futures_data = await client.get_futures_data(symbol)
                if futures_data:
                    logger.info(f"✓ {symbol} futures price: ₹{futures_data['mark_price']:,.2f}")
                else:
                    logger.warning(f"⚠️ Could not get {symbol} futures data")
                
                funding_rate = await client.get_funding_rate(symbol)
                if funding_rate is not None:
                    logger.info(f"✓ {symbol} funding rate: {funding_rate:.4f}%")
                else:
                    logger.warning(f"⚠️ Could not get {symbol} funding rate")
                
                logger.info("")
                
            except Exception as e:
                logger.error(f"❌ Error testing {symbol}: {e}")
        
        logger.info("🎉 Real API test completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ API test failed: {e}")
        return False
    
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(test_real_api())
