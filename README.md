# Crypto Trading Bot - Funding Rate Arbitrage

A sophisticated cryptocurrency trading bot designed for funding rate arbitrage on the CoinSwitch exchange with robust fallback data mechanisms.

## ✨ Key Features

- **Dual Mode Operation**: Safe demo mode with simulated data + live mode with real market data
- **Robust Data Sources**: Primary CoinSwitch API with CoinGecko/Binance fallbacks
- **Smart Error Handling**: Graceful fallback when primary APIs are unavailable
- **Real-time Monitoring**: WebSocket connections for live market data
- **Risk Management**: Built-in position sizing and slippage protection
- **Performance Tracking**: Comprehensive metrics and logging

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

1. **Clone and setup:**
```bash
git clone <repository>
cd funding-rate-arbitrage-bot
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Test in demo mode:**
```bash
python test.py
python main.py  # Runs in demo mode by default
```

## 📋 Configuration

### Environment Variables (.env)
```bash
# Mode: "demo" for simulation, "live" for real trading
ENVIRONMENT=demo

# CoinSwitch API Credentials (for live mode)
COINSWITCH_API_KEY=your_api_key_here
COINSWITCH_API_SECRET=your_api_secret_here
```

### Trading Parameters (config.py)
- `TARGET_SYMBOLS`: ['BTC/INR', 'ETH/INR', 'MATIC/INR']
- `MIN_PROFITABLE_APR`: 10.0% (minimum required annual return)
- `POSITION_SIZE_QUOTE`: ₹10,000 (position size in INR)
- `MAX_SLIPPAGE_PERCENT`: 0.5% (maximum acceptable slippage)

## 📁 Project Structure

```
├── api_client.py           # API client with WebSocket support
├── logic_engine.py         # Arbitrage logic with caching
├── performance_utils.py    # Basic profiling and caching utilities
├── main.py                # Main bot implementation
├── config.py              # Configuration settings
├── requirements.txt       # Dependencies
├── setup.py               # Setup script
├── test.py               # Test suite
├── .env                  # Environment variables (create this)
└── README.md             # This file
```

## 🚀 Quick Start

1. **Setup Environment**:
   ```bash
   python setup.py
   ```

2. **Configure API Keys**:
   Create `.env` file:
   ```
   COINSWITCH_API_KEY=your_api_key
   COINSWITCH_API_SECRET=your_api_secret
   ```

3. **Run Tests**:
   ```bash
   python test.py
   ```

4. **Start Bot**:
   ```bash
   python main.py
   ```

## 🔧 Configuration

Key settings in `config.py`:

```python
# Trading Strategy
TARGET_SYMBOLS = ['BTC/INR', 'ETH/INR', 'MATIC/INR']
MIN_PROFITABLE_APR = 10.0
POSITION_SIZE_QUOTE = 10000.0
MAX_OPEN_POSITIONS = 3

# Performance
CONNECTION_POOL_SIZE = 10
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 3
```

## 📊 Performance Features Retained

### WebSocket Data Feeds
- Real-time price updates
- Automatic reconnection
- Low-latency market data

### Efficient HTTP Client
- Connection pooling
- Async requests
- Retry logic with exponential backoff

### Smart Caching
- TTL-based price caching
- Opportunity result caching
- Memory-efficient cleanup

### Position Management
- Full trade lifecycle tracking
- Automatic position closure
- Risk-based position sizing

## 🧪 Testing

The bot includes comprehensive tests:

```bash
python test.py
```

Tests cover:
- Module imports
- Configuration validation
- API client functionality
- Logic engine calculations
- Performance utilities

## ⚡ Performance Characteristics

### Latency Optimizations
- WebSocket price feeds: ~5ms latency
- HTTP requests: Connection pooling + keep-alive
- Opportunity detection: Cached results (10s TTL)
- Order execution: Parallel spot + futures placement

### Memory Usage
- Simplified data structures
- Bounded cache sizes
- No heavy computational libraries

### CPU Usage
- Single-threaded with async/await
- No thread pools or multiprocessing
- Efficient Python operations only

## 🔍 Monitoring

### Built-in Profiling
```python
# Operation timing
profiler.start_operation("trade_execution")
# ... trading logic ...
profiler.end_operation("trade_execution", start_time)
```

### Simple Statistics
- Active positions count
- Total trades executed
- Average operation times
- Basic success metrics

## 🛡️ Risk Management

### Simple but Effective
- Position size limits
- Symbol whitelist validation
- Price movement checks
- Maximum slippage protection
- Time-based position closure

## 📈 Trading Strategy

### Funding Rate Arbitrage
1. Monitor funding rates across symbols
2. Identify positive funding rate opportunities
3. Execute simultaneous spot buy + futures sell
4. Hold position for one funding period (8 hours)
5. Close position and collect funding payment

### Entry Criteria
- Funding rate > 1% (configurable)
- Expected APR > 10% (configurable)
- Sufficient liquidity available
- Risk assessment passes

## 🔄 Development

### Code Style
- Clear, readable Python code
- Minimal external dependencies
- Comprehensive error handling
- Async/await throughout

### Adding Features
- Keep functions focused and simple
- Use caching for performance-critical paths
- Maintain async patterns
- Add tests for new functionality

### Performance Tips
- Use WebSocket feeds for real-time data
- Cache frequently accessed data
- Profile operations to identify bottlenecks
- Keep position sizes reasonable

---

**Note**: This bot balances performance and simplicity, making it perfect for learning, development, and production use where maintainability is prioritized.
