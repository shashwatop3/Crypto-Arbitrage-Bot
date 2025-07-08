import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import config
import time

logger = logging.getLogger(__name__)

class ArbitrageLogicEngine:
    """
    Simplified arbitrage logic engine with essential functionality
    """
    
    def __init__(self, api_client):
        self.api_client = api_client
        self._has_started = False  # Add a flag to manage the initial startup delay
        
        # Simple caching for performance
        self.opportunity_cache = {}
        self.cache_expiry = 10  # seconds
        
        # Precomputed fee rates
        self.fee_rates = {
            'spot_maker': 0.00017,  # 0.1%
            'spot_taker': 0.00017,
            'futures_maker': 0.00017,  # 0.02%
            'futures_taker': 0.00017
        }
    
    async def calculate_profitability(self, funding_rate: float, hours_to_funding: float, 
                                    spot_price: float, futures_price: float) -> Dict:
        """Calculate profitability with simple logic"""
        try:
            # Calculate fees
            total_fees = (self.fee_rates['spot_taker'] + self.fee_rates['futures_taker']) * 2
            
            # Calculate funding payment (every 8 hours)
            funding_intervals = max(1, hours_to_funding / 8)
            expected_funding = funding_rate * funding_intervals
            
            # Net profit
            net_profit_percent = expected_funding - total_fees
            
            # Price basis (difference between futures and spot)
            basis = (futures_price - spot_price) / spot_price
            
            # Annualized return
            if hours_to_funding > 0:
                annualized_return = (net_profit_percent * 365 * 24) / hours_to_funding
            else:
                annualized_return = 0
            
            return {
                'net_profit_percent': net_profit_percent,
                'annualized_return': annualized_return,
                'funding_rate': funding_rate,
                'total_fees': total_fees,
                'basis': basis,
                'is_profitable': net_profit_percent > 0 and annualized_return > config.MIN_PROFITABLE_APR
            }
            
        except Exception as e:
            logger.error(f"Error calculating profitability: {e}")
            return {
                'net_profit_percent': 0,
                'annualized_return': 0,
                'is_profitable': False,
                'error': str(e)
            }
    
    async def assess_liquidity(self, symbol: str) -> Dict:
        """Simple liquidity assessment"""
        try:
            # Get basic ticker data
            spot_price = await self.api_client.get_spot_price(symbol)
            futures_data = await self.api_client.get_futures_data(symbol)
            
            if not spot_price or not futures_data:
                return {'is_liquid': False, 'reason': 'Missing price data'}
            
            # Simple check - assume sufficient liquidity if we have current prices
            # In a real implementation, you'd check order book depth
            return {
                'is_liquid': True,
                'spot_price': spot_price,
                'futures_price': futures_data.get('mark_price', 0),
                'estimated_liquidity': config.MIN_LIQUIDITY_QUOTE  # Simplified
            }
            
        except Exception as e:
            logger.error(f"Error assessing liquidity for {symbol}: {e}")
            return {'is_liquid': False, 'reason': str(e)}
    
    async def assess_risk(self, symbol: str, position_size: float) -> Dict:
        """Simple risk assessment"""
        try:
            # Basic risk checks
            risk_factors = []
            risk_score = 0
            
            # Check position size
            if position_size > config.POSITION_SIZE_QUOTE * 2:
                risk_factors.append('Large position size')
                risk_score += 0.3
            
            # Check if symbol is in target list
            if symbol not in self.api_client.trading_pairs:
                risk_factors.append('Symbol not in target list')
                risk_score += 0.5
            
            # Simple volatility check (would need historical data for real implementation)
            spot_price = await self.api_client.get_spot_price(symbol)
            if spot_price and spot_price < 100:  # Arbitrary threshold for demo
                risk_factors.append('Low price - high volatility risk')
                risk_score += 0.2
            
            return {
                'risk_score': min(risk_score, 1.0),
                'risk_factors': risk_factors,
                'is_acceptable': risk_score < 0.7,
                'max_position_size': config.POSITION_SIZE_QUOTE
            }
            
        except Exception as e:
            logger.error(f"Error assessing risk for {symbol}: {e}")
            return {
                'risk_score': 1.0,
                'is_acceptable': False,
                'error': str(e)
            }
    
    def _get_cache_key(self, symbol: str) -> str:
        """Generate cache key for opportunity"""
        return f"opportunity_{symbol}_{int(time.time() / self.cache_expiry)}"
    
    async def _wait_for_data(self, timeout=30):
        """Waits for the first piece of data to arrive on WebSockets."""
        logger.info("Waiting for initial market data...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.api_client.spot_prices and self.api_client.futures_data:
                logger.info("Initial market data received.")
                return True
            await asyncio.sleep(1)
        logger.warning("Timeout waiting for initial market data.")
        return False

    async def find_arbitrage_opportunities(self) -> List[Dict]:
        """Find arbitrage opportunities across all symbols"""
        if not self._has_started:
            if await self._wait_for_data():
                self._has_started = True
            else:
                logger.error("Halting due to no market data.")
                return []

        opportunities = []
        
        # Ensure we have the latest trading pairs from the client
        trading_pairs = self.api_client.trading_pairs
        if not trading_pairs:
            logger.warning("No trading pairs available in the API client to analyze.")
            return opportunities

        for symbol in trading_pairs:
            try:
                # Check cache first
                cache_key = self._get_cache_key(symbol)
                if cache_key in self.opportunity_cache:
                    cached_opp = self.opportunity_cache[cache_key]
                    if cached_opp.get('is_profitable'):
                        opportunities.append(cached_opp)
                    continue
                
                # Analyze opportunity
                opportunity = await self.analyze_symbol_opportunity(symbol)
                
                # Cache the result
                self.opportunity_cache[cache_key] = opportunity
                
                # Clean old cache entries
                if len(self.opportunity_cache) > 100:
                    oldest_keys = list(self.opportunity_cache.keys())[:50]
                    for key in oldest_keys:
                        del self.opportunity_cache[key]
                
                if opportunity.get('is_profitable'):
                    opportunities.append(opportunity)
                    
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        # Sort by profitability
        opportunities.sort(key=lambda x: x.get('annualized_return', 0), reverse=True)
        
        return opportunities
    
    async def analyze_symbol_opportunity(self, symbol: str) -> Dict:
        """Analyze arbitrage opportunity for a single symbol"""
        try:
            # Get current data
            spot_price = await self.api_client.get_spot_price(symbol)
            futures_data = await self.api_client.get_futures_data(symbol)
            funding_rate = await self.api_client.get_funding_rate(symbol)
            
            if not all([spot_price, futures_data, funding_rate is not None]):
                return {
                    'symbol': symbol,
                    'is_profitable': False,
                    'reason': 'Missing market data'
                }
            
            futures_price = futures_data.get('mark_price', 0)
            
            # Calculate time to next funding
            now = datetime.now()
            next_funding_hour = ((now.hour // 8) + 1) * 8
            if next_funding_hour >= 24:
                next_funding = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            else:
                next_funding = now.replace(hour=next_funding_hour, minute=0, second=0, microsecond=0)
            
            hours_to_funding = (next_funding - now).total_seconds() / 3600
            
            # Calculate profitability
            profitability = await self.calculate_profitability(
                funding_rate, hours_to_funding, spot_price, futures_price
            )
            
            # Check liquidity and risk
            liquidity = await self.assess_liquidity(symbol)
            risk = await self.assess_risk(symbol, config.POSITION_SIZE_QUOTE)
            
            # Combine analysis
            opportunity = {
                'symbol': symbol,
                'timestamp': time.time(),
                'spot_price': spot_price,
                'futures_price': futures_price,
                'funding_rate': funding_rate,
                'hours_to_funding': hours_to_funding,
                'next_funding_time': next_funding.isoformat(),
                **profitability,
                'liquidity': liquidity,
                'risk': risk,
                'is_profitable': (
                    profitability.get('is_profitable', False) and
                    liquidity.get('is_liquid', False) and
                    risk.get('is_acceptable', False) and
                    funding_rate > config.MIN_POSITIVE_FUNDING_RATE
                )
            }
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error analyzing opportunity for {symbol}: {e}")
            return {
                'symbol': symbol,
                'is_profitable': False,
                'error': str(e)
            }
    
    async def calculate_position_sizes(self, symbol: str, target_amount: float) -> Dict:
        """Calculate optimal position sizes for arbitrage"""
        try:
            spot_price = await self.api_client.get_spot_price(symbol)
            futures_data = await self.api_client.get_futures_data(symbol)
            
            if not spot_price or not futures_data:
                return {'error': 'Missing price data'}
            
            futures_price = futures_data.get('mark_price', 0)
            
            # Simple position sizing
            spot_quantity = target_amount / spot_price
            futures_quantity = spot_quantity  # 1:1 hedge
            
            return {
                'spot_quantity': spot_quantity,
                'futures_quantity': futures_quantity,
                'spot_notional': spot_quantity * spot_price,
                'futures_notional': futures_quantity * futures_price,
                'total_required_margin': target_amount
            }
            
        except Exception as e:
            logger.error(f"Error calculating position sizes: {e}")
            return {'error': str(e)}
    
    async def validate_opportunity(self, opportunity: Dict) -> bool:
        """Final validation before executing trade"""
        try:
            symbol = opportunity['symbol']
            
            # Re-check current prices
            current_spot = await self.api_client.get_spot_price(symbol)
            current_futures_data = await self.api_client.get_futures_data(symbol)
            
            if not current_spot or not current_futures_data:
                logger.warning(f"Cannot validate {symbol} - missing current data")
                return False
            
            # Check if prices haven't moved too much
            original_spot = opportunity['spot_price']
            original_futures = opportunity['futures_price']
            
            spot_change = abs(current_spot - original_spot) / original_spot
            futures_change = abs(current_futures_data['mark_price'] - original_futures) / original_futures
            
            if spot_change > config.MAX_SLIPPAGE_PERCENT / 100 or futures_change > config.MAX_SLIPPAGE_PERCENT / 100:
                logger.warning(f"Price moved too much for {symbol}: spot={spot_change:.2%}, futures={futures_change:.2%}")
                return False
            
            # Check if opportunity is still profitable
            current_funding = await self.api_client.get_funding_rate(symbol)
            if current_funding is None or current_funding < config.MIN_POSITIVE_FUNDING_RATE:
                logger.warning(f"Funding rate changed for {symbol}: {current_funding}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating opportunity: {e}")
            return False
