# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency trading bot for funding rate arbitrage on CoinSwitch exchange. The bot identifies opportunities where futures funding rates are sufficiently high to generate profit through simultaneous spot buy and futures sell positions.

## Key Commands

### Development Setup
```bash
# Initial setup
python setup.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python test.py

# Test specific functionality
python test_socketio_subscribe.py
```

### Running the Bot
```bash
# Start bot (uses .env ENVIRONMENT setting)
python main.py

# Demo mode (safe testing with simulated data)
# Set ENVIRONMENT=demo in .env file

# Live mode (real trading)
# Set ENVIRONMENT=live in .env file
```

### Configuration
```bash
# Create environment file
cp .env.example .env
# Edit .env with your CoinSwitch API credentials
```

## Architecture

### Core Components

1. **main.py** - Main bot orchestrator with trading loop
   - `ArbitrageBot` class manages the overall bot lifecycle
   - Handles position tracking and monitoring
   - Implements 30-second opportunity checks and 60-second position monitoring

2. **api_client.py** - CoinSwitch API client
   - REST API integration for trading operations
   - WebSocket connections for real-time market data
   - Handles authentication using Ed25519 signatures
   - Connection pooling and retry logic

3. **logic_engine.py** - Arbitrage calculation engine
   - Identifies profitable funding rate opportunities
   - Calculates position sizes and profitability
   - Caches results for performance (10-second TTL)

4. **config.py** - Centralized configuration
   - API credentials and environment settings
   - Trading parameters (symbols, position sizes, risk limits)
   - WebSocket and REST API endpoints

5. **performance_utils.py** - Performance monitoring
   - `SimpleProfiler` for operation timing
   - Latency metrics collection and reporting

### Data Flow

1. **Market Data**: WebSocket feeds provide real-time spot prices, futures prices, and funding rates
2. **Opportunity Detection**: Logic engine evaluates funding rate arbitrage opportunities every 30 seconds
3. **Trade Execution**: Simultaneous spot buy and futures sell orders placed when opportunities meet criteria
4. **Position Management**: Active positions monitored and closed after funding period (8-24 hours)

### Key Configuration Parameters

- `TARGET_SYMBOLS`: Trading pairs (default: SOL/INR)
- `MIN_PROFITABLE_APR`: Minimum annual return threshold (10%)
- `POSITION_SIZE_QUOTE`: Position size in quote currency (₹10,000)
- `MAX_OPEN_POSITIONS`: Maximum concurrent positions (3)
- `MAX_SLIPPAGE_PERCENT`: Maximum acceptable slippage (0.5%)

## Environment Modes

### Demo Mode (ENVIRONMENT=demo)
- Uses simulated market data for BTC/INR
- Safe for testing without real money
- No WebSocket connections required
- Simulated prices: BTC/INR at ₹70,00,000 with 1% funding rate

### Live Mode (ENVIRONMENT=live)
- Real CoinSwitch API integration
- Requires valid API_KEY and API_SECRET
- Actual trading with real funds
- Full WebSocket market data feeds

## WebSocket Configuration

### Working WebSocket Setup
- **Base URL**: `wss://ws.coinswitch.co/`
- **Socket.IO Path**: `/pro/realtime-rates-socket/spot/coinswitchx`
- **Namespace**: `/coinswitchx`
- **Protocol**: Socket.IO v4 (NOT raw WebSocket)

### Subscription Events
- `FETCH_ORDER_BOOK_CS_PRO` - Real-time order book data
- `FETCH_CANDLESTICK_CS_PRO` - 1-minute candlestick data
- **Subscription Format**: `{"event": "subscribe", "pair": "BTC/INR"}`

### Connection Process
1. Connect to WebSocket base URL
2. Join `/coinswitchx` namespace
3. Subscribe to desired market data events
4. Handle both subscription confirmations and live data

### Implementation Notes
- WebSocket connections only active in live mode
- Automatic reconnection with exponential backoff
- Proper error handling for connection failures
- Real-time price updates stored in memory cache

## Testing

The bot includes comprehensive test coverage:
- Module import validation
- Configuration validation
- API client functionality
- Logic engine calculations
- Performance utilities

## Performance Characteristics

### Latency Optimizations
- WebSocket connections for sub-100ms market data
- Connection pooling for HTTP requests
- 10-second opportunity result caching
- Async/await throughout for non-blocking operations

### Resource Usage
- Single-threaded with asyncio
- Bounded cache sizes to prevent memory leaks
- Efficient data structures for position tracking

## Risk Management

- Position size limits per trade
- Symbol whitelist validation
- Maximum slippage protection
- Automatic position closure after funding periods
- Comprehensive error handling and logging

## Logging

- Structured logging with timestamps
- Separate log files with rotation
- Console output for monitoring
- Performance metrics logging every 5 minutes

## Development Guidelines

### Code Style
- Async/await pattern throughout
- Comprehensive error handling
- Clear docstrings for public methods
- Type hints where beneficial

### Adding New Features
- Follow existing async patterns
- Add appropriate error handling
- Update configuration in config.py
- Include tests for new functionality
- Consider performance impact on trading loop

### Common Issues
- Ensure API credentials are properly set in .env
- Check network connectivity for WebSocket feeds
- Verify trading pairs are available on CoinSwitch
- Monitor log files for detailed error information