# Simple configuration for trading bot
import os
from token import NAME
from dotenv import load_dotenv

load_dotenv()

# API Credentials - Switch to Delta Trading
API_KEY = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")
ENVIRONMENT = os.getenv("ENVIRONMENT", "demo")  # Default to demo mode

# Demo Mode Settings
DEMO_MODE = ENVIRONMENT == "demo"
USE_MOCK_DATA = DEMO_MODE  # Use simulated data when in demo mode

# Base URLs (Updated for Delta Exchange API)
BASE_URL = "https://api.delta.exchange"
SPOT_BASE_URL = "https://api.delta.exchange"
FUTURES_BASE_URL = "https://api.delta.exchange"
NAMESPACE = "/delta"
# WebSocket URLs (Updated for Delta Exchange)
WS_URL = "wss://socket.india.delta.exchange"
WS_TESTNET_URL = "wss://socket-ind.testnet.deltaex.org"


# Connection Settings
CONNECTION_POOL_SIZE = 10
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10.0

# Trading Strategy
TARGET_SYMBOLS = ['BTCUSD']  # Delta Exchange uses BTCUSD format
MIN_PROFITABLE_APR = 10.0
MIN_POSITIVE_FUNDING_RATE = 0.01  # 1%
POSITION_SIZE_QUOTE = 10000.0
MAX_OPEN_POSITIONS = 3

# Risk Management
MAX_SLIPPAGE_PERCENT = 0.5
MIN_LIQUIDITY_QUOTE = 50000.0

# Validation
if not DEMO_MODE and (not API_KEY or not API_SECRET):
    raise ValueError("Please set DELTA_API_KEY and DELTA_API_SECRET in .env file for production mode")
