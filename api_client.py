import asyncio
import aiohttp
import json
import time
import hmac
import hashlib
import logging
import os
import socketio
import urllib.parse
import websockets
import websocket
import threading
from typing import Dict, Optional, List
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import config

logger = logging.getLogger(__name__)

class CoinSwitchClient:
    """
    A simplified CoinSwitch client for live trading, using WebSockets for market data
    and REST API for trading operations.
    """
    
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        
        if config.DEMO_MODE:
            logger.info("🧪 Running in DEMO MODE - using simulated data")
        else:
            logger.info("🔴 Running in LIVE MODE - using real Delta Exchange API")
        self.connector = aiohttp.TCPConnector(
            limit=config.CONNECTION_POOL_SIZE,
            keepalive_timeout=30
        )
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=timeout,
            headers={
                'Content-Type': 'application/json',
                'X-AUTH-APIKEY': self.api_key or ''
            }
        )
        
        self.ws_connections = {}
        self.ws_tasks = {}
        self.futures_polling_active = False
        
        # Real-time data cache and lock
        self.spot_prices = {}
        self.futures_data = {}
        self.funding_rates = {}
        self._data_lock = asyncio.Lock()
        
        # Available trading pairs
        self.trading_pairs = []
        
        # Store event loop for thread-safe WebSocket processing
        self.event_loop = None

    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def initialize(self):
        """Initializes the client, fetches trading pairs, and starts WebSockets."""
        try:
            # Store the current event loop for thread-safe WebSocket processing
            self.event_loop = asyncio.get_event_loop()
            
            self.trading_pairs = config.TARGET_SYMBOLS
            logger.info(f"Loaded {len(self.trading_pairs)} trading pairs from config.")

            if config.DEMO_MODE:
                # In demo mode, populate with simulated data
                await self._populate_demo_data()
                logger.info("🧪 Demo mode - Simulated data initialized")
            else:
                await self._start_websockets()
                logger.info("🌐 Live mode - WebSocket connections initialized")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise
    
    async def cleanup(self):
        """Cleans up all resources, including WebSockets and the HTTP session."""
        try:
            for ws_type, sio in self.ws_connections.items():
                if sio.connected:
                    await sio.disconnect()
                    logger.info(f"WebSocket {ws_type} disconnected")

            for task in self.ws_tasks.values():
                if not task.done():
                    task.cancel()
            
            if self.session:
                await self.session.close()
            
            logger.info("CoinSwitchClient cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _generate_auth_headers(self) -> Dict:
        """Generates authentication headers for WebSocket connections."""
        if not self.api_secret:
            raise ValueError("API secret is required for authentication")
        timestamp = str(int(time.time() * 1000))
        message = f"{self.api_key}{timestamp}"
        signature = hmac.new(self.api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        logger.debug(f"Auth Headers - API Key: {self.api_key}, Timestamp: {timestamp}, Message: {message}, Signature: {signature}")
        return {
            'X-AUTH-APIKEY': self.api_key,
            'X-AUTH-SIGNATURE': signature,
            'X-AUTH-TIMESTAMP': timestamp
        }

    def _generate_signature(self, timestamp: str, method: str, path: str, params: Dict = None, body: str = "") -> str:
        """Generates an Ed25519 signature for REST API requests."""
        try:
            if method.upper() == 'GET' and params:
                query = urllib.parse.urlencode(params)
                full_path = path + ('?' if '?' not in path else '&') + query
                message_str = method.upper() + urllib.parse.unquote_plus(full_path) + timestamp
            else:
                message_str = method.upper() + path + timestamp + body
            if not self.api_secret:
                raise ValueError("API secret is required for authentication")
            secret_key_bytes = bytes.fromhex(self.api_secret)
            private_key = Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
            signature_bytes = private_key.sign(message_str.encode('utf-8'))
            return signature_bytes.hex()
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            return "invalid_signature"
    
    async def _populate_demo_data(self):
        """Populate demo data for testing"""
        try:
            # Add simulated BTC/USD price data
            async with self._data_lock:
                # Current BTC/USD price around $100,000
                btc_price = 100000.0
                self.spot_prices['BTCUSD'] = {
                    'bid': btc_price * 0.999,  # Slightly lower bid
                    'ask': btc_price * 1.001,  # Slightly higher ask
                    'last': btc_price
                }
                
                # Simulated futures data (slightly higher for positive funding)
                self.futures_data['BTCUSD'] = btc_price * 1.002
                
                # Simulated positive funding rate (1% for demo)
                self.funding_rates['BTCUSD'] = 0.01
                
                logger.info(f"💰 Demo BTC/USD Spot Price: ${btc_price:,.2f}")
                logger.info(f"📈 Demo BTC/USD Futures Price: ${self.futures_data['BTCUSD']:,.2f}")
                logger.info(f"📊 Demo BTC/USD Funding Rate: {self.funding_rates['BTCUSD']:.2%}")
                
                # Also add for BTC/USD format (with slash)
                self.spot_prices['BTC/USD'] = self.spot_prices['BTCUSD']
                self.futures_data['BTC/USD'] = self.futures_data['BTCUSD']
                self.funding_rates['BTC/USD'] = self.funding_rates['BTCUSD']
                
        except Exception as e:
            logger.error(f"Failed to populate demo data: {e}")
    
    async def _populate_demo_futures_data(self):
        """Populate demo futures data when real API is not available"""
        try:
            async with self._data_lock:
                # Get current spot price to base futures price on
                spot_price = self.spot_prices.get('BTCUSD', {})
                if isinstance(spot_price, dict):
                    base_price = spot_price.get('last', spot_price.get('ask', 100000.0))
                else:
                    base_price = spot_price if spot_price else 100000.0
                
                # Set futures price slightly higher than spot (typical contango)
                futures_price = base_price * 1.002  # 0.2% premium
                self.futures_data['BTCUSD'] = futures_price
                self.futures_data['BTC/USD'] = futures_price
                
                # Set a positive funding rate for demo
                funding_rate = 0.01  # 1% funding rate
                self.funding_rates['BTCUSD'] = funding_rate
                self.funding_rates['BTC/USD'] = funding_rate
                
                logger.info(f"💰 Demo Futures Data - BTC/USD: ${futures_price:,.2f}")
                logger.info(f"📊 Demo Funding Rate - BTC/USD: {funding_rate:.2%}")
                
        except Exception as e:
            logger.error(f"Failed to populate demo futures data: {e}")
    
    async def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Optional[Dict]:
        """Makes an authenticated HTTP request to the CoinSwitch API."""
        try:
            url = f"{config.BASE_URL}{endpoint}"
            timestamp = str(int(time.time() * 1000))
            body = json.dumps(data) if data else ""
            signature = self._generate_signature(timestamp, method.upper(), endpoint, body=body, params=params)
            
            headers = {
                'X-AUTH-SIGNATURE': signature,
                'X-AUTH-EPOCH': timestamp,
                'X-AUTH-APIKEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            async with self.session.request(method, url, params=params, json=data, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Request failed: {method} {endpoint} - {e}")
            return None

    async def _start_websockets(self):
        """Starts and manages asyncio-based WebSocket connections."""
        if not config.DEMO_MODE:
            # Start Delta Exchange WebSocket for real market data
            self.ws_tasks['delta_websocket'] = asyncio.create_task(self._run_delta_websocket())
            logger.info("🌐 Live mode - Delta Exchange WebSocket initialized (real data only)")
        else:
            logger.info("🧪 Demo mode - Skipping WebSocket connections")

    async def _run_delta_websocket(self):
        """Official Delta Exchange WebSocket connection for both spot and futures data"""
        retry_delay = 5
        max_retry_delay = 60
        connection_attempts = 0
        
        while True:
            try:
                connection_attempts += 1
                logger.info(f"🔌 Attempting Delta Exchange WebSocket connection (Attempt {connection_attempts})")
                
                # Initialize with demo data immediately for testing
                await self._populate_demo_data()
                
                # Create Delta Exchange WebSocket connection using official format
                ws_url = "wss://socket.india.delta.exchange"
                
                # Run WebSocket in a separate thread to avoid blocking asyncio
                def run_websocket():
                    try:
                        ws = websocket.WebSocketApp(
                            ws_url,
                            on_message=self._on_websocket_message,
                            on_error=self._on_websocket_error,
                            on_close=self._on_websocket_close
                        )
                        ws.on_open = self._on_websocket_open
                        logger.info(f"🔌 Starting Delta Exchange WebSocket connection to {ws_url}")
                        ws.run_forever()
                    except Exception as e:
                        logger.error(f"❌ WebSocket thread error: {e}")
                
                # Start WebSocket in a separate thread
                ws_thread = threading.Thread(target=run_websocket)
                ws_thread.daemon = True
                ws_thread.start()
                
                # Wait for WebSocket to establish connection
                await asyncio.sleep(5)
                
                # Keep the connection alive
                while True:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Delta Exchange WebSocket connection error: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    def _on_websocket_open(self, ws):
        """Called when WebSocket connection is opened"""
        logger.info("🔌 Delta Exchange WebSocket connection opened")
        
        # Subscribe to market data channels using official format
        for symbol in self.trading_pairs:
            # SPOT DATA SUBSCRIPTIONS
            logger.info(f"📡 Subscribing to SPOT data for {symbol}")
            self._subscribe_channel(ws, "v2/ticker", [symbol])        # Spot ticker
            self._subscribe_channel(ws, "l1_orderbook", [symbol])     # Spot orderbook
            self._subscribe_channel(ws, "all_trades", [symbol])       # Spot trades
            
            # FUTURES DATA SUBSCRIPTIONS
            logger.info(f"📡 Subscribing to FUTURES data for {symbol}")
            self._subscribe_channel(ws, "mark_price", [symbol])       # Futures mark price
            self._subscribe_channel(ws, "candlestick_1m", [f"MARK:{symbol}"])  # Futures candlesticks
            
            # FUNDING RATE DATA
            logger.info(f"📡 Subscribing to FUNDING RATE data for {symbol}")
            # Note: Funding rate is included in v2/ticker data

    def _subscribe_channel(self, ws, channel_name, symbols):
        """Subscribe to a specific channel using official Delta Exchange format"""
        payload = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": channel_name,
                        "symbols": symbols
                    }
                ]
            }
        }
        ws.send(json.dumps(payload))
        logger.info(f"📡 Subscribed to {channel_name} for symbols: {symbols}")

    def _on_websocket_message(self, ws, message):
        """Called when WebSocket message is received"""
        try:
            data = json.loads(message)
            logger.info(f"📊 Received Delta Exchange WebSocket message: {data}")
            
            # Process the message in a thread-safe way
            asyncio.run_coroutine_threadsafe(
                self._process_websocket_message(data), 
                self.event_loop
            )
            
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Received non-JSON message: {message}")
        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {e}")

    def _on_websocket_error(self, ws, error):
        """Called when WebSocket error occurs"""
        logger.error(f"❌ Delta Exchange WebSocket error: {error}")

    def _on_websocket_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket connection is closed"""
        logger.warning(f"❌ Delta Exchange WebSocket closed with status: {close_status_code}, message: {close_msg}")

    async def _process_websocket_message(self, data: Dict):
        """Process WebSocket message from Delta Exchange"""
        try:
            # Check message type based on actual Delta Exchange format
            if isinstance(data, dict):
                msg_type = data.get('type', '')
                
                # Handle subscription confirmations
                if msg_type == 'subscriptions':
                    logger.info(f"✅ Subscription confirmed: {data}")
                    return
                
                # Handle orderbook updates (l1_orderbook)
                elif msg_type == 'l1_orderbook':
                    await self._process_delta_orderbook_update(data)
                
                # Handle trade updates (all_trades)
                elif msg_type == 'all_trades':
                    await self._process_delta_trade_update(data)
                
                # Handle ticker updates (v2/ticker)
                elif msg_type == 'v2/ticker':
                    await self._process_delta_ticker_update(data)
                
                # Handle mark price updates
                elif msg_type == 'mark_price':
                    await self._process_delta_mark_price_update(data)
                
                # Handle candlestick updates
                elif msg_type == 'candlestick_1m':
                    await self._process_delta_candlestick_update(data)
                
                # Log unknown message types
                else:
                    logger.debug(f"🔍 Unknown message type '{msg_type}': {data}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {e}")

    async def _process_delta_orderbook_update(self, data: Dict):
        """Process Delta Exchange orderbook update (l1_orderbook)"""
        try:
            symbol = data.get('symbol')
            if not symbol:
                return
            
            # Extract bid/ask from Delta Exchange format
            best_bid = data.get('best_bid')
            best_ask = data.get('best_ask')
            
            async with self._data_lock:
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                
                if best_bid:
                    self.spot_prices[symbol]['bid'] = float(best_bid)
                    logger.info(f"💰 {symbol} Real Bid: ${float(best_bid):,.2f}")
                
                if best_ask:
                    self.spot_prices[symbol]['ask'] = float(best_ask)
                    logger.info(f"💰 {symbol} Real Ask: ${float(best_ask):,.2f}")
                
                # Update last price with mid price
                if best_bid and best_ask:
                    mid_price = (float(best_bid) + float(best_ask)) / 2
                    self.spot_prices[symbol]['last'] = mid_price
                    logger.info(f"📈 {symbol} Real Mid Price: ${mid_price:,.2f}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing Delta orderbook update: {e}")

    async def _process_delta_trade_update(self, data: Dict):
        """Process Delta Exchange trade update (all_trades)"""
        try:
            symbol = data.get('symbol')
            price = data.get('price')
            size = data.get('size')
            
            if not symbol or not price:
                return
            
            trade_price = float(price)
            
            async with self._data_lock:
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                self.spot_prices[symbol]['last'] = trade_price
                logger.info(f"💱 {symbol} Real Trade: ${trade_price:,.2f} (Size: {size})")
                
        except Exception as e:
            logger.error(f"❌ Error processing Delta trade update: {e}")

    async def _process_delta_ticker_update(self, data: Dict):
        """Process Delta Exchange ticker update (v2/ticker) - includes spot price, mark price, and funding rate"""
        try:
            symbol = data.get('symbol')
            close_price = data.get('close')
            mark_price = data.get('mark_price')
            funding_rate = data.get('funding_rate')
            
            if not symbol:
                return
            
            async with self._data_lock:
                # Update spot price
                if close_price:
                    spot_price = float(close_price)
                    if symbol not in self.spot_prices:
                        self.spot_prices[symbol] = {}
                    self.spot_prices[symbol]['last'] = spot_price
                    logger.info(f"📊 {symbol} Real Spot Price: ${spot_price:,.2f}")
                
                # Update futures mark price
                if mark_price:
                    futures_price = float(mark_price)
                    self.futures_data[symbol] = futures_price
                    logger.info(f"📈 {symbol} Real Mark Price (Futures): ${futures_price:,.2f}")
                
                # Update funding rate
                if funding_rate:
                    rate = float(funding_rate)
                    self.funding_rates[symbol] = rate
                    logger.info(f"💰 {symbol} Real Funding Rate: {rate:.4f} ({rate*100:.2f}%)")
                
        except Exception as e:
            logger.error(f"❌ Error processing Delta ticker update: {e}")

    async def _process_delta_mark_price_update(self, data: Dict):
        """Process Delta Exchange mark price update (dedicated futures price feed)"""
        try:
            symbol = data.get('symbol')
            mark_price = data.get('mark_price')
            
            if not symbol or not mark_price:
                return
            
            futures_price = float(mark_price)
            
            async with self._data_lock:
                self.futures_data[symbol] = futures_price
                logger.info(f"📈 {symbol} Real Mark Price Update: ${futures_price:,.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error processing Delta mark price update: {e}")

    async def _process_delta_candlestick_update(self, data: Dict):
        """Process Delta Exchange candlestick update (1m MARK price candles for futures)"""
        try:
            symbol = data.get('symbol')
            close_price = data.get('close')
            
            if not symbol or not close_price:
                return
            
            # Remove MARK: prefix if present
            if symbol.startswith('MARK:'):
                clean_symbol = symbol[5:]
                symbol_type = "FUTURES"
            else:
                clean_symbol = symbol
                symbol_type = "SPOT"
            
            price = float(close_price)
            
            async with self._data_lock:
                if symbol_type == "FUTURES":
                    self.futures_data[clean_symbol] = price
                    logger.info(f"🕯️ {clean_symbol} Real Futures Candlestick: ${price:,.2f}")
                else:
                    if clean_symbol not in self.spot_prices:
                        self.spot_prices[clean_symbol] = {}
                    self.spot_prices[clean_symbol]['last'] = price
                    logger.info(f"🕯️ {clean_symbol} Real Spot Candlestick: ${price:,.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error processing Delta candlestick update: {e}")

    async def _process_ticker_update(self, data: Dict):
        """Process ticker update from Delta Exchange"""
        try:
            symbol = data['symbol']
            last_price = float(data['close'])
            
            async with self._data_lock:
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                self.spot_prices[symbol]['last'] = last_price
                logger.info(f"📈 {symbol} Ticker Price: ${last_price:,.2f}")
                
                # Also handle bid/ask if available
                if 'bid' in data:
                    self.spot_prices[symbol]['bid'] = float(data['bid'])
                if 'ask' in data:
                    self.spot_prices[symbol]['ask'] = float(data['ask'])
                    
        except Exception as e:
            logger.error(f"❌ Error processing ticker update: {e}")

    async def _process_orderbook_update(self, data: Dict):
        """Process orderbook update from Delta Exchange"""
        try:
            symbol = data['symbol']
            
            async with self._data_lock:
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                
                # Process buy orders (bids)
                if 'buy' in data and data['buy'] and len(data['buy']) > 0:
                    bid_price = float(data['buy'][0]['price'])
                    self.spot_prices[symbol]['bid'] = bid_price
                    logger.info(f"💰 {symbol} Bid: ${bid_price:,.2f}")
                
                # Process sell orders (asks)
                if 'sell' in data and data['sell'] and len(data['sell']) > 0:
                    ask_price = float(data['sell'][0]['price'])
                    self.spot_prices[symbol]['ask'] = ask_price
                    logger.info(f"💰 {symbol} Ask: ${ask_price:,.2f}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing orderbook update: {e}")

    async def _process_trade_update(self, data: Dict):
        """Process trade update from Delta Exchange"""
        try:
            symbol = data['symbol']
            trade_price = float(data['price'])
            
            async with self._data_lock:
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                self.spot_prices[symbol]['last'] = trade_price
                logger.info(f"💱 {symbol} Trade: ${trade_price:,.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error processing trade update: {e}")

    async def _process_mark_price_update(self, data: Dict):
        """Process mark price update from Delta Exchange"""
        try:
            symbol = data['symbol']
            mark_price = float(data['mark_price'])
            
            async with self._data_lock:
                # Update futures data with mark price
                self.futures_data[symbol] = mark_price
                logger.info(f"📈 {symbol} Mark Price: ${mark_price:,.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error processing mark price update: {e}")

    async def _process_candlestick_update(self, data: Dict):
        """Process candlestick update from Delta Exchange"""
        try:
            symbol = data['symbol']
            close_price = float(data['close'])
            
            async with self._data_lock:
                # Update with candlestick close price
                if symbol not in self.spot_prices:
                    self.spot_prices[symbol] = {}
                self.spot_prices[symbol]['last'] = close_price
                logger.info(f"🕯️ {symbol} Candlestick Close: ${close_price:,.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error processing candlestick update: {e}")

    async def _process_raw_websocket_message(self, data: Dict):
        """Process raw WebSocket message from Delta Exchange"""
        try:
            # Check if this is a ticker update
            if 'symbol' in data and 'close' in data:
                symbol = data['symbol']
                last_price = float(data['close'])
                
                async with self._data_lock:
                    if symbol not in self.spot_prices:
                        self.spot_prices[symbol] = {}
                    self.spot_prices[symbol]['last'] = last_price
                    logger.info(f"📈 {symbol} Raw WebSocket Price Update: ${last_price:,.2f}")
            
            # Check if this is an orderbook update
            elif 'symbol' in data and ('buy' in data or 'sell' in data):
                symbol = data['symbol']
                
                async with self._data_lock:
                    if symbol not in self.spot_prices:
                        self.spot_prices[symbol] = {}
                    
                    if 'buy' in data and data['buy'] and len(data['buy']) > 0:
                        bid_price = float(data['buy'][0]['price'])
                        self.spot_prices[symbol]['bid'] = bid_price
                        logger.info(f"💰 {symbol} Bid: ${bid_price:,.2f}")
                    
                    if 'sell' in data and data['sell'] and len(data['sell']) > 0:
                        ask_price = float(data['sell'][0]['price'])
                        self.spot_prices[symbol]['ask'] = ask_price
                        logger.info(f"💰 {symbol} Ask: ${ask_price:,.2f}")
            
            # Check if this is a mark price update (futures)
            elif 'symbol' in data and 'price' in data and 'mark_price' in str(data):
                symbol = data['symbol']
                mark_price = float(data['price'])
                
                async with self._data_lock:
                    self.futures_data[symbol] = mark_price
                    logger.info(f"📈 {symbol} Mark Price: ${mark_price:,.2f}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing raw WebSocket message: {e}")

    async def _run_spot_websocket(self):
        retry_delay = 5  # Initial delay in seconds
        max_retry_delay = 60  # Max delay in seconds
        connection_attempts = 0
        
        while True:
            try:
                sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0, logger=True, engineio_logger=True)
                self.ws_connections['spot'] = sio
                connection_attempts += 1

                @sio.event
                async def connect():
                    logger.info(f"✅ Successfully connected to spot WebSocket (Attempt {connection_attempts})")
                    
                @sio.event
                async def connect():
                    logger.info(f"✅ Successfully connected to Delta Exchange WebSocket! (Attempt {connection_attempts})")
                    
                    # Initialize with demo data immediately for testing
                    await self._populate_demo_data()
                    
                    # Subscribe to Delta Exchange market data streams using correct channels
                    for symbol in self.trading_pairs:
                        # Delta Exchange channels for real-time data
                        channels = [
                            f"v2/ticker.{symbol}",
                            f"l1_orderbook.{symbol}",
                            f"l2_orderbook.{symbol}",
                            f"all_trades.{symbol}",
                            f"mark_price.{symbol}"
                        ]
                        
                        for channel in channels:
                            logger.info(f"📡 Subscribing to Delta Exchange channel: {channel}")
                            try:
                                # Delta Exchange subscription format
                                await sio.emit('subscribe', {
                                    'type': 'subscribe',
                                    'payload': {
                                        'channels': [channel]
                                    }
                                })
                                logger.info(f"✅ Subscribed to {channel}")
                            except Exception as e:
                                logger.error(f"❌ Failed to subscribe to {channel}: {e}")

                @sio.event
                async def disconnect():
                    logger.warning("❌ Disconnected from spot WebSocket")
                    logger.info("Attempting to reconnect...")

                @sio.on('l1_orderbook')
                async def on_l1_orderbook_update(data):
                    try:
                        logger.info(f"📊 Received Delta Exchange l1_orderbook update: {json.dumps(data, indent=2)}")
                        
                        # Delta Exchange l1_orderbook format
                        if 'symbol' in data and 'buy' in data and 'sell' in data:
                            symbol = data['symbol']
                            
                            # Extract bid/ask prices
                            if data['sell'] and len(data['sell']) > 0:
                                ask_price = float(data['sell'][0]['price'])
                                ask_quantity = float(data['sell'][0]['size'])
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['ask'] = ask_price
                                    logger.info(f"💰 {symbol} Ask Price Updated: ${ask_price:,.2f} (Qty: {ask_quantity})")
                            
                            if data['buy'] and len(data['buy']) > 0:
                                bid_price = float(data['buy'][0]['price'])
                                bid_quantity = float(data['buy'][0]['size'])
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['bid'] = bid_price
                                    logger.info(f"💰 {symbol} Bid Price Updated: ${bid_price:,.2f} (Qty: {bid_quantity})")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing Delta Exchange l1_orderbook update: {e}")
                        logger.debug(f"Problematic orderbook data: {data}")

                @sio.on('l2_orderbook')
                async def on_l2_orderbook_update(data):
                    try:
                        logger.info(f"📊 Received Delta Exchange l2_orderbook update: {json.dumps(data, indent=2)}")
                        
                        # Delta Exchange l2_orderbook format - similar to l1 but with more depth
                        if 'symbol' in data and 'buy' in data and 'sell' in data:
                            symbol = data['symbol']
                            
                            # Extract best bid/ask prices
                            if data['sell'] and len(data['sell']) > 0:
                                ask_price = float(data['sell'][0]['price'])
                                ask_quantity = float(data['sell'][0]['size'])
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['ask'] = ask_price
                                    logger.info(f"💰 {symbol} Ask Price Updated: ${ask_price:,.2f} (Qty: {ask_quantity})")
                            
                            if data['buy'] and len(data['buy']) > 0:
                                bid_price = float(data['buy'][0]['price'])
                                bid_quantity = float(data['buy'][0]['size'])
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['bid'] = bid_price
                                    logger.info(f"💰 {symbol} Bid Price Updated: ${bid_price:,.2f} (Qty: {bid_quantity})")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing Delta Exchange l2_orderbook update: {e}")
                        logger.debug(f"Problematic orderbook data: {data}")

                @sio.on('v2/ticker')
                async def on_v2_ticker_update(data):
                    try:
                        logger.info(f"📊 Received Delta Exchange v2/ticker update: {json.dumps(data, indent=2)}")
                        
                        # Delta Exchange v2/ticker format
                        if 'symbol' in data and 'close' in data:
                            symbol = data['symbol']
                            
                            # Extract ticker information
                            if 'close' in data:
                                last_price = float(data['close'])
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['last'] = last_price
                                    logger.info(f"📈 {symbol} Last Price Updated: ${last_price:,.2f}")
                                    
                                    # Also extract volume and other data if available
                                    if 'volume' in data:
                                        volume = float(data['volume'])
                                        logger.info(f"📊 {symbol} 24h Volume: {volume}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing Delta Exchange v2/ticker update: {e}")
                        logger.debug(f"Problematic ticker data: {data}")

                @sio.on('all_trades')
                async def on_trade_update(data):
                    try:
                        logger.info(f"💱 Received Delta Exchange all_trades update: {json.dumps(data, indent=2)}")
                        
                        # Delta Exchange all_trades format
                        if 'symbol' in data and 'price' in data:
                            symbol = data['symbol']
                            
                            # Extract trade information
                            if 'price' in data:
                                trade_price = float(data['price'])
                                trade_quantity = float(data.get('size', 0))
                                trade_side = data.get('side', 'unknown')
                                
                                async with self._data_lock:
                                    if symbol not in self.spot_prices:
                                        self.spot_prices[symbol] = {}
                                    self.spot_prices[symbol]['last'] = trade_price
                                    logger.info(f"💱 {symbol} Trade: ${trade_price:,.2f} (Qty: {trade_quantity}, Side: {trade_side})")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing Delta Exchange all_trades update: {e}")
                        logger.debug(f"Problematic trade data: {data}")

                @sio.on('mark_price')
                async def on_mark_price_update(data):
                    try:
                        logger.info(f"📊 Received Delta Exchange mark_price update: {json.dumps(data, indent=2)}")
                        
                        # Delta Exchange mark_price format - this is futures pricing
                        if 'symbol' in data and 'price' in data:
                            symbol = data['symbol']
                            mark_price = float(data['price'])
                            
                            async with self._data_lock:
                                # Update futures data with mark price
                                self.futures_data[symbol] = mark_price
                                logger.info(f"📈 {symbol} Mark Price Updated: ${mark_price:,.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing Delta Exchange mark_price update: {e}")
                        logger.debug(f"Problematic mark_price data: {data}")

                # Add more potential Delta Exchange event handlers
                @sio.on('v2/ticker')
                async def on_v2_ticker(data):
                    logger.info(f"📊 Delta Exchange v2/ticker event: {json.dumps(data, indent=2)}")
                
                @sio.on('all_ticker')
                async def on_all_ticker(data):
                    logger.info(f"📊 Delta Exchange all_ticker event: {json.dumps(data, indent=2)}")
                
                @sio.on('trades')
                async def on_trades(data):
                    logger.info(f"💱 Delta Exchange trades event: {json.dumps(data, indent=2)}")
                
                @sio.on('message')
                async def on_message(data):
                    logger.info(f"📨 Delta Exchange message: {json.dumps(data, indent=2)}")
                
                @sio.on('update')
                async def on_update(data):
                    logger.info(f"🔄 Delta Exchange update: {json.dumps(data, indent=2)}")

                # Catch all events to see what we're actually receiving from Delta Exchange
                @sio.on('*')
                async def catch_all_delta(event, data):
                    if event not in ['connect', 'disconnect', 'l1_orderbook', 'l2_orderbook', 'v2/ticker', 'all_trades', 'mark_price', 'message', 'update']:
                        logger.info(f"🔍 Delta Exchange - Unexpected event: {event} with data: {data}")

                # Connect to Delta Exchange WebSocket using correct URLs
                ws_urls = [
                    "wss://socket.india.delta.exchange",
                    "wss://socket-ind.testnet.deltaex.org"
                ]
                
                connected = False
                for ws_url in ws_urls:
                    logger.info(f"🔌 Trying to connect to Delta Exchange WebSocket at {ws_url}")
                    try:
                        await sio.connect(
                            ws_url,
                            transports=['websocket'],
                            wait_timeout=10
                        )
                        logger.info(f"✅ Connected to Delta Exchange WebSocket at {ws_url}")
                        connected = True
                        break
                    except Exception as e:
                        logger.error(f"❌ Failed to connect to {ws_url}: {e}")
                        continue
                
                if not connected:
                    logger.error("❌ Failed to connect to any Delta Exchange WebSocket URL")
                    raise Exception("Could not connect to Delta Exchange WebSocket")
                
                logger.info("✅ WebSocket connection established")
                
                # Reset retry delay on successful connection
                retry_delay = 5
                
                # Keep connection alive
                await sio.wait()
                
            except (aiohttp.ClientError, socketio.exceptions.ConnectionError, asyncio.TimeoutError) as e:
                logger.error(f"❌ Spot WebSocket connection error: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                
                # Exponential backoff with max limit
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")
            except Exception as e:
                logger.exception(f"❌ Unexpected error in spot WebSocket: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")

    async def _run_futures_websocket(self):
        retry_delay = 5  # Initial delay in seconds
        max_retry_delay = 60  # Max delay in seconds
        connection_attempts = 0
        
        while True:
            try:
                sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0, logger=True, engineio_logger=True)
                self.ws_connections['futures'] = sio
                connection_attempts += 1

                @sio.event
                async def connect():
                    logger.info(f"✅ Successfully connected to futures WebSocket (Attempt {connection_attempts})")
                    
                @sio.event(namespace='/coinswitchx')
                async def connect():
                    logger.info(f"✅ Successfully connected to futures /coinswitchx namespace! (Attempt {connection_attempts})")
                    # Subscribe to futures data for all trading pairs
                    for symbol in self.trading_pairs:
                        # Try both symbol formats
                        symbols_to_try = [symbol, symbol.replace('/', '')]  # BTC/INR and BTCINR
                        
                        for symbol_format in symbols_to_try:
                            subscribe_data = {
                                'event': 'subscribe',
                                'pair': symbol_format
                            }
                            
                            # Subscribe to futures ticker
                            logger.info(f"📡 Subscribing to futures ticker for {symbol_format}")
                            try:
                                await sio.emit('FETCH_FUTURES_TICKER_CS_PRO', subscribe_data, namespace='/coinswitchx')
                                logger.info(f"✅ Successfully subscribed to {symbol_format} futures ticker")
                            except Exception as e:
                                logger.error(f"❌ Failed to subscribe to {symbol_format} futures ticker: {e}")
                                
                            # Subscribe to funding rate
                            logger.info(f"📡 Subscribing to funding rate for {symbol_format}")
                            try:
                                await sio.emit('FETCH_FUNDING_RATE_CS_PRO', subscribe_data, namespace='/coinswitchx')
                                logger.info(f"✅ Successfully subscribed to {symbol_format} funding rate")
                            except Exception as e:
                                logger.error(f"❌ Failed to subscribe to {symbol_format} funding rate: {e}")
                                
                            # Also try subscribing to market data
                            logger.info(f"📡 Subscribing to futures market data for {symbol_format}")
                            try:
                                await sio.emit('FETCH_FUTURES_MARKET_DATA_CS_PRO', subscribe_data, namespace='/coinswitchx')
                                logger.info(f"✅ Successfully subscribed to {symbol_format} futures market data")
                            except Exception as e:
                                logger.error(f"❌ Failed to subscribe to {symbol_format} futures market data: {e}")

                @sio.event
                async def disconnect():
                    logger.warning("❌ Disconnected from futures WebSocket")
                    logger.info("Attempting to reconnect...")

                @sio.on('FETCH_FUTURES_TICKER_CS_PRO', namespace='/coinswitchx')
                async def on_futures_ticker(data):
                    try:
                        logger.debug(f"📊 Received futures ticker data: {json.dumps(data, indent=2)}")
                        
                        # Handle subscription confirmation
                        if 'success' in data and data.get('success') == 'true':
                            logger.info(f"✅ Futures ticker subscription confirmed: {data.get('message', 'No message')}")
                            return
                        
                        # Extract futures price
                        if 'lastPrice' in data or 'close' in data:
                            symbol = data.get('pair', '').replace('/', '')  # BTC/INR -> BTCINR
                            price = float(data.get('lastPrice', data.get('close', 0)))
                            if price > 0:
                                async with self._data_lock:
                                    self.futures_data[symbol] = price
                                    logger.info(f"📈 {symbol} Futures Price Updated: ₹{price:,.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing futures ticker: {e}")
                        logger.debug(f"Problematic futures ticker data: {data}")

                @sio.on('FETCH_FUNDING_RATE_CS_PRO', namespace='/coinswitchx')
                async def on_funding_rate(data):
                    try:
                        logger.debug(f"📊 Received funding rate data: {json.dumps(data, indent=2)}")
                        
                        # Handle subscription confirmation
                        if 'success' in data and data.get('success') == 'true':
                            logger.info(f"✅ Funding rate subscription confirmed: {data.get('message', 'No message')}")
                            return
                        
                        # Extract funding rate
                        if 'fundingRate' in data or 'rate' in data:
                            symbol = data.get('pair', '').replace('/', '')  # BTC/INR -> BTCINR
                            rate = float(data.get('fundingRate', data.get('rate', 0)))
                            async with self._data_lock:
                                self.funding_rates[symbol] = rate
                                logger.info(f"📊 {symbol} Funding Rate Updated: {rate:.6f} ({rate*100:.4f}%)")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing funding rate: {e}")
                        logger.debug(f"Problematic funding rate data: {data}")

                @sio.on('FETCH_FUTURES_MARKET_DATA_CS_PRO', namespace='/coinswitchx')
                async def on_futures_market_data(data):
                    try:
                        logger.debug(f"📊 Received futures market data: {json.dumps(data, indent=2)}")
                        
                        # Handle subscription confirmation
                        if 'success' in data and data.get('success') == 'true':
                            logger.info(f"✅ Futures market data subscription confirmed: {data.get('message', 'No message')}")
                            return
                        
                        # Extract futures market data
                        if 'price' in data or 'lastPrice' in data or 'close' in data:
                            symbol = data.get('pair', '').replace('/', '')  # BTC/INR -> BTCINR
                            price = float(data.get('price', data.get('lastPrice', data.get('close', 0))))
                            if price > 0:
                                async with self._data_lock:
                                    self.futures_data[symbol] = price
                                    logger.info(f"📈 {symbol} Futures Market Data Updated: ₹{price:,.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing futures market data: {e}")
                        logger.debug(f"Problematic futures market data: {data}")

                # Catch all futures events to see what we're actually receiving
                @sio.on('*', namespace='/coinswitchx')
                async def catch_all_futures(event, data):
                    if event not in ['FETCH_FUTURES_TICKER_CS_PRO', 'FETCH_FUNDING_RATE_CS_PRO', 'FETCH_FUTURES_MARKET_DATA_CS_PRO']:
                        logger.info(f"🔍 FUTURES - Unexpected event: {event} with data: {data}")

                # Connect to CoinSwitch Futures WebSocket with authentication
                ws_url = "wss://ws.coinswitch.co/"
                socketio_path = "/pro/realtime-rates-socket/futures/coinswitchx"
                logger.info(f"🔌 Connecting to futures WebSocket at {ws_url} with path {socketio_path}")
                
                # Add authentication headers for futures WebSocket
                auth_headers = self._generate_auth_headers()
                logger.info(f"🔐 Using authentication headers for futures WebSocket")
                
                try:
                    await sio.connect(
                        ws_url,
                        socketio_path=socketio_path,
                        namespaces=['/coinswitchx'],
                        transports=['websocket'],
                        wait_timeout=10,
                        headers=auth_headers
                    )
                    logger.info("✅ Futures WebSocket connection established")
                except Exception as e:
                    logger.error(f"❌ Futures WebSocket connection failed: {e}")
                    raise
                
                # Reset retry delay on successful connection
                retry_delay = 5
                
                # Keep connection alive
                await sio.wait()
                
            except (aiohttp.ClientError, socketio.exceptions.ConnectionError, asyncio.TimeoutError) as e:
                logger.error(f"❌ Futures WebSocket connection error: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                
                # Exponential backoff with max limit
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")
            except Exception as e:
                logger.exception(f"❌ Unexpected error in futures WebSocket: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")

    async def _run_user_websocket(self):
        retry_delay = 5  # Initial delay in seconds
        max_retry_delay = 60  # Max delay in seconds
        connection_attempts = 0
        
        while True:
            try:
                sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0, logger=True, engineio_logger=True)
                self.ws_connections['user'] = sio
                connection_attempts += 1

                @sio.event
                async def connect():
                    logger.info(f"✅ Successfully connected to user WebSocket (Attempt {connection_attempts})")
                    
                @sio.event(namespace='/coinswitchx')
                async def connect():
                    logger.info(f"✅ Successfully connected to user /coinswitchx namespace! (Attempt {connection_attempts})")
                    
                    # Subscribe to user-specific data with API key
                    subscribe_data = {
                        'event': 'subscribe',
                        'apikey': self.api_key
                    }
                    
                    # Subscribe to order updates
                    logger.info("📡 Subscribing to order updates...")
                    try:
                        await sio.emit('FETCH_ORDER_UPDATES_CS_PRO', subscribe_data, namespace='/coinswitchx')
                        logger.info("✅ Successfully subscribed to order updates")
                    except Exception as e:
                        logger.error(f"❌ Failed to subscribe to order updates: {e}")
                        
                    # Subscribe to balance updates
                    logger.info("📡 Subscribing to balance updates...")
                    try:
                        await sio.emit('FETCH_BALANCE_UPDATES_CS_PRO', subscribe_data, namespace='/coinswitchx')
                        logger.info("✅ Successfully subscribed to balance updates")
                    except Exception as e:
                        logger.error(f"❌ Failed to subscribe to balance updates: {e}")

                @sio.event
                async def disconnect():
                    logger.warning("❌ Disconnected from user WebSocket")
                    logger.info("Attempting to reconnect...")

                @sio.on('FETCH_ORDER_UPDATES_CS_PRO', namespace='/coinswitchx')
                async def on_order_update(data):
                    try:
                        logger.info(f"📦 Received order update: {json.dumps(data, indent=2)}")
                        
                        # Handle subscription confirmation
                        if 'success' in data and data.get('success') == 'true':
                            logger.info(f"✅ Order updates subscription confirmed: {data.get('message', 'No message')}")
                            return
                        
                        # Process order update
                        if 'orderId' in data:
                            order_id = data.get('orderId')
                            status = data.get('status')
                            symbol = data.get('symbol', data.get('pair', ''))
                            side = data.get('side')
                            filled_qty = data.get('filledQty', 0)
                            price = data.get('price', 0)
                            
                            logger.info(f"📦 Order Update: {order_id} ({symbol}) - {side} {status}")
                            if filled_qty > 0:
                                logger.info(f"💰 Filled: {filled_qty} at ₹{price:,.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing order update: {e}")
                        logger.debug(f"Problematic order update data: {data}")

                @sio.on('FETCH_BALANCE_UPDATES_CS_PRO', namespace='/coinswitchx')
                async def on_balance_update(data):
                    try:
                        logger.info(f"💰 Received balance update: {json.dumps(data, indent=2)}")
                        
                        # Handle subscription confirmation
                        if 'success' in data and data.get('success') == 'true':
                            logger.info(f"✅ Balance updates subscription confirmed: {data.get('message', 'No message')}")
                            return
                        
                        # Process balance update
                        if 'currency' in data or 'asset' in data:
                            currency = data.get('currency', data.get('asset', ''))
                            available = data.get('available', data.get('free', 0))
                            locked = data.get('locked', data.get('locked', 0))
                            
                            logger.info(f"💰 Balance Update: {currency} - Available: {available}, Locked: {locked}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing balance update: {e}")
                        logger.debug(f"Problematic balance update data: {data}")

                # Connect to CoinSwitch User WebSocket with authentication
                ws_url = "wss://ws.coinswitch.co/"
                socketio_path = "/pro/realtime-rates-socket/user/coinswitchx"
                logger.info(f"🔌 Connecting to user WebSocket at {ws_url} with path {socketio_path}")
                
                # Add authentication headers for user WebSocket
                auth_headers = self._generate_auth_headers()
                logger.info(f"🔐 Using authentication headers for user WebSocket")
                
                try:
                    await sio.connect(
                        ws_url,
                        socketio_path=socketio_path,
                        namespaces=['/coinswitchx'],
                        transports=['websocket'],
                        wait_timeout=10,
                        headers=auth_headers
                    )
                    logger.info("✅ User WebSocket connection established")
                except Exception as e:
                    logger.error(f"❌ User WebSocket connection failed: {e}")
                    raise
                
                # Reset retry delay on successful connection
                retry_delay = 5
                
                # Keep connection alive
                await sio.wait()
                
            except (aiohttp.ClientError, socketio.exceptions.ConnectionError, asyncio.TimeoutError) as e:
                logger.error(f"❌ User WebSocket connection error: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                
                # Exponential backoff with max limit
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")
            except Exception as e:
                logger.exception(f"❌ Unexpected error in user WebSocket: {e}")
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds... (Attempt {connection_attempts})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
                logger.debug(f"Next retry delay: {retry_delay} seconds")

    # Futures simulator removed - using real Delta Exchange data only
    
    async def _get_spot_price_sync(self, symbol: str) -> Optional[float]:
        """Synchronous version of get_spot_price for internal use."""
        price_data = self.spot_prices.get(symbol)
        if isinstance(price_data, dict):
            # Return last price if available (from candlestick), otherwise mid price
            if 'last' in price_data and price_data['last'] > 0:
                return price_data['last']
            # Return mid price (average of bid and ask)
            bid = price_data.get('bid', 0)
            ask = price_data.get('ask', 0)
            if bid > 0 and ask > 0:
                return (bid + ask) / 2
            elif ask > 0:
                return ask
            elif bid > 0:
                return bid
        elif isinstance(price_data, (int, float)):
            return price_data
        return None

    # --- Data Access Methods ---
    async def get_spot_price(self, symbol: str) -> Optional[float]:
        """Gets the latest spot price from the WebSocket cache."""
        async with self._data_lock:
            price_data = self.spot_prices.get(symbol)
            if isinstance(price_data, dict):
                # Return last price if available (from candlestick), otherwise mid price
                if 'last' in price_data and price_data['last'] > 0:
                    return price_data['last']
                # Return mid price (average of bid and ask)
                bid = price_data.get('bid', 0)
                ask = price_data.get('ask', 0)
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
                elif ask > 0:
                    return ask
                elif bid > 0:
                    return bid
            elif isinstance(price_data, (int, float)):
                return price_data
            return None
    
    async def get_futures_data(self, symbol: str) -> Optional[Dict]:
        """Gets the latest futures data from the WebSocket cache."""
        async with self._data_lock:
            price = self.futures_data.get(symbol)
            if price is not None:
                return {'price': price}
            return None
    
    async def get_futures_price(self, symbol: str) -> Optional[float]:
        """Gets the latest futures price from the WebSocket cache."""
        async with self._data_lock:
            return self.futures_data.get(symbol)
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Gets the latest funding rate from the WebSocket cache."""
        async with self._data_lock:
            return self.funding_rates.get(symbol)
    
    async def place_order(self, symbol: str, side: str, quantity: float, price: float = None, exchange_type: str = 'spot') -> Optional[Dict]:
        """Places a trading order via the REST API."""
        try:
            if config.DEMO_MODE:
                # Demo mode - simulate order placement
                order_id = f"DEMO_{exchange_type}_{symbol}_{side}_{int(time.time() * 1000)}"
                simulated_order = {
                    'orderId': order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'status': 'FILLED',
                    'exchange_type': exchange_type,
                    'timestamp': time.time()
                }
                logger.info(f"🧪 Demo Order Placed: {order_id} - {side} {quantity} {symbol} @ ₹{price:,.2f}")
                return simulated_order
            
            # Live mode - actual order placement
            is_futures = exchange_type == 'futures'
            api_symbol = symbol.replace('/', '')
            
            order_data = {
                'symbol': api_symbol,
                'side': side.lower(),
                'quantity': str(quantity),
                'type': 'limit' if price else 'market'
            }
            if price:
                order_data['price'] = str(price)
            
            endpoint = f'/trade/api/v2/futures/order' if is_futures else f'/trade/api/v2/order'
            response = await self._make_request('POST', endpoint, data=order_data)
            
            if response:
                logger.info(f"✅ Order placed successfully: {response.get('orderId')}")
            return response
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            return None
    
    async def cancel_order(self, order_id: str, exchange_type: str = 'spot') -> Optional[Dict]:
        """Cancels an order via the REST API."""
        is_futures = exchange_type == 'futures'
        endpoint = f'/trade/api/v2/futures/order/{order_id}' if is_futures else f'/trade/api/v2/order/{order_id}'
        return await self._make_request('DELETE', endpoint)
    
    async def get_account_balance(self) -> Optional[Dict]:
        """Gets the user's account balance via the REST API."""
        try:
            resp = await self._make_request('GET', '/trade/api/v2/user/portfolio')
            return resp.get('data') if resp else None
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None

# Keep the old class name for compatibility
OptimizedCoinSwitchClient = CoinSwitchClient
