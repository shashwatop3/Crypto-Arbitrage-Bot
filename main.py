import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import config
from api_client import CoinSwitchClient
from logic_engine import ArbitrageLogicEngine
from performance_utils import SimpleProfiler

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Simple position tracking"""
    trade_id: str
    symbol: str
    position_size: float
    entry_time: datetime
    entry_spot_price: float
    entry_futures_price: float
    funding_rate: float
    spot_order_id: str
    futures_order_id: str
    status: str = "ACTIVE"

@dataclass
class BotStats:
    """Simple bot statistics"""
    active_positions: int = 0
    total_trades: int = 0
    total_profit: float = 0.0
    last_update: float = 0.0

class ArbitrageBot:
    """
    Simplified arbitrage bot focused on core functionality
    """
    
    def __init__(self):
        self.running = False
        self.api_client = None
        self.logic_engine = None
        self.profiler = SimpleProfiler()
        
        # Position tracking
        self.active_positions: Dict[str, Position] = {}
        self.position_history: List[Position] = []
        
        # Simple statistics
        self.stats = BotStats()
        
        # Performance tracking
        self.last_opportunity_check = 0
        self.last_position_check = 0
    
    async def initialize(self):
        """Initialize the trading bot"""
        try:
            logger.info("Initializing Arbitrage Bot...")
            
            # Initialize API client
            self.api_client = CoinSwitchClient()
            await self.api_client.initialize()
            
            # Initialize logic engine
            self.logic_engine = ArbitrageLogicEngine(self.api_client)
            
            logger.info("✓ Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            self.running = False
            
            if self.api_client:
                await self.api_client.cleanup()
            
            logger.info("Bot cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def start(self):
        """Start the trading bot"""
        try:
            await self.initialize()
            self.running = True
            
            logger.info("🚀 Starting Arbitrage Bot")
            
            # Start main trading loop
            await self._run_trading_loop()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.cleanup()
    
    async def _run_trading_loop(self):
        """Main trading loop"""
        while self.running:
            try:
                # Check for new opportunities
                if time.time() - self.last_opportunity_check > 30:  # Check every 30 seconds
                    await self._check_opportunities()
                    self.last_opportunity_check = time.time()
                
                # Monitor existing positions
                if time.time() - self.last_position_check > 60:  # Check every minute
                    await self._monitor_positions()
                    self.last_position_check = time.time()
                
                # Update statistics
                await self._update_stats()
                
                # Short sleep to prevent busy waiting
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(10)
    
    async def _check_opportunities(self):
        """Check for arbitrage opportunities"""
        start_time = self.profiler.start_operation("opportunity_check")
        
        try:
            # Skip if we have max positions
            if len(self.active_positions) >= config.MAX_OPEN_POSITIONS:
                logger.info(f"Max positions reached ({config.MAX_OPEN_POSITIONS})")
                return
            
            # Find opportunities
            opportunities = await self.logic_engine.find_arbitrage_opportunities()
            
            if not opportunities:
                logger.debug("No profitable opportunities found")
                return
            
            logger.info(f"Found {len(opportunities)} opportunities")
            
            # Execute best opportunity
            best_opportunity = opportunities[0]
            await self._execute_arbitrage(best_opportunity)
            
        except Exception as e:
            logger.error(f"Error checking opportunities: {e}")
        finally:
            self.profiler.end_operation("opportunity_check", start_time)
    
    async def _execute_arbitrage(self, opportunity: Dict):
        """Execute an arbitrage trade"""
        start_time = self.profiler.start_operation("trade_execution")
        
        try:
            symbol = opportunity['symbol']
            
            # Final validation
            if not await self.logic_engine.validate_opportunity(opportunity):
                logger.warning(f"Opportunity validation failed for {symbol}")
                return
            
            # Calculate position sizes
            position_sizes = await self.logic_engine.calculate_position_sizes(
                symbol, config.POSITION_SIZE_QUOTE
            )
            
            if 'error' in position_sizes:
                logger.error(f"Position sizing failed: {position_sizes['error']}")
                return
            
            # Generate trade ID
            trade_id = f"ARB_{symbol.replace('/', '')}_{int(time.time())}"
            
            logger.info(f"Executing arbitrage for {symbol} (Trade ID: {trade_id})")
            
            # Place spot buy order
            spot_order = await self.api_client.place_order(
                symbol=symbol,
                side='buy',
                quantity=position_sizes['spot_quantity'],
                price=opportunity['spot_price'] * 1.001,  # Slight premium for execution
                exchange_type='spot'
            )
            
            if not spot_order:
                logger.error("Failed to place spot order")
                return
            
            # Place futures sell order
            futures_order = await self.api_client.place_order(
                symbol=symbol,
                side='sell',
                quantity=position_sizes['futures_quantity'],
                price=opportunity['futures_price'] * 0.999,  # Slight discount for execution
                exchange_type='futures'
            )
            
            if not futures_order:
                logger.error("Failed to place futures order")
                # Cancel spot order
                await self.api_client.cancel_order(spot_order['orderId'], symbol, 'spot')
                return
            
            # Create position record
            position = Position(
                trade_id=trade_id,
                symbol=symbol,
                position_size=position_sizes['spot_quantity'],
                entry_time=datetime.now(),
                entry_spot_price=opportunity['spot_price'],
                entry_futures_price=opportunity['futures_price'],
                funding_rate=opportunity['funding_rate'],
                spot_order_id=spot_order['orderId'],
                futures_order_id=futures_order['orderId']
            )
            
            self.active_positions[trade_id] = position
            logger.info(f"✓ Arbitrage position opened: {trade_id}")
            
        except Exception as e:
            logger.error(f"Error executing arbitrage: {e}")
        finally:
            self.profiler.end_operation("trade_execution", start_time)
    
    async def _monitor_positions(self):
        """Monitor existing positions"""
        start_time = self.profiler.start_operation("position_monitoring")
        
        try:
            positions_to_close = []
            
            for trade_id, position in self.active_positions.items():
                try:
                    # Check if position should be closed
                    should_close = await self._should_close_position(position)
                    
                    if should_close:
                        positions_to_close.append(trade_id)
                        
                except Exception as e:
                    logger.error(f"Error monitoring position {trade_id}: {e}")
            
            # Close positions that should be closed
            for trade_id in positions_to_close:
                await self._close_position(trade_id)
                
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
        finally:
            self.profiler.end_operation("position_monitoring", start_time)
    
    async def _should_close_position(self, position: Position) -> bool:
        """Determine if a position should be closed"""
        try:
            # Close after 8 hours (one funding period)
            time_open = datetime.now() - position.entry_time
            if time_open > timedelta(hours=24):
                logger.info(f"Position {position.trade_id} held for {time_open}, closing")
                return True
            
            # Close if funding rate becomes negative
            current_funding = await self.api_client.get_funding_rate(position.symbol)
            if current_funding is not None and current_funding < 0:
                logger.info(f"Negative funding rate for {position.trade_id}, closing")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if position should close: {e}")
            return False
    
    async def _close_position(self, trade_id: str):
        """Close an arbitrage position"""
        start_time = self.profiler.start_operation("position_closing")
        
        try:
            position = self.active_positions.get(trade_id)
            if not position:
                return
            
            logger.info(f"Closing position: {trade_id}")
            
            # Close spot position (sell)
            spot_close_order = await self.api_client.place_order(
                symbol=position.symbol,
                side='sell',
                quantity=position.position_size,
                exchange_type='spot'
            )
            
            # Close futures position (buy)
            futures_close_order = await self.api_client.place_order(
                symbol=position.symbol,
                side='buy',
                quantity=position.position_size,
                exchange_type='futures'
            )
            
            if spot_close_order and futures_close_order:
                # Mark position as closed
                position.status = "CLOSED"
                
                # Move to history
                self.position_history.append(position)
                del self.active_positions[trade_id]
                
                # Update stats
                self.stats.total_trades += 1
                
                logger.info(f"✓ Position closed: {trade_id}")
            else:
                logger.error(f"Failed to close position: {trade_id}")
                
        except Exception as e:
            logger.error(f"Error closing position {trade_id}: {e}")
        finally:
            self.profiler.end_operation("position_closing", start_time)
    
    async def _update_stats(self):
        """Update bot statistics"""
        try:
            self.stats.active_positions = len(self.active_positions)
            self.stats.last_update = time.time()
            
            # Log stats periodically
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                await self._log_performance()
                
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    async def _log_performance(self):
        """Log performance metrics"""
        try:
            logger.info("=== Bot Performance Summary ===")
            logger.info(f"Active Positions: {self.stats.active_positions}")
            logger.info(f"Total Trades: {self.stats.total_trades}")
            
            # Log profiler metrics
            for operation, metrics in self.profiler.metrics.items():
                if metrics:
                    avg_time = sum(m.duration_ms for m in metrics) / len(metrics)
                    logger.info(f"{operation}: avg {avg_time:.1f}ms ({len(metrics)} samples)")
            
            logger.info("=" * 30)
            
        except Exception as e:
            logger.error(f"Error logging performance: {e}")
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        return {
            'running': self.running,
            'active_positions': len(self.active_positions),
            'total_trades': self.stats.total_trades,
            'uptime': time.time() - (self.stats.last_update or time.time()),
            'positions': [asdict(pos) for pos in self.active_positions.values()]
        }

async def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check configuration
    if not config.API_KEY or not config.API_SECRET:
        logger.error("Please set COINSWITCH_API_KEY and COINSWITCH_API_SECRET in .env file")
        return
    
    # Create and start bot
    bot = ArbitrageBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
