# src/trading/spike_detector.py

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import math

@dataclass
class Spike:
    """Represents a detected price spike"""
    market_id: str
    market_name: str
    direction: str  # "buy" or "sell"
    current_price: float
    previous_price: float
    change_pct: float
    timestamp: datetime
    confidence: float  # 0.0-1.0

class SpikeDetector:
    """Detects significant price spikes in prediction markets"""
    
    def __init__(self, config):
        self.config = config
        # Store price history per market
        self.price_history = {}  # market_id -> deque of (price, timestamp)
        self.spike_cooldown = {}  # market_id -> last_spike_timestamp
    
    def add_price(self, market_id: str, price: float, timestamp: datetime):
        """Add price point for a market"""
        if market_id not in self.price_history:
            self.price_history[market_id] = deque(
                maxlen=self.config.PRICE_HISTORY_SIZE
            )
        
        self.price_history[market_id].append((price, timestamp))
    
    def detect_spikes(self, threshold: Optional[float] = None) -> List[Spike]:
        """
        Detect spikes across all markets
        
        Args:
            threshold: Price change percentage (overrides config)
        
        Returns:
            List of detected spikes
        """

        threshold = threshold or self.config.SPIKE_THRESHOLD
        spikes = []
        
        for market_id, prices in self.price_history.items():
            if len(prices) < 2:
                continue  # Need at least 2 points
            
            # Get current and previous prices
            current_price, current_time = prices[-1]
            previous_price, previous_time = prices[-2]
            
            # Calculate change
            if previous_price == 0:
                continue
            
            change_pct = (current_price - previous_price) / previous_price
            
            # Check spike condition
            if abs(change_pct) >= threshold:
                # Check cooldown (avoid repeat trades on same spike)
                if self._check_cooldown(market_id, current_time):
                    continue
                
                # Create spike object
                spike = Spike(
                    market_id=market_id,
                    market_name=self._get_market_name(market_id),
                    direction="buy" if change_pct < 0 else "sell",
                    current_price=current_price,
                    previous_price=previous_price,
                    change_pct=change_pct,
                    timestamp=current_time,
                    confidence=self._calculate_confidence(
                        market_id, change_pct
                    )
                )
                
                spikes.append(spike)
                self.spike_cooldown[market_id] = current_time
        
        return spikes
    
    def _check_cooldown(self, market_id: str, current_time: datetime) -> bool:
        """Check if market is in cooldown period"""
        if market_id not in self.spike_cooldown:
            return False
        
        last_spike_time = self.spike_cooldown[market_id]
        elapsed = (current_time - last_spike_time).total_seconds()
        
        return elapsed < self.config.SOLD_POSITION_TIME
    
    def _calculate_confidence(self, market_id: str, change_pct: float) -> float:
        """
        Calculate confidence score (0.0-1.0)
        Based on: magnitude of move, volatility context, volume
        """
        # Simple implementation: larger moves = higher confidence
        confidence = min(1.0, abs(change_pct) / (self.config.SPIKE_THRESHOLD * 2))
        
        # Could add volatility adjustment
        if market_id in self.price_history:
            volatility = self._calculate_volatility(market_id)
            # Penalize low volatility environment
            if volatility < 0.01:
                confidence *= 0.7
        
        return confidence
    
    def _calculate_volatility(self, market_id: str) -> float:
        """Calculate rolling volatility (standard deviation of returns)"""
        if market_id not in self.price_history:
            return 0.0
        
        prices = [p for p, _ in self.price_history[market_id]]
        
        if len(prices) < 2:
            return 0.0
        
        # Calculate returns
        returns = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(1, len(prices))
        ]
        
        if not returns:
            return 0.0
        
        # Standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        
        return math.sqrt(variance)
    
    def _get_market_name(self, market_id: str) -> str:
        """Get human-readable market name (from API or cache)"""
        # In real implementation, would fetch from market data
        return market_id
