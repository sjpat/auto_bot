"""
Mispricing Detection Strategy

Identifies markets trading away from their theoretical fair value.
Works in all volatility environments.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque

from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.models.market import Market
from src.models.position import Position
from src.models.pricing_models import PricingModels, FairValue


class MispricingStrategy(BaseStrategy):
    """
    Detect and trade mispriced markets.
    
    Strategy Logic:
    1. Calculate theoretical fair value for each market
    2. Compare to current market price
    3. If edge > threshold, generate signal
    4. Exit when price converges to fair value
    
    Works best for:
    - Binary YES/NO markets
    - Markets near expiration
    - Correlated market groups
    - Low volatility environments (no spikes needed!)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Strategy parameters
        self.min_edge = config.get('MIN_EDGE', 0.08)  # 8% edge minimum
        self.min_confidence = config.get('MIN_CONFIDENCE', 0.6)
        self.max_holding_time = config.get('MAX_HOLDING_TIME', 3600 * 4)  # 4 hours
        
        # Pricing models
        self.pricing_models = PricingModels()
        
        # Track price history for mean reversion
        self.price_history: Dict[str, deque] = {}
        self.history_size = config.get('HISTORY_SIZE', 50)
        
        # Track which markets we've analyzed
        self.fair_values: Dict[str, FairValue] = {}
        
        self.logger.info(
            f"MispricingStrategy initialized: "
            f"min_edge={self.min_edge:.1%}, "
            f"min_confidence={self.min_confidence:.1%}"
        )
    
    def generate_entry_signals(self, markets: List[Market]) -> List[Signal]:
        """
        Find mispriced markets.
        
        Args:
            markets: List of available markets
        
        Returns:
            List of signals for mispriced opportunities
        """
        signals = []
        
        for market in markets:
            # Skip if not tradeable
            if not market.is_open or not market.is_liquid:
                continue
            
            # Update price history
            self._update_price_history(market)
            
            # Try multiple pricing methods
            fair_value = self._calculate_fair_value(market)
            
            if fair_value:
                # Calculate edge
                edge = abs(fair_value.probability - market.yes_price)
                
                # Check if edge meets threshold
                if edge >= self.min_edge and fair_value.confidence >= self.min_confidence:
                    # Determine direction
                    if fair_value.probability > market.yes_price:
                        signal_type = SignalType.BUY  # Underpriced
                    else:
                        signal_type = SignalType.SELL  # Overpriced
                    
                    signal = Signal(
                        signal_type=signal_type,
                        market_id=market.market_id,
                        price=market.yes_price,
                        confidence=fair_value.confidence,
                        metadata={
                            'edge': edge,
                            'fair_value': fair_value.probability,
                            'market_price': market.yes_price,
                            'pricing_method': fair_value.method,
                            'pricing_metadata': fair_value.metadata
                        }
                    )
                    
                    signals.append(signal)
                    self.signals_generated += 1
                    
                    # Cache fair value
                    self.fair_values[market.market_id] = fair_value
                    
                    self.logger.info(
                        f"💰 Mispricing detected: {market.market_id[:20]}... | "
                        f"Edge: {edge:.1%} | "
                        f"Fair: {fair_value.probability:.1%} | "
                        f"Market: {market.yes_price:.1%} | "
                        f"Method: {fair_value.method}"
                    )
        
        return self.filter_signals(signals, min_confidence=self.min_confidence)
    
    def generate_exit_signals(
        self,
        positions: List[Position],
        markets: Dict[str, Market]
    ) -> List[Signal]:
        """
        Exit when mispricing corrects or time limit reached.
        
        Args:
            positions: Open positions
            markets: Current market data
        
        Returns:
            List of exit signals
        """
        signals = []
        
        for position in positions:
            if not position.is_open:
                continue
            
            market = markets.get(position.market_id)
            if not market:
                continue
            
            # Update position
            position.update_current_price(market.yes_price)
            
            # Check exit conditions
            exit_reason = self._check_mispricing_exit(position, market)
            
            if exit_reason:
                signal = Signal(
                    signal_type=SignalType.SELL,
                    market_id=position.market_id,
                    price=market.yes_price,
                    confidence=1.0,
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
                    f"P&L: ${position.unrealized_pnl:+.2f}"
                )
        
        return signals
    
    def _calculate_fair_value(self, market: Market) -> Optional[FairValue]:
        """
        Calculate fair value using multiple methods.
        Returns the most confident estimate.
        """
        candidates = []
        
        # Method 1: YES/NO complement
        fair_value = self.pricing_models.binary_yes_no_complement({
            'yes_price': market.yes_price,
            'no_price': market.no_price  # Kalshi doesn't always provide NO
        })
        if fair_value:
            candidates.append(fair_value)
        
        # Method 2: Time decay (near expiration)
        fair_value = self.pricing_models.time_decay_expiration({
            'time_to_close_seconds': market.time_to_close_seconds,
            'current_price': market.yes_price
        })
        if fair_value:
            candidates.append(fair_value)
        
        # Method 3: Mean reversion
        if market.market_id in self.price_history:
            history = list(self.price_history[market.market_id])
            fair_value = self.pricing_models.moving_average_reversion(
                price_history=history,
                current_price=market.yes_price
            )
            if fair_value:
                candidates.append(fair_value)
        
        # Return the most confident estimate
        if candidates:
            best = max(candidates, key=lambda fv: fv.confidence)
            return best
        
        return None
    
    def _check_mispricing_exit(self, position: Position, market: Market) -> Optional[str]:
        """
        Check if we should exit a mispricing position.
        
        Exit conditions:
        1. Price has converged to fair value (profit target met)
        2. Mispricing has worsened (stop loss)
        3. Holding time limit reached
        4. New information invalidates thesis
        """
        # 1. Profit target met
        if position.unrealized_pnl >= 2.0:  # $2 profit
            return "profit_target"
        
        # 2. Stop loss
        if position.unrealized_pnl <= -1.5:  # $1.50 loss
            return "stop_loss"
        
        # 3. Time limit
        if position.holding_time_seconds >= self.max_holding_time:
            return "time_limit"
        
        # 4. Price has converged to fair value
        if market.market_id in self.fair_values:
            fair_value = self.fair_values[market.market_id]
            current_edge = abs(fair_value.probability - market.yes_price)
            
            # If edge has decreased significantly (60%+ correction)
            original_edge = position.metadata.get('edge', 0.10)
            if current_edge < original_edge * 0.4:
                return "convergence_to_fair_value"
        
        return None
    
    def _update_price_history(self, market: Market):
        """Track price history for mean reversion analysis."""
        if market.market_id not in self.price_history:
            self.price_history[market.market_id] = deque(maxlen=self.history_size)
        
        self.price_history[market.market_id].append(market.yes_price)
    
    def on_market_update(self, market: Market):
        """Called when market data is updated."""
        self._update_price_history(market)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        base_stats = super().get_statistics()
        
        base_stats.update({
            'min_edge': self.min_edge,
            'markets_with_fair_values': len(self.fair_values),
            'markets_tracked': len(self.price_history)
        })
        
        return base_stats

