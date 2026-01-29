"""
Performance metrics and tracking for backtesting
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import statistics


@dataclass
class TradeRecord:
    """Record of a single trade"""

    trade_id: int
    market_id: str
    market_title: str

    # Entry
    entry_time: datetime
    entry_price: float
    entry_side: str  # 'yes' or 'no'
    contracts: int
    entry_cost: float
    entry_fee: float

    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_revenue: Optional[float] = None
    exit_fee: Optional[float] = None
    exit_reason: Optional[str] = None

    # P&L
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    hold_time: Optional[timedelta] = None

    # Spike info
    spike_change_pct: float = 0.0
    spike_direction: str = ""

    def close_trade(self, exit_time, exit_price, exit_fee, exit_reason):
        """Close the trade and calculate P&L"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_fee = exit_fee
        self.exit_reason = exit_reason
        self.hold_time = exit_time - self.entry_time

        if self.entry_side == "yes":
            # YES position: profit when price goes up
            entry_value = self.contracts * self.entry_price
            exit_value = self.contracts * self.exit_price
            self.gross_pnl = exit_value - entry_value
        else:
            entry_value = self.contracts * (1.0 - self.entry_price)
            exit_value = self.contracts * (1.0 - self.exit_price)
            self.gross_pnl = exit_value - entry_value

        self.net_pnl = self.gross_pnl - self.entry_fee - self.exit_fee
        self.return_pct = self.net_pnl / entry_value if entry_value > 0 else 0

    def is_winning_trade(self) -> bool:
        """Check if trade was profitable"""
        return self.net_pnl is not None and self.net_pnl > 0


@dataclass
class BacktestResults:
    """Complete results from a backtest run"""

    # Configuration
    start_date: datetime
    end_date: datetime
    starting_balance: float
    spike_threshold: float

    # Trading statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L metrics
    final_balance: float = 0.0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    total_fees_paid: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_consecutive_losses: int = 0

    # Spike detection metrics
    spikes_detected: int = 0
    spikes_traded: int = 0
    spikes_rejected: int = 0
    rejection_reasons: dict = field(default_factory=dict)

    # Per-trade statistics
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_hold_time: Optional[timedelta] = None

    # Trade log
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)  # (timestamp, balance)

    def calculate_metrics(self):
        """Calculate all performance metrics from trade history"""
        if not self.trades:
            return

        # Basic counts
        self.total_trades = len(self.trades)
        self.winning_trades = sum(1 for t in self.trades if t.is_winning_trade())
        self.losing_trades = self.total_trades - self.winning_trades
        self.win_rate = (
            self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        )

        # P&L calculations
        winning_pnls = [t.net_pnl for t in self.trades if t.is_winning_trade()]
        losing_pnls = [t.net_pnl for t in self.trades if not t.is_winning_trade()]

        self.gross_profit = sum(winning_pnls) if winning_pnls else 0
        self.gross_loss = abs(sum(losing_pnls)) if losing_pnls else 0
        self.total_pnl = sum(t.net_pnl for t in self.trades if t.net_pnl)
        self.profit_factor = (
            self.gross_profit / self.gross_loss if self.gross_loss > 0 else float("inf")
        )
        self.total_fees_paid = sum(t.entry_fee + (t.exit_fee or 0) for t in self.trades)

        # Per-trade stats
        self.avg_win = statistics.mean(winning_pnls) if winning_pnls else 0
        self.avg_loss = statistics.mean(losing_pnls) if losing_pnls else 0
        self.largest_win = max(winning_pnls) if winning_pnls else 0
        self.largest_loss = min(losing_pnls) if losing_pnls else 0

        # Hold time - FIX HERE
        hold_times = [t.hold_time for t in self.trades if t.hold_time is not None]
        if hold_times:
            avg_seconds = sum(ht.total_seconds() for ht in hold_times) / len(hold_times)
            self.avg_hold_time = timedelta(seconds=avg_seconds)
        else:
            self.avg_hold_time = None  # Keep as None if no hold times

        # Drawdown calculation
        self._calculate_drawdown()

        # Sharpe ratio
        self._calculate_sharpe_ratio()

        # Consecutive losses
        self._calculate_max_consecutive_losses()

    def _calculate_drawdown(self):
        """Calculate maximum drawdown"""
        if not self.equity_curve:
            return

        peak = self.starting_balance
        max_dd = 0
        max_dd_pct = 0

        for timestamp, balance in self.equity_curve:
            if balance > peak:
                peak = balance

            drawdown = peak - balance
            drawdown_pct = drawdown / peak if peak > 0 else 0

            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct

        self.max_drawdown = max_dd
        self.max_drawdown_pct = max_dd_pct

    def _calculate_sharpe_ratio(self):
        """Calculate Sharpe ratio (assuming risk-free rate = 0)"""
        if len(self.trades) < 2:
            self.sharpe_ratio = 0
            return

        returns = [t.return_pct for t in self.trades if t.return_pct is not None]
        if not returns:
            self.sharpe_ratio = 0
            return

        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        self.sharpe_ratio = mean_return / std_return if std_return > 0 else 0

    def _calculate_max_consecutive_losses(self):
        """Calculate maximum consecutive losing trades"""
        max_losses = 0
        current_losses = 0

        for trade in self.trades:
            if trade.is_winning_trade():
                current_losses = 0
            else:
                current_losses += 1
                max_losses = max(max_losses, current_losses)

        self.max_consecutive_losses = max_losses
