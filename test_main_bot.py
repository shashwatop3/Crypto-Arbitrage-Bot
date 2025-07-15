#!/usr/bin/env python3
"""
Test script for the main trading bot with WebSocket integration
Runs for 30 seconds then exits
"""

import asyncio
import logging
import signal
import sys
from main import ArbitrageBot, setup_logging

# Configure logging
logger = setup_logging()

class BotTester:
    def __init__(self):
        self.bot = None
        self.running = True
        
    async def run_test(self, duration=30):
        """Test the bot for specified duration"""
        logger.info(f"🧪 Starting bot test for {duration} seconds...")
        
        try:
            # Create and initialize bot
            self.bot = ArbitrageBot()
            
            # Set up signal handler for graceful shutdown
            def signal_handler(signum, frame):
                logger.info("🛑 Test interrupted by signal")
                self.running = False
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Start bot in background
            bot_task = asyncio.create_task(self.bot.start())
            
            # Wait for specified duration
            await asyncio.sleep(duration)
            
            logger.info(f"⏰ Test duration ({duration}s) completed")
            
            # Stop the bot
            if self.bot:
                self.bot.running = False
                await self.bot.cleanup()
                
            # Cancel bot task
            if not bot_task.done():
                bot_task.cancel()
                try:
                    await bot_task
                except asyncio.CancelledError:
                    pass
                    
            logger.info("✅ Bot test completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Bot test failed: {e}")
            raise
            
    async def print_bot_status(self):
        """Print current bot status"""
        if self.bot:
            status = self.bot.get_status()
            logger.info("📊 Bot Status:")
            logger.info(f"  Running: {status['running']}")
            logger.info(f"  Active Positions: {status['active_positions']}")
            logger.info(f"  Total Trades: {status['total_trades']}")
            
            # Check WebSocket connections
            if hasattr(self.bot, 'api_client') and self.bot.api_client:
                logger.info("🌐 WebSocket Status:")
                for ws_type, sio in self.bot.api_client.ws_connections.items():
                    connected = sio.connected if sio else False
                    logger.info(f"  {ws_type}: {'✅ Connected' if connected else '❌ Disconnected'}")
                    
                # Check if we have spot prices
                if hasattr(self.bot.api_client, 'spot_prices'):
                    logger.info("💰 Spot Prices:")
                    for symbol, price in self.bot.api_client.spot_prices.items():
                        logger.info(f"  {symbol}: {price}")

async def main():
    """Main test function"""
    tester = BotTester()
    
    try:
        # Run test for 30 seconds
        await tester.run_test(duration=30)
        
        # Print final status
        await tester.print_bot_status()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)