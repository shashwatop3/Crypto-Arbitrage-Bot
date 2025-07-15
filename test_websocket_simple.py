#!/usr/bin/env python3
"""
Simple WebSocket connection test for CoinSwitch API
Tests basic WebSocket connection without Socket.IO
"""

import asyncio
import logging
import json
import time
import websockets
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleWebSocketTest:
    def __init__(self):
        self.connected = False
        self.data_received = False
        self.start_time = None
        
    async def test_websocket_connection(self, test_duration=10):
        """Test basic WebSocket connection"""
        self.start_time = time.time()
        
        logger.info(f"🚀 Starting Simple WebSocket test for {test_duration} seconds...")
        
        # Test different WebSocket URLs
        test_urls = [
            "wss://ws.coinswitch.co/",
            "wss://api-trading.coinswitch.co/",
            "wss://coinswitch.co/",
            "wss://ws.coinswitch.co/pro/realtime-rates-socket/spot/",
            "wss://api-trading.coinswitch.co/pro/realtime-rates-socket/spot/"
        ]
        
        for url in test_urls:
            logger.info(f"🔌 Testing WebSocket connection to: {url}")
            
            try:
                async with websockets.connect(
                    url,
                    ping_interval=None,
                    ping_timeout=None
                ) as websocket:
                    self.connected = True
                    logger.info(f"✅ Successfully connected to: {url}")
                    
                    # Try to send a subscription message
                    subscription_messages = [
                        {
                            "event": "subscribe",
                            "pair": "BTC,INR",
                            "channel": "orderbook"
                        },
                        {
                            "method": "subscribe",
                            "params": ["btcinr@ticker"],
                            "id": 1
                        },
                        {
                            "subscribe": "btcinr@ticker"
                        }
                    ]
                    
                    for msg in subscription_messages:
                        try:
                            await websocket.send(json.dumps(msg))
                            logger.info(f"📡 Sent subscription: {msg}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to send subscription: {e}")
                    
                    # Listen for messages
                    try:
                        async for message in websocket:
                            if not self.data_received:
                                self.data_received = True
                                elapsed = time.time() - self.start_time
                                logger.info(f"🎉 First data received! (took {elapsed:.2f}s)")
                            
                            logger.info(f"📊 Received: {message}")
                            
                            # Break after test duration
                            if time.time() - self.start_time >= test_duration:
                                break
                    except Exception as e:
                        logger.warning(f"⚠️ Error receiving messages: {e}")
                    
                    return True
                    
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"❌ Connection closed: {e}")
            except websockets.exceptions.InvalidStatus as e:
                logger.warning(f"❌ Invalid status code: {e}")
            except Exception as e:
                logger.warning(f"❌ Connection failed: {e}")
        
        logger.error("❌ All WebSocket connections failed")
        return False
    
    def print_test_results(self):
        """Print test results summary"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        logger.info("=" * 50)
        logger.info("📋 SIMPLE WEBSOCKET TEST RESULTS")
        logger.info("=" * 50)
        logger.info(f"Total test time: {total_time:.2f} seconds")
        logger.info(f"Connection successful: {'✅ YES' if self.connected else '❌ NO'}")
        logger.info(f"Data received: {'✅ YES' if self.data_received else '❌ NO'}")
        
        if self.connected:
            logger.info("🎉 At least one WebSocket connection worked!")
            if self.data_received:
                logger.info("🎉 Data was successfully received!")
            else:
                logger.warning("⚠️ Connection worked but no data received")
        else:
            logger.error("❌ No WebSocket connections worked")
            
        logger.info("=" * 50)

async def main():
    """Main test function"""
    test = SimpleWebSocketTest()
    
    try:
        # Run test for 10 seconds
        success = await test.test_websocket_connection(test_duration=10)
        
        # Print results
        test.print_test_results()
        
        # Exit with appropriate code
        exit_code = 0 if success else 1
        logger.info(f"Exiting with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)