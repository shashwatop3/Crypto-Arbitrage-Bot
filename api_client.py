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
        
        logger.info(" Running in LIVE MODE - using real CoinSwitch API")
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
                'X-AUTH-APIKEY': self.api_key
            }
        )
        
        self.ws_connections = {}
        self.ws_tasks = {}
        
        # Real-time data cache and lock
        self.spot_prices = {}
        self.futures_data = {}
        self.funding_rates = {}
        self._data_lock = asyncio.Lock()
        
        # Available trading pairs
        self.trading_pairs = []

    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def initialize(self):
        """Initializes the client, fetches trading pairs, and starts WebSockets."""
        try:
            self.trading_pairs = config.TARGET_SYMBOLS
            logger.info(f"Loaded {len(self.trading_pairs)} trading pairs from config.")

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
        timestamp = str(int(time.time() * 1000))
        message = f"{self.api_key}{timestamp}"
        signature = hmac.new(self.api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
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

            secret_key_bytes = bytes.fromhex(self.api_secret)
            private_key = Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
            signature_bytes = private_key.sign(message_str.encode('utf-8'))
            return signature_bytes.hex()
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            return "invalid_signature"
    
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
        self.ws_tasks['spot'] = asyncio.create_task(self._run_spot_websocket())
        self.ws_tasks['futures'] = asyncio.create_task(self._run_futures_websocket())
        self.ws_tasks['user'] = asyncio.create_task(self._run_user_websocket())

    async def _run_spot_websocket(self):
        pass

    async def _run_futures_websocket(self):
        pass

    async def _run_user_websocket(self):
        pass

    # --- Data Access Methods ---
    async def get_spot_price(self, symbol: str) -> Optional[float]:
        """Gets the latest spot price from the WebSocket cache."""
        async with self._data_lock:
            return self.spot_prices.get(symbol)
    
    async def get_futures_data(self, symbol: str) -> Optional[Dict]:
        """Gets the latest futures data from the WebSocket cache."""
        async with self._data_lock:
            return self.futures_data.get(symbol)
    
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Gets the latest funding rate from the WebSocket cache."""
        async with self._data_lock:
            return self.funding_rates.get(symbol)
    
    async def place_order(self, symbol: str, side: str, quantity: float, price: float = None, exchange_type: str = 'spot') -> Optional[Dict]:
        """Places a trading order via the REST API."""
        try:
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
                logger.info(f"Order placed successfully: {response.get('orderId')}")
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
