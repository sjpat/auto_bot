"""
Market data model for market information.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MarketStatus(str, Enum):
    """Market status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    HALTED = "halted"
    SETTLING = "settling"
    SETTLED = "settled"


@dataclass
class Market:
    """
    Represents a prediction market.
    
    Attributes:
        market_id: Unique market identifier
        title: Market title/question
        status: Current market status
        close_time: Market close timestamp
        yes_price: Current YES price (0.00-1.00)
        no_price: Current NO price (0.00-1.00)
        yes_bid: Best YES bid
        yes_ask: Best YES ask
        no_bid: Best NO bid
        no_ask: Best NO ask
        volume: 24h volume
        liquidity: Available liquidity
        open_interest: Total open interest
        category: Market category
        last_updated: Last update timestamp
    """
    
    market_id: str
    title: str
    status: MarketStatus
    close_time: datetime
    yes_price: float = 0.50
    no_price: float = 0.50
    yes_bid: Optional[float] = None
    yes_ask: Optional[float] = None
    no_bid: Optional[float] = None
    no_ask: Optional[float] = None
    volume: float = 0.0
    liquidity: float = 0.0
    open_interest: float = 0.0
    category: Optional[str] = None
    last_updated: datetime = None
    
    def __post_init__(self):
        """Initialize calculated fields."""
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    @property
    def is_open(self) -> bool:
        """Check if market is open for trading."""
        return self.status == MarketStatus.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if market is closed."""
        return self.status in [MarketStatus.CLOSED, MarketStatus.SETTLED]
    
    @property
    def time_to_close_seconds(self) -> float:
        """Get seconds until market closes."""
        return (self.close_time - datetime.now()).total_seconds()
    
    @property
    def time_to_close_hours(self) -> float:
        """Get hours until market closes."""
        return self.time_to_close_seconds / 3600
    
    @property
    def time_to_close_days(self) -> float:
        """Get days until market closes."""
        return self.time_to_close_seconds / 86400
    
    def is_expiring_soon(self, hours: float = 24.0) -> bool:
        """Check if market is expiring within specified hours."""
        return 0 < self.time_to_close_hours < hours
    
    @property
    def spread_yes(self) -> Optional[float]:
        """Get YES spread (ask - bid)."""
        if self.yes_ask is not None and self.yes_bid is not None:
            return self.yes_ask - self.yes_bid
        return None
    
    @property
    def spread_no(self) -> Optional[float]:
        """Get NO spread (ask - bid)."""
        if self.no_ask is not None and self.no_bid is not None:
            return self.no_ask - self.no_bid
        return None
    
    @property
    def mid_price_yes(self) -> Optional[float]:
        """Get YES mid price."""
        if self.yes_ask is not None and self.yes_bid is not None:
            return (self.yes_ask + self.yes_bid) / 2
        return self.yes_price
    
    @property
    def mid_price_no(self) -> Optional[float]:
        """Get NO mid price."""
        if self.no_ask is not None and self.no_bid is not None:
            return (self.no_ask + self.no_bid) / 2
        return self.no_price
    
    @property
    def is_liquid(self, min_liquidity: float = 500.0) -> bool:
        """Check if market has sufficient liquidity."""
        return self.liquidity >= min_liquidity
    
    @property
    def is_tradeable(self, min_liquidity: float = 500.0, max_hours_to_close: float = 1.0) -> bool:
        """
        Check if market is tradeable.
        
        Args:
            min_liquidity: Minimum liquidity required
            max_hours_to_close: Maximum hours until close (avoid expiring markets)
        
        Returns:
            True if market is open, liquid, and not expiring soon
        """
        return (
            self.is_open and
            self.is_liquid(min_liquidity) and
            not self.is_expiring_soon(max_hours_to_close)
        )
    
    def __str__(self) -> str:
        return (
            f"Market({self.market_id[:8]}... | {self.title[:30]}... | "
            f"{self.status.value} | YES: ${self.yes_price:.4f} NO: ${self.no_price:.4f})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()
