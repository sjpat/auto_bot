"""
Momentum / Trend Following Strategy.

Captures sustained price movements during volatile events (e.g., sports games).
Unlike SpikeStrategy (which fades moves), this strategy bets WITH the trend.
"""

import logging
from collections import deque
from typing import List, Dict, Any, Optional

from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.models.market import Market
from src.models.position import Position


class MomentumStrategy(BaseStrategy):
    """
    Momentum strategy for volatile live events.
    
    Logic:
    1. Monitor Rate of Change (ROC) over a specific window (e.g., 1-5 minutes).
    2. If price moves significantly in one direction AND volume supports it, enter.
    3. Use tight trailing stops to capture the "run".
    
    Best for:
    - NBA/NFL games (scoring runs)
    - Election nights (precinct reporting trends)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Parameters
        self.momentum_window = config.get('MOMENTUM_WINDOW', 6)  # Number of updates to look back
        self.momentum_threshold = config.get('MOMENTUM_THRESHOLD', 0.03)  # 3% move required
        self.min_confidence = config.get('MIN_CONFIDENCE', 0.65)
        
        self.target_profit_usd = config.get('TARGET_PROFIT_USD', 3.0)
        self.target_loss_usd = config.get('TARGET_LOSS_USD', -1.5)
        self.holding_time_limit = config.get('HOLDING_TIME_LIMIT', 1800)  # 30 mins max for momentum
        self.min_liquidity = config.get('MIN_LIQUIDITY_REQUIREMENT', 500.0)
        
        # State
        self.price_history: Dict[str, deque] = {}
        
        self.logger.info(
            f"MomentumStrategy initialized: "
            f"window={self.momentum_window}, threshold={self.momentum_threshold:.1%}"
        )

    def generate_entry_signals(self, markets: List[Market]) -> List[Signal]:
        signals = []
        
        for market in markets:
            if not market.is_open or not market.is_liquid(self.min_liquidity):
                continue
                
            # Need history to calculate momentum
            if market.market_id not in self.price_history:
                continue
                
            history = list(self.price_history[market.market_id])
            # Need at least window + 1 points to calculate change over 'window' intervals
            if len(history) <= self.momentum_window:
                continue
            
            # Calculate Rate of Change (ROC)
            current_price = market.yes_price
            past_price = history[-(self.momentum_window + 1)]
            
            roc = (current_price - past_price) / past_price if past_price > 0 else 0
            
            # Detect Momentum
            if abs(roc) >= self.momentum_threshold:
                # Filter out prices that are already too high/low (limited upside)
                if current_price > 0.92 or current_price < 0.08:
                    continue
                
                direction = SignalType.BUY if roc > 0 else SignalType.SELL
                
                # Confidence scales with the strength of the move relative to threshold
                confidence = min(0.5 + (abs(roc) / self.momentum_threshold) * 0.1, 0.9)
                
                if confidence >= self.min_confidence:
                    signal = Signal(
                        signal_type=direction,
                        market_id=market.market_id,
                        price=current_price,
                        confidence=confidence,
                        metadata={
                            'strategy': 'momentum',
                            'roc': roc,
                            'window': self.momentum_window,
                            'past_price': past_price
                        }
                    )
                    signals.append(signal)
                    self.signals_generated += 1
                    
                    self.logger.info(
                        f"🚀 Momentum detected: {market.market_id} | "
                        f"ROC: {roc:+.1%} in {self.momentum_window} ticks | "
                        f"Dir: {direction}"
                    )
        
        return signals

    def generate_exit_signals(self, positions: List[Position], markets: Dict[str, Market]) -> List[Signal]:
        signals = []
        for position in positions:
            if not position.is_open:
                continue
            
            market = markets.get(position.market_id)
            if not market:
                continue
                
            position.update_current_price(market.yes_price)
            
            # Momentum trades rely heavily on trailing stops (implemented in PositionManager/Engine)
            # But we can add a "momentum stalled" exit here
            
            # 1. Hard targets
            if position.unrealized_pnl >= self.target_profit_usd:
                signals.append(self._create_exit(position, market.yes_price, "profit_target"))
            elif position.unrealized_pnl <= self.target_loss_usd:
                signals.append(self._create_exit(position, market.yes_price, "stop_loss"))
            elif position.holding_time_seconds >= self.holding_time_limit:
                signals.append(self._create_exit(position, market.yes_price, "time_limit"))
            
            # 2. Trend Reversal Check
            # If the momentum that justified the trade reverses, exit early
            if market.market_id in self.price_history:
                history = list(self.price_history[market.market_id])
                if len(history) > self.momentum_window:
                    current_price = market.yes_price
                    past_price = history[-(self.momentum_window + 1)]
                    roc = (current_price - past_price) / past_price if past_price > 0 else 0
                    
                    # If Long (betting on YES price increase)
                    if getattr(position, 'side', 'buy') == 'buy':
                        if roc < -self.momentum_threshold * 0.5:  # Significant reversal (50% of entry threshold)
                            signals.append(self._create_exit(position, market.yes_price, "trend_reversal"))
                    
                    # If Short (betting on YES price decrease)
                    elif getattr(position, 'side', 'buy') == 'sell':
                        if roc > self.momentum_threshold * 0.5:
                            signals.append(self._create_exit(position, market.yes_price, "trend_reversal"))
                
        return signals

    def _create_exit(self, position, price, reason):
        return Signal(
            signal_type=SignalType.SELL,
            market_id=position.market_id,
            price=price,
            confidence=1.0,
            metadata={'reason': reason}
        )

    def on_market_update(self, market: Market):
        if market.market_id not in self.price_history:
            self.price_history[market.market_id] = deque(maxlen=50)
        self.price_history[market.market_id].append(market.yes_price)
