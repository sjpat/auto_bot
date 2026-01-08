"""
Candle/OHLCV data model for price history.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List


class Timeframe(str, Enum):
    """Timeframe enumeration for candles."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


@dataclass
class Candle:
    """
    Represents a price candle (OHLCV).
    
    Attributes:
        timestamp: Candle timestamp
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
    """
    
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    @property
    def range_pct(self) -> float:
        """Get price range as percentage of open."""
        if self.open > 0:
            return (self.high - self.low) / self.open * 100
        return 0.0
    
    @property
    def change_pct(self) -> float:
        """Get price change percentage."""
        if self.open > 0:
            return (self.close - self.open) / self.open * 100
        return 0.0
    
    @property
    def is_bullish(self) -> bool:
        """Check if candle is bullish (close > open)."""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Check if candle is bearish (close < open)."""
        return self.close < self.open
    
    @property
    def body_size(self) -> float:
        """Get candle body size."""
        return abs(self.close - self.open)
    
    @property
    def upper_wick(self) -> float:
        """Get upper wick size."""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        """Get lower wick size."""
        return min(self.open, self.close) - self.low
    
    def __str__(self) -> str:
        direction = "🟢" if self.is_bullish else "🔴"
        return (
            f"Candle({direction} | O:{self.open:.4f} H:{self.high:.4f} "
            f"L:{self.low:.4f} C:{self.close:.4f} | {self.change_pct:+.2f}%)"
        )
