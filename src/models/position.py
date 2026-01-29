"""
Position data model for tracking open trades.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PositionSide(str, Enum):
    """Position side enumeration."""

    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """
    Represents an open trading position.

    Attributes:
        position_id: Unique position identifier
        market_id: Market identifier
        side: Long or short
        entry_price: Entry price
        quantity: Number of contracts
        entry_cost: Total entry cost including fees
        entry_fee: Entry transaction fee
        opened_at: Position open timestamp
        closed_at: Position close timestamp
        current_price: Current market price
        exit_price: Actual exit price
        exit_revenue: Revenue from exit
        exit_fee: Exit transaction fee
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss
        return_pct: Return percentage
    """

    position_id: str
    market_id: str
    side: PositionSide
    entry_price: float
    quantity: int
    entry_cost: float
    entry_fee: float
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    current_price: float = 0.0
    exit_price: Optional[float] = None
    exit_revenue: Optional[float] = None
    exit_fee: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: Optional[float] = None
    return_pct: float = 0.0

    @property
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.closed_at is None

    @property
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.closed_at is not None

    @property
    def holding_time_seconds(self) -> float:
        """Get holding time in seconds."""
        end_time = self.closed_at if self.closed_at else datetime.now()
        return (end_time - self.opened_at).total_seconds()

    @property
    def holding_time_minutes(self) -> float:
        """Get holding time in minutes."""
        return self.holding_time_seconds / 60

    @property
    def holding_time_hours(self) -> float:
        """Get holding time in hours."""
        return self.holding_time_seconds / 3600

    @property
    def entry_notional(self) -> float:
        """Get entry notional value (excluding fees)."""
        return self.entry_price * self.quantity

    @property
    def current_notional(self) -> float:
        """Get current notional value."""
        return self.current_price * self.quantity

    @property
    def total_fees(self) -> float:
        """Get total fees (entry + exit)."""
        return self.entry_fee + (self.exit_fee or 0.0)

    def update_current_price(self, price: float, exit_fee: float = 0.0):
        """
        Update current price and recalculate unrealized P&L.

        Args:
            price: Current market price
            exit_fee: Estimated exit fee
        """
        self.current_price = price

        # Calculate unrealized P&L
        if self.side == PositionSide.LONG:
            # Long: profit if price goes up
            gross_pnl = (price - self.entry_price) * self.quantity
        else:
            # Short: profit if price goes down
            gross_pnl = (self.entry_price - price) * self.quantity

        # Subtract fees
        self.unrealized_pnl = gross_pnl - self.entry_fee - exit_fee

        # Calculate return percentage
        self.return_pct = (
            (self.unrealized_pnl / self.entry_cost * 100)
            if self.entry_cost > 0
            else 0.0
        )

    def close(
        self,
        exit_price: float,
        exit_revenue: float,
        exit_fee: float,
        realized_pnl: float,
        return_pct: float,
    ):
        """
        Close the position.

        Args:
            exit_price: Actual exit price
            exit_revenue: Revenue from exit (after fees)
            exit_fee: Exit transaction fee
            realized_pnl: Realized profit/loss
            return_pct: Return percentage
        """
        self.closed_at = datetime.now()
        self.exit_price = exit_price
        self.exit_revenue = exit_revenue
        self.exit_fee = exit_fee
        self.realized_pnl = realized_pnl
        self.return_pct = return_pct
        self.current_price = exit_price
        self.unrealized_pnl = 0.0  # No longer unrealized

    def __str__(self) -> str:
        status = "OPEN" if self.is_open else "CLOSED"
        pnl = self.unrealized_pnl if self.is_open else self.realized_pnl
        return (
            f"Position({self.position_id} | {status} | {self.side.value.upper()} {self.quantity} "
            f"@ ${self.entry_price:.4f} | P&L: ${pnl:+.2f} ({self.return_pct:+.1f}%))"
        )

    def __repr__(self) -> str:
        return self.__str__()
