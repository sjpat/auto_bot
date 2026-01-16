"""
Paper Trading System for Kalshi Bot

Simulates trading with real market data but virtual money.
Wraps the real KalshiClient to intercept orders.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from collections import deque
import json
from pathlib import Path

from src.clients.kalshi_client import KalshiClient, Order, Market

logger = logging.getLogger(__name__)

@dataclass
class PaperOrder:
    """Simulated order for paper trading."""
    order_id: str
    market_id: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price: float
    status: str = "filled"  # Always fill immediately in paper trading
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    slippage: float = 0.0  # Simulated slippage
    
    def __post_init__(self):
        """Auto-fill order in paper trading."""
        # Simulate instant fill with small slippage
        self.filled_quantity = self.quantity
        self.avg_fill_price = self.price * (1 + self.slippage)
        self.filled_at = datetime.now()
    
    def to_real_order(self) -> Order:
        """Convert to Order object for compatibility."""
        return Order(
            order_id=self.order_id,
            market_id=self.market_id,
            side=self.side,
            quantity=self.quantity,
            price_cents=int(self.price * 100),
            status=self.status,
            filled_quantity=self.filled_quantity,
            avg_fill_price_cents=int(self.avg_fill_price * 100),
            created_at=self.created_at
        )


@dataclass
class PaperPosition:
    """Simulated position for paper trading."""
    position_id: str
    market_id: str
    side: str
    entry_price: float
    quantity: int
    entry_cost: float
    entry_fee: float
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_revenue: Optional[float] = None
    exit_fee: Optional[float] = None
    net_pnl: Optional[float] = None
    return_pct: Optional[float] = None


class PaperTradingClient:
    """
    Paper trading client that wraps KalshiClient.
    
    Features:
    - Uses REAL market data from Kalshi production API
    - Simulates order execution (instant fills)
    - Tracks virtual balance and P&L
    - Saves trading history to file
    - Realistic fee calculations
    - Optional slippage simulation
    """
    
    def __init__(
        self,
        kalshi_client: KalshiClient,
        starting_balance: float = 1000.0,
        simulate_slippage: bool = True,
        max_slippage_pct: float = 0.005,  # 0.5% max slippage
        save_history: bool = True,
        history_file: str = "logs/paper_trading_history.json"
    ):
        """
        Initialize paper trading client.
        
        Args:
            kalshi_client: Real KalshiClient for market data
            starting_balance: Starting virtual balance in USD
            simulate_slippage: Simulate realistic slippage
            max_slippage_pct: Maximum slippage percentage
            save_history: Save trades to file
            history_file: Path to history file
        """
        self.logger = logging.getLogger(__name__)
        
        # Real Kalshi client for market data
        self.real_client = kalshi_client
        
        # Virtual account
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.total_pnl = 0.0
        
        # Slippage simulation
        self.simulate_slippage = simulate_slippage
        self.max_slippage_pct = max_slippage_pct
        
        # Trade tracking
        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_positions: deque = deque(maxlen=1000)
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_fees_paid = 0.0
        
        # History tracking
        self.save_history = save_history
        self.history_file = history_file
        self.trade_history: List[Dict] = []
        
        self.logger.info("=" * 80)
        self.logger.info("📄 PAPER TRADING MODE ENABLED")
        self.logger.info("=" * 80)
        self.logger.info(f"💰 Starting Balance: ${starting_balance:.2f}")
        self.logger.info(f"📊 Market Data: REAL (Kalshi Production)")
        self.logger.info(f"💸 Order Execution: SIMULATED (Instant fills)")
        self.logger.info(f"📈 Slippage: {'ENABLED' if simulate_slippage else 'DISABLED'}")
        self.logger.info("=" * 80)
    
    async def authenticate(self) -> bool:
        """Use real client authentication."""
        return await self.real_client.authenticate()
    
    async def verify_connection(self) -> bool:
        """Use real client connection."""
        return await self.real_client.verify_connection()
    
    async def get_balance(self) -> float:
        """Get virtual balance."""
        return self.current_balance
    
    async def get_markets(self, status: str = "open", limit: int = 1000, filter_untradeable: bool = True) -> List[Market]:
        """Get REAL markets from Kalshi."""
        return await self.real_client.get_markets(status=status, limit=limit, filter_untradeable=filter_untradeable)
    
    async def get_market(self, market_id: str) -> Market:
        """Get REAL market data from Kalshi."""
        return await self.real_client.get_market(market_id)
    
    def _calculate_slippage(self, side: str) -> float:
        """
        Calculate realistic slippage for order.
        
        Args:
            side: 'buy' or 'sell'
        
        Returns:
            Slippage percentage (can be negative for favorable slippage)
        """
        if not self.simulate_slippage:
            return 0.0
        
        import random
        
        # Simulate realistic slippage:
        # - Buy orders: usually pay slightly more (positive slippage)
        # - Sell orders: usually get slightly less (negative slippage)
        # - Occasionally get favorable slippage
        
        if side.lower() == "buy":
            # 80% chance of positive slippage (worse fill)
            # 20% chance of negative slippage (better fill)
            if random.random() < 0.8:
                return random.uniform(0, self.max_slippage_pct)
            else:
                return -random.uniform(0, self.max_slippage_pct / 2)
        else:  # sell
            # Similar but reversed
            if random.random() < 0.8:
                return -random.uniform(0, self.max_slippage_pct)
            else:
                return random.uniform(0, self.max_slippage_pct / 2)
    
    async def create_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit"
    ) -> Order:
        """
        Simulate order execution.
        
        Args:
            market_id: Market ID
            side: 'buy' or 'sell'
            quantity: Number of contracts
            price: Limit price
            order_type: 'limit' or 'market'
        
        Returns:
            Order object (simulated)
        """
        # Generate order ID
        order_id = f"paper_{len(self.orders) + 1}_{int(datetime.now().timestamp())}"
        
        # Calculate slippage
        slippage = self._calculate_slippage(side)
        
        # Create paper order (auto-fills)
        paper_order = PaperOrder(
            order_id=order_id,
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=price,
            slippage=slippage
        )
        
        # Check if we have enough balance
        order_cost = paper_order.avg_fill_price * quantity
        if order_cost > self.current_balance:
            self.logger.error(
                f"❌ Insufficient balance: need ${order_cost:.2f}, "
                f"have ${self.current_balance:.2f}"
            )
            raise Exception("Insufficient balance for paper trade")
        
        # Deduct from balance
        self.current_balance -= order_cost
        
        # Store order
        self.orders[order_id] = paper_order
        
        # Log
        slippage_str = f"{slippage:+.2%}" if slippage != 0 else "none"
        self.logger.info(
            f"📝 Paper Order Filled: {side.upper()} {quantity} @ ${price:.4f} "
            f"(actual: ${paper_order.avg_fill_price:.4f}, slippage: {slippage_str}) | "
            f"Market: {market_id[:12]}... | "
            f"Balance: ${self.current_balance:.2f}"
        )
        
        # Convert to real Order object for compatibility
        return paper_order.to_real_order()
    
    def record_position_close(
        self,
        position: PaperPosition,
        exit_price: float,
        exit_fee: float,
        net_pnl: float,
        return_pct: float
    ):
        """
        Record a closed position.
        
        Args:
            position: Position that was closed
            exit_price: Exit price
            exit_fee: Exit fee
            net_pnl: Net P&L
            return_pct: Return percentage
        """
        position.closed_at = datetime.now()
        position.exit_price = exit_price
        position.exit_fee = exit_fee
        position.net_pnl = net_pnl
        position.return_pct = return_pct
        
        # Update balance
        position.exit_revenue = (exit_price * position.quantity) - exit_fee
        self.current_balance += position.exit_revenue
        
        # Update P&L
        self.total_pnl += net_pnl
        self.total_fees_paid += position.entry_fee + exit_fee
        
        # Update statistics
        self.total_trades += 1
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Move to history
        self.closed_positions.append(position)
        
        # Save trade history
        if self.save_history:
            self._save_trade_to_history(position)
        
        # Log
        emoji = "🟢" if net_pnl > 0 else "🔴"
        self.logger.info(
            f"{emoji} Position Closed: {position.position_id} | "
            f"P&L: ${net_pnl:+.2f} ({return_pct:+.1%}) | "
            f"Balance: ${self.current_balance:.2f} | "
            f"Total P&L: ${self.total_pnl:+.2f}"
        )
    
    def _save_trade_to_history(self, position: PaperPosition):
        """Save trade to JSON file."""
        trade_record = {
            "timestamp": position.closed_at.isoformat(),
            "position_id": position.position_id,
            "market_id": position.market_id,
            "side": position.side,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": position.exit_price,
            "holding_time_seconds": (position.closed_at - position.opened_at).total_seconds(),
            "gross_pnl": (position.exit_price - position.entry_price) * position.quantity,
            "total_fees": position.entry_fee + (position.exit_fee or 0),
            "net_pnl": position.net_pnl,
            "return_pct": position.return_pct,
            "balance_after": self.current_balance
        }
        
        self.trade_history.append(trade_record)
        
        # Save to file
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.trade_history, f, indent=2)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        win_rate = (
            self.winning_trades / self.total_trades * 100 
            if self.total_trades > 0 
            else 0
        )
        
        avg_pnl = (
            self.total_pnl / self.total_trades 
            if self.total_trades > 0 
            else 0
        )
        
        return_pct = (
            (self.current_balance - self.starting_balance) / self.starting_balance * 100
        )
        
        return {
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "total_pnl": self.total_pnl,
            "return_pct": return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "avg_pnl_per_trade": avg_pnl,
            "total_fees_paid": self.total_fees_paid,
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed_positions)
        }
    
    def print_summary(self):
        """Print trading summary."""
        stats = self.get_statistics()
        
        print("\n" + "="*80)
        print("📊 PAPER TRADING SUMMARY")
        print("="*80)
        print(f"Starting Balance:  ${stats['starting_balance']:>12.2f}")
        print(f"Current Balance:   ${stats['current_balance']:>12.2f}")
        print(f"Total P&L:         ${stats['total_pnl']:>+12.2f}")
        print(f"Return:            {stats['return_pct']:>+12.1f}%")
        print("-"*80)
        print(f"Total Trades:      {stats['total_trades']:>12}")
        print(f"Winning Trades:    {stats['winning_trades']:>12}")
        print(f"Losing Trades:     {stats['losing_trades']:>12}")
        print(f"Win Rate:          {stats['win_rate']:>12.1f}%")
        print(f"Avg P&L/Trade:     ${stats['avg_pnl_per_trade']:>+12.2f}")
        print(f"Total Fees Paid:   ${stats['total_fees_paid']:>12.2f}")
        print("-"*80)
        print(f"Open Positions:    {stats['open_positions']:>12}")
        print(f"Closed Positions:  {stats['closed_positions']:>12}")
        print("="*80 + "\n")

    async def close(self):
        """Close client (pass through to real client)."""
        await self.real_client.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
        # Print final summary
        self.print_summary()
