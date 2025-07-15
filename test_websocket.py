#!/usr/bin/env python3
"""
WebSocket connection test for CoinSwitch API
Tests connection to CoinSwitch WebSocket and subscribes to BTC-INR market data
Runs for 10 seconds then exits
"""

import asyncio
import logging
import json
import time
import socketio
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoinSwitchWebSocketTest:
    def __init__(self):
        self.sio = None
        self.connected = False
        self.data_received = False
        self.start_time = None
        
    async def test_websocket_connection(self, test_duration=10):
        """Test WebSocket connection for specified duration"""
        self.start_time = time.time()
        
        logger.info(f"🚀 Starting WebSocket test for {test_duration} seconds...")
        logger.info("Testing BTC-INR market data connection")
        
        # Create WebSocket client
        self.sio = socketio.AsyncClient(
            reconnection=False,
            logger=True,
            engineio_logger=True
        )
        
        # Event handlers
        @self.sio.event
        async def connect():
            self.connected = True
            elapsed = time.time() - self.start_time
            logger.info(f"✅ Connected to WebSocket successfully! (took {elapsed:.2f}s)")
            
        @self.sio.event
        async def connect_error(data):
            logger.error(f"❌ Connection error: {data}")
            
        # Handle namespace connection
        @self.sio.event(namespace='/coinswitchx')
        async def connect():
            self.connected = True
            elapsed = time.time() - self.start_time
            logger.info(f"✅ Connected to /coinswitchx namespace! (took {elapsed:.2f}s)")
            
            # Subscribe to BTC-INR order book
            subscribe_data = {
                'event': 'subscribe',
                'pair': 'BTC/INR'
            }
            logger.info("📡 Subscribing to BTC-INR order book...")
            
            try:
                await self.sio.emit('FETCH_ORDER_BOOK_CS_PRO', subscribe_data, namespace='/coinswitchx')
                logger.info("✅ Successfully sent subscription request")
            except Exception as e:
                logger.error(f"❌ Failed to subscribe: {e}")
        
        @self.sio.event
        async def disconnect():
            logger.info("❌ Disconnected from WebSocket")
            self.connected = False
        
        @self.sio.event
        async def connect_error(data):
            logger.error(f"❌ Connection error: {data}")
        
        @self.sio.on('FETCH_ORDER_BOOK_CS_PRO', namespace='/coinswitchx')
        async def on_order_book(data):
            if not self.data_received:
                self.data_received = True
                elapsed = time.time() - self.start_time
                logger.info(f"🎉 First data received! (took {elapsed:.2f}s)")
            
            try:
                # Check if it's a subscription confirmation
                if 'success' in data and data.get('success') == 'true':
                    logger.info(f"✅ Subscription confirmed: {data.get('message', 'No message')}")
                    return
                
                # Parse and display order book data
                pair = data.get('pair', 'Unknown')
                
                if 'ask' in data and len(data['ask']) > 0:
                    best_ask = float(data['ask'][0][0])
                    ask_qty = float(data['ask'][0][1])
                    logger.info(f"📊 {pair} - Best Ask: ₹{best_ask:,.2f} (Qty: {ask_qty})")
                
                if 'bid' in data and len(data['bid']) > 0:
                    best_bid = float(data['bid'][0][0])
                    bid_qty = float(data['bid'][0][1])
                    logger.info(f"📊 {pair} - Best Bid: ₹{best_bid:,.2f} (Qty: {bid_qty})")
                
                # Calculate spread
                if 'ask' in data and 'bid' in data and len(data['ask']) > 0 and len(data['bid']) > 0:
                    spread = float(data['ask'][0][0]) - float(data['bid'][0][0])
                    spread_pct = (spread / float(data['bid'][0][0])) * 100
                    logger.info(f"📈 Spread: ₹{spread:,.2f} ({spread_pct:.4f}%)")
                
            except Exception as e:
                logger.error(f"❌ Error processing order book data: {e}")
                logger.debug(f"Raw data: {json.dumps(data, indent=2)}")
        
        @self.sio.on('*')
        async def catch_all(event, data):
            logger.debug(f"🔍 Received event: {event} with data: {data}")
        
        # Connect to WebSocket using the correct CoinSwitch Pro configuration
        ws_url = "wss://ws.coinswitch.co/"
        socketio_path = "/pro/realtime-rates-socket/spot/coinswitchx"
        
        logger.info(f"🔌 Connecting to: {ws_url}")
        logger.info(f"📍 Socket.IO path: {socketio_path}")
        logger.info(f"🏷️ Namespace: /coinswitchx")
        
        try:
            await self.sio.connect(
                ws_url,
                socketio_path=socketio_path,
                namespaces=['/coinswitchx'],
                transports=['websocket'],
                wait_timeout=10
            )
            logger.info("✅ Successfully connected to CoinSwitch Pro WebSocket!")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
        
        try:
            
            # Wait for test duration
            await asyncio.sleep(test_duration)
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
        
        finally:
            # Cleanup
            if self.sio and self.sio.connected:
                await self.sio.disconnect()
        
        return self.connected and self.data_received
    
    def print_test_results(self):
        """Print test results summary"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        logger.info("=" * 50)
        logger.info("📋 TEST RESULTS SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total test time: {total_time:.2f} seconds")
        logger.info(f"Connection successful: {'✅ YES' if self.connected else '❌ NO'}")
        logger.info(f"Data received: {'✅ YES' if self.data_received else '❌ NO'}")
        
        if self.connected and self.data_received:
            logger.info("🎉 TEST PASSED - WebSocket connection working correctly!")
        else:
            logger.error("❌ TEST FAILED - WebSocket connection has issues")
            
        logger.info("=" * 50)

async def main():
    """Main test function"""
    test = CoinSwitchWebSocketTest()
    
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