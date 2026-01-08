"""
Spike detection trading strategy.

Detects sudden price movements (spikes) and executes mean-reversion trades.
"""

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.models.market import Market
from src.models.position import Position


class SpikeStrategy(BaseStrategy):
    """
    Spike detection strategy for mean-reversion trading.
    
    Strategy Logic:
    1. Track price history for each market
    2. Detect significant price spikes (deviation from mean)
    3. Enter position betting on mean reversion
    4. Exit on profit target or stop loss
    
    Parameters:
        SPIKE_THRESHOLD: Minimum price change to trigger signal (default: 0.04 = 4%)
        HISTORY_SIZE: Number of price points to track (default: 100)
        MIN_HISTORY: Minimum history before generating signals (default: 20)
        TARGET_PROFIT_USD: Profit target in dollars
        TARGET_LOSS_USD: Stop loss in dollars
        HOLDING_TIME_LIMIT: Maximum hold time in seconds
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Strategy parameters
        self.spike_threshold = config.get('SPIKE_THRESHOLD', 0.04)
        self.history_size = config.get('HISTORY_SIZE', 100)
        self.min_history = config.get('MIN_HISTORY', 20)
        self.target_profit_usd = config.get('TARGET_PROFIT_USD', 2.50)
        self.target_loss_usd = config.get('TARGET_LOSS_USD', -1.50)
        self.holding_time_limit = config.get('HOLDING_TIME_LIMIT', 3600)  # 1 hour
        
        # Price history for each market
        self.price_history: Dict[str, deque] = {}
        
        # Cooldown tracking (avoid re-entering same market too quickly)
        self.cooldown_period = config.get('COOLDOWN_PERIOD', 60)  # 60 seconds
        self.last_trade_time: Dict[str, datetime] = {}
        
        self.logger.info(
            f"SpikeStrategy initialized: "
            f"threshold={self.spike_threshold:.1%}, "
            f"target_profit=${self.target_profit_usd:.2f}, "
            f"stop_loss=${self.target_loss_usd:.2f}"
        )
    
    def generate_entry_signals(self, markets: List[Market]) -> List[Signal]:
        """
        Generate buy signals for markets with detected spikes.
        
        Args:
            markets: List of tradeable markets
        
        Returns:
            List of buy signals for spikes
        """
        signals = []
        
        for market in markets:
            # Skip if market not tradeable
            if not market.is_open or not market.is_liquid():
                continue
            
            # Skip if in cooldown
            if self._is_in_cooldown(market.market_id):
                continue
            
            # Check for spike
            spike_info = self._detect_spike(market)
            
            if spike_info:
                signal = Signal(
                    signal_type=SignalType.BUY,
                    market_id=market.market_id,
                    price=market.yes_price,
                    confidence=spike_info['confidence'],
                    metadata={
                        'spike_magnitude': spike_info['magnitude'],
                        'direction': spike_info['direction'],
                        'mean_price': spike_info['mean_price'],
                        'std_dev': spike_info['std_dev'],
                        'history_length': spike_info['history_length']
                    }
                )
                
                signals.append(signal)
                self.signals_generated += 1
                
                self.logger.info(
                    f"📊 Spike detected: {market.market_id[:12]}... | "
                    f"Price: ${market.yes_price:.4f} | "
                    f"Magnitude: {spike_info['magnitude']:.1%} | "
                    f"Direction: {spike_info['direction']}"
                )
        
        return self.filter_signals(signals, min_confidence=0.6)
    
    def generate_exit_signals(
        self,
        positions: List[Position],
        markets: Dict[str, Market]
    ) -> List[Signal]:
        """
        Generate sell signals for positions that hit targets or limits.
        
        Args:
            positions: List of open positions
            markets: Dictionary of market_id -> Market
        
        Returns:
            List of sell signals
        """
        signals = []
        
        for position in positions:
            if not position.is_open:
                continue
            
            market = markets.get(position.market_id)
            if not market:
                self.logger.warning(f"Market not found for position: {position.market_id}")
                continue
            
            # Update position with current price
            # Note: This assumes fee calculator is available in parent context
            position.update_current_price(market.yes_price)
            
            # Check exit conditions
            exit_reason = self._check_exit_conditions(position)
            
            if exit_reason:
                signal = Signal(
                    signal_type=SignalType.SELL,
                    market_id=position.market_id,
                    price=market.yes_price,
                    confidence=1.0,  # Always confident on exits
                    metadata={
                        'reason': exit_reason,
                        'holding_time_seconds': position.holding_time_seconds,
                        'unrealized_pnl': position.unrealized_pnl,
                        'return_pct': position.return_pct
                    }
                )
                signals.append(signal)
                
                self.logger.info(
                    f"🚪 Exit signal: {position.position_id} | "
                    f"Reason: {exit_reason} | "
                    f"P&L: ${position.unrealized_pnl:+.2f} ({position.return_pct:+.1%})"
                )
        
        return signals

    def on_market_update(self, market: Market):
        """
        Track price history for market.
        
        Args:
            market: Updated market data
        """
        # Initialize history if needed
        if market.market_id not in self.price_history:
            self.price_history[market.market_id] = deque(maxlen=self.history_size)
        
        # Add current price
        self.price_history[market.market_id].append(market.yes_price)