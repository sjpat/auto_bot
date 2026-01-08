"""
Order data model for trading operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """
    Represents a trading order.
    
    Attributes:
        order_id: Unique order identifier
        market_id: Market identifier
        side: Buy or sell
        order_type: Limit or market
        quantity: Number of contracts
        price: Limit price (None for market orders)
        status: Current order status
        filled_quantity: Number of contracts filled
        avg_fill_price: Average fill price
        created_at: Order creation timestamp
        updated_at: Last update timestamp
        filled_at: Fill completion timestamp
        fee: Transaction fee
        slippage: Actual slippage experienced
    """
    
    order_id: str
    market_id: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    fee: float = 0.0
    slippage: float = 0.0
    
    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_open(self) -> bool:
        """Check if order is still open."""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def unfilled_quantity(self) -> int:
        """Get unfilled quantity."""
        return self.quantity - self.filled_quantity
    
    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        return (self.filled_quantity / self.quantity * 100) if self.quantity > 0 else 0.0
    
    @property
    def notional_value(self) -> float:
        """Get notional value of order."""
        price = self.avg_fill_price if self.is_filled else self.price
        return (price or 0.0) * self.quantity
    
    @property
    def total_cost(self) -> float:
        """Get total cost including fees."""
        return self.notional_value + self.fee
    
    def update_fill(self, filled_qty: int, fill_price: float, fee: float = 0.0):
        """
        Update order fill information.
        
        Args:
            filled_qty: Quantity filled in this update
            fill_price: Price of this fill
            fee: Fee for this fill
        """
        # Update filled quantity
        previous_filled = self.filled_quantity
        self.filled_quantity += filled_qty
        
        # Update average fill price (weighted average)
        if self.filled_quantity > 0:
            total_value = (self.avg_fill_price * previous_filled) + (fill_price * filled_qty)
            self.avg_fill_price = total_value / self.filled_quantity
        
        # Update fee
        self.fee += fee
        
        # Update status
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.now()
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        # Update timestamp
        self.updated_at = datetime.now()
    
    def cancel(self):
        """Mark order as cancelled."""
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now()
    
    def reject(self):
        """Mark order as rejected."""
        self.status = OrderStatus.REJECTED
        self.updated_at = datetime.now()
    
    def __str__(self) -> str:
        return (
            f"Order({self.order_id[:8]}... | {self.side.value.upper()} {self.quantity} "
            f"@ ${self.price:.4f} | {self.status.value})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()
