# Simple configuration for trading bot
import os
from dotenv import load_dotenv

load_dotenv()

# API Credentials
API_KEY = os.getenv("COINSWITCH_API_KEY")
API_SECRET = os.getenv("COINSWITCH_API_SECRET")
ENVIRONMENT = os.getenv("ENVIRONMENT", "demo")  # Default to demo mode

# Demo Mode Settings
DEMO_MODE = ENVIRONMENT == "demo"
USE_MOCK_DATA = DEMO_MODE  # Use simulated data when in demo mode

# Base URLs (Updated to match official CoinSwitch Pro API documentation)
BASE_URL = "https://coinswitch.co"
SPOT_BASE_URL = "https://coinswitch.co"
FUTURES_BASE_URL = "https://coinswitch.co"

# WebSocket URLs (Updated to match official CoinSwitch Pro API documentation)
WS_SPOT_URL = "wss://ws.coinswitch.co/"
WS_FUTURES_URL = "wss://ws.coinswitch.co/"

# Connection Settings
CONNECTION_POOL_SIZE = 10
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10.0

# Trading Strategy
TARGET_SYMBOLS = ['SOL/INR']
MIN_PROFITABLE_APR = 10.0
MIN_POSITIVE_FUNDING_RATE = 0.01  # 1%
POSITION_SIZE_QUOTE = 10000.0
MAX_OPEN_POSITIONS = 3

# Risk Management
MAX_SLIPPAGE_PERCENT = 0.5
MIN_LIQUIDITY_QUOTE = 50000.0

# Validation
if not DEMO_MODE and (not API_KEY or not API_SECRET):
    raise ValueError("Please set COINSWITCH_API_KEY and COINSWITCH_API_SECRET in .env file for production mode")
