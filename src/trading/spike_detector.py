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
    # market_name: Optional[str]
    direction: str  # "buy" or "sell"
    current_price: float
    previous_price: float
    change_pct: float
    timestamp: datetime
    price_change: Optional[float] = None
    mean_price: Optional[float] = None
    std_dev: Optional[float] = None
    # confidence: Optional[float]  # 0.0-1.0


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
            self.price_history[market_id] = deque(maxlen=self.config.PRICE_HISTORY_SIZE)

        self.price_history[market_id].append((price, timestamp))

    def detect_spikes(
        self, markets: List = None, threshold: Optional[float] = None
    ) -> List[Spike]:
        """
        Detect spikes across all markets

        Args:
            markets: List of Market objects with current prices
            threshold: Price change percentage (overrides config)

        Returns:
            List of detected spikes
        """
        threshold = threshold or self.config.SPIKE_THRESHOLD
        spikes = []

        # If markets provided, check them against price history
        if markets:
            for market in markets:
                market_id = market.market_id

                # Need sufficient price history
                if market_id not in self.price_history:
                    continue

                price_history = self.price_history[market_id]
                if len(price_history) < 20:
                    continue

                # Extract just price values (not tuples)
                prices = [
                    p if isinstance(p, (int, float)) else p[0] for p in price_history
                ]

                # Calculate mean of historical prices
                mean_price = sum(prices) / len(prices)

                if mean_price == 0:
                    continue

                # Get current price from market (convert cents to dollars)
                current_price = market.last_price_cents / 10000.0

                # Calculate change
                change_pct = (current_price - mean_price) / mean_price

                if abs(change_pct) >= threshold:
                    spike = Spike(
                        market_id=market_id,
                        current_price=current_price,
                        previous_price=mean_price,
                        change_pct=change_pct,
                        price_change=current_price - mean_price,
                        mean_price=mean_price,
                        std_dev=self._calculate_volatility(market_id),
                        direction="buy" if change_pct > 0 else "sell",
                        timestamp=datetime.now(),
                    )
                    spikes.append(spike)
        else:
            # Legacy behavior: check price_history only
            for market_id, price_history in self.price_history.items():
                if len(price_history) < 20:
                    continue

                # Extract just price values (not tuples)
                prices = [
                    p if isinstance(p, (int, float)) else p[0] for p in price_history
                ]

                # Calculate mean
                mean_price = sum(prices) / len(prices)

                # Get current price from history
                current_price = prices[-1]

                if mean_price == 0:
                    continue

                # Calculate change
                change_pct = (current_price - mean_price) / mean_price

                if abs(change_pct) >= threshold:
                    spike = Spike(
                        market_id=market_id,
                        current_price=current_price,
                        previous_price=mean_price,
                        change_pct=change_pct,
                        direction="buy" if change_pct > 0 else "sell",
                        timestamp=datetime.now(),
                    )
                    spikes.append(spike)

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
            (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
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
