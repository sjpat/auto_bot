import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from src.strategies.base_strategy import Signal, SignalType

class VolumeStrategy:
    """
    Detects significant volume spikes relative to recent history.
    High volume + Price Move = Strong Signal (Smart Money).
    """
    def __init__(self, config):
        self.enabled = config.ENABLE_VOLUME_STRATEGY
        self.spike_threshold = config.VOLUME_SPIKE_THRESHOLD
        self.min_volume = config.MIN_VOLUME_FOR_STRATEGY
        self.history_size = 20
        # Store history: market_id -> list of {'timestamp': ts, 'volume': vol, 'price': price}
        self.history: Dict[str, List[Dict]] = {}

    def on_market_update(self, market):
        """Update volume history for a market."""
        if not self.enabled:
            return

        if market.market_id not in self.history:
            self.history[market.market_id] = []
        
        # Use 'volume' (24h cumulative) if available, otherwise 0
        # Check both 'volume' (live) and 'volume_24h' (backtest/historical)
        current_vol = getattr(market, 'volume', getattr(market, 'volume_24h', 0))
        
        self.history[market.market_id].append({
            'timestamp': datetime.now(),
            'volume': current_vol,
            'price': market.yes_price  # Use yes_price for consistency
        })
        
        # Keep history size manageable
        if len(self.history[market.market_id]) > self.history_size:
            self.history[market.market_id].pop(0)

    def generate_entry_signals(self, markets) -> List[Signal]:
        """Check markets for volume spikes."""
        if not self.enabled:
            return []
            
        signals = []
        for market in markets:
            signal = self.analyze_market(market)
            if signal:
                signals.append(signal)
        return signals

    def analyze_market(self, market) -> Optional[Signal]:
        history = self.history.get(market.market_id, [])
        if len(history) < 5:
            return None
            
        # Calculate tick volumes (change in cumulative volume)
        tick_volumes = []
        price_changes = []
        
        for i in range(1, len(history)):
            vol_delta = history[i]['volume'] - history[i-1]['volume']
            price_delta = history[i]['price'] - history[i-1]['price']
            
            # Filter out negative volume deltas (API resets/glitches)
            if vol_delta >= 0:
                tick_volumes.append(vol_delta)
                price_changes.append(price_delta)
        
        if not tick_volumes:
            return None
            
        current_vol = tick_volumes[-1]
        current_price_change = price_changes[-1]
        
        # Ignore noise (very low volume ticks)
        if current_vol < self.min_volume:
            return None

        # Calculate average of previous ticks (excluding current spike)
        if len(tick_volumes) > 1:
            avg_vol = np.mean(tick_volumes[:-1])
            if avg_vol < 1: avg_vol = 1  # Avoid division by zero
        else:
            return None
            
        vol_ratio = current_vol / avg_vol
        
        # Check for spike
        if vol_ratio > self.spike_threshold:
            # Determine direction based on price move
            direction = None
            if current_price_change > 0.005: # Require small positive move
                direction = SignalType.BUY
            elif current_price_change < -0.005: # Require small negative move
                direction = SignalType.SELL
            
            # Only signal if there is a directional move matching the volume
            if direction:
                return Signal(
                    market_id=market.market_id,
                    price=market.yes_price,
                    signal_type=direction,
                    # Confidence increases with volume ratio, capped at 0.9
                    confidence=min(0.9, 0.5 + (vol_ratio / 20.0)),
                    metadata={
                        'strategy': 'volume_spike',
                        'vol_ratio': vol_ratio,
                        'avg_vol': avg_vol,
                        'current_vol': current_vol,
                        'price_change': current_price_change,
                        # Map to spike_magnitude for RiskManager compatibility
                        'spike_magnitude': abs(current_price_change)
                    }
                )
        return None

    def get_statistics(self) -> Dict:
        return {
            'enabled': self.enabled,
            'tracked_markets': len(self.history)
        }
