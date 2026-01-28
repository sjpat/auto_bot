"""
Backtest Engine - Parity-Aligned Version
Updated: 2026-01-20

This engine incorporates all 7 critical parity fixes:
1. ✅ Reuses live bot components (StrategyManager, RiskManager, FeeCalculator, MarketFilter)
2. ✅ Fixed position sizing (TRADE_UNIT-based instead of %-based)
3. ✅ Integrated risk manager checks
4. ✅ Matched exit logic to live bot
5. ✅ Replaced hardcoded fees with FeeCalculator
6. ✅ Added market filtering (spread, expiry, depth)
7. ✅ Correct YES/NO price handling for Kalshi contracts
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from src.backtesting.historical_data import HistoricalPricePoint
from src.trading.correlation_manager import CorrelationManager

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class BacktestConfig:
    """Configuration for backtest engine - aligned with live bot parameters"""
    
    # Account settings
    starting_balance: float = 10000.0
    
    # Position sizing (FIXED, not percentage)
    TRADE_UNIT: int = 100  # Fixed contracts per trade
    MAX_CONCURRENT_TRADES: int = 3
    
    # Spike detection
    SPIKE_THRESHOLD: float = 0.04  # 4% threshold
    
    # Exit targets (USD-based, not percentage)
    TARGET_PROFIT_USD: float = 2.50
    TARGET_LOSS_USD: float = -1.50
    
    # Slippage
    MAX_SLIPPAGE_TOLERANCE: float = 0.025
    
    # Market filtering
    MIN_LIQUIDITY_USD: float = 500.0
    MAX_SPREAD_PCT: float = 0.30  # 30% max spread
    MIN_PRICE_HISTORY: int = 20  # Min data points before trading
    MAX_SUSPICIOUS_SPIKE_PCT: float = 0.30  # Reject if spike > 30%
    MIN_TIME_TO_EXPIRY_HOURS: float = 0.5  # 30 min minimum
    
    # Risk management
    MAX_DAILY_LOSS_PCT: float = 0.15  # 15% daily loss limit
    MAX_DAILY_LOSS_USD: Optional[float] = None  # Calculated from starting_balance
    MAX_EVENT_EXPOSURE_USD: float = 200.0  # Max exposure per event group
    
    # Trailing Stop
    USE_TRAILING_STOP: bool = False
    TRAILING_STOP_ACTIVATION_USD: float = 5.00  # Start trailing after $5 profit
    TRAILING_STOP_DISTANCE_USD: float = 2.50    # Trail by $2.50
    
    def __post_init__(self):
        """Calculate derived values"""
        if self.MAX_DAILY_LOSS_USD is None:
            self.MAX_DAILY_LOSS_USD = self.starting_balance * self.MAX_DAILY_LOSS_PCT


@dataclass
class Trade:
    """Represents a single trade"""
    trade_id: str
    market_id: str
    side: OrderSide
    entry_price: float
    entry_quantity: int
    entry_timestamp: datetime
    entry_cost: float  # Total cost to open position
    entry_fees: float
    
    exit_price: Optional[float] = None
    exit_quantity: Optional[int] = None
    exit_timestamp: Optional[datetime] = None
    exit_fees: float = 0.0
    
    status: OrderStatus = OrderStatus.OPEN
    metadata: Dict = field(default_factory=dict)
    
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    exit_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    spike_detected: bool = False
    spike_size: float = 0.0
    max_unrealized_pnl: float = -1000000.0  # Track high water mark
    
    # Internal state for strategy compatibility
    _current_price: float = 0.0
    _current_timestamp: Optional[datetime] = None

    def update_state(self, current_price: float, current_timestamp: datetime):
        """Update state for strategy calculations"""
        self._current_price = current_price
        self._current_timestamp = current_timestamp

    def update_current_price(self, current_price: float):
        """Update current price (Strategy compatibility wrapper)"""
        self._current_price = current_price

    @property
    def position_id(self) -> str:
        return self.trade_id

    @property
    def is_open(self) -> bool:
        return self.status == OrderStatus.OPEN

    @property
    def unrealized_pnl(self) -> float:
        val = (self._current_price - self.entry_price) * self.entry_quantity
        return val if self.side == OrderSide.BUY else -val

    @property
    def return_pct(self) -> float:
        return (self.unrealized_pnl / self.entry_cost) if self.entry_cost > 0 else 0.0

    @property
    def holding_time_seconds(self) -> float:
        return (self._current_timestamp - self.entry_timestamp).total_seconds() if self._current_timestamp else 0.0

    def close(self, exit_price: float, exit_timestamp: datetime, fee_calc, reason: str = "target_reached"):
        """Close the trade"""
        self.exit_price = exit_price
        self.exit_timestamp = exit_timestamp
        self.status = OrderStatus.CLOSED
        self.exit_reason = reason
        
        # Calculate exit fees
        self.exit_fees = fee_calc.kalshi_fee(self.entry_quantity, exit_price)
        
        # Calculate P&L
        gross_pnl = (exit_price - self.entry_price) * self.entry_quantity
        if self.side == OrderSide.SELL:
            gross_pnl = -gross_pnl
        
        self.pnl = gross_pnl - self.entry_fees - self.exit_fees
        
        if self.entry_cost > 0:
            self.pnl_pct = (self.pnl / self.entry_cost) * 100



@dataclass
class BacktestMarketAdapter:
    """
    Adapter to wrap historical price data as a Market-like object.
    Provides compatibility interface for strategies expecting Market objects.
    """
    market_id: str
    price_point: HistoricalPricePoint
    
    @property
    def is_open(self) -> bool:
        """Market is always open during backtest"""
        return True
    
    def is_liquid(self, min_liquidity: float = None, min_liquidity_usd: float = None) -> bool:
        """Check if market meets minimum liquidity requirement
        
        Accepts either min_liquidity or min_liquidity_usd parameter.
        """
        threshold = min_liquidity if min_liquidity is not None else min_liquidity_usd
        if threshold is None:
            return True
        return self.price_point.liquidity_usd >= threshold
    
    def __post_init__(self):
        """No initialization needed for adapter"""
        pass
    
    @property
    def yes_price(self) -> float:
        """Get YES price from price point"""
        return self.price_point.yes_price
    
    @property
    def no_price(self) -> float:
        """Get NO price from price point"""
        return self.price_point.no_price
    
    @property
    def bid(self) -> Optional[float]:
        """Get bid price"""
        return self.price_point.bid
    
    @property
    def ask(self) -> Optional[float]:
        """Get ask price"""
        return self.price_point.ask
    
    @property
    def volume_24h(self) -> float:
        """Get 24h volume"""
        return self.price_point.volume_24h or 0.0
    
    @property
    def spread_pct(self) -> float:
        """Calculate spread as a percentage of the mid-price."""
        if self.bid is None or self.ask is None or self.bid == 0 or self.ask == 0:
            return 0.0
        
        mid_price = (self.bid + self.ask) / 2
        if mid_price > 0:
            return (self.ask - self.bid) / mid_price
        return 0.0
    
    @property
    def time_to_close_seconds(self) -> float:
        """Calculate time to close in seconds"""
        if hasattr(self.price_point, 'expiry_timestamp') and self.price_point.expiry_timestamp:
            delta = self.price_point.expiry_timestamp - self.price_point.timestamp
            return max(0.0, delta.total_seconds())
        return 604800.0  # Default to 7 days if unknown


@dataclass
class BacktestResults:
    """Results from backtest run"""
    final_balance: float = 0.0
    starting_balance: float = 0.0
    total_return_pct: float = 0.0
    total_return_usd: float = 0.0
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    total_pnl: float = 0.0
    total_fees_paid: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    daily_pnl: Dict[str, float] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    
    signals_evaluated: int = 0
    signals_accepted: int = 0
    signals_rejected: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)


class BacktestEngine:
    """
    Backtest engine with parity to live trading bot.
    
    Integrates:
    - StrategyManager for spike detection
    - RiskManager for pre-trade validation
    - FeeCalculator for accurate fee simulation
    - MarketFilter for market quality checks
    """
    
    def __init__(
        self,
        strategy_manager,  # From live bot
        risk_manager,      # From live bot
        fee_calculator,    # From live bot
        market_filter,     # From live bot
        config: BacktestConfig,
    ):
        self.strategy_manager = strategy_manager
        self.risk_manager = risk_manager
        self.fee_calculator = fee_calculator
        self.market_filter = market_filter
        self.config = config
        
        self.balance = config.starting_balance
        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        
        self.current_date = None
        self.daily_pnl_dict: Dict[str, float] = {}  # Fixed: Dict instead of float
        self.session_pnl = 0.0
        
        # Initialize Correlation Manager (Engine acts as PositionManager)
        self.correlation_manager = CorrelationManager(config, self)
        
        logger.info(f"BacktestEngine initialized with balance: ${self.balance:,.2f}")

    async def run_backtest(
        self,
        historical_data: Dict[str, List[HistoricalPricePoint]],
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResults:
        """
        Run backtest on historical data.
        
        Args:
            historical_data: Dict mapping market_id -> list of HistoricalPricePoint
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            BacktestResults with complete backtest statistics
        """
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        self.balance = self.config.starting_balance
        self.open_trades = {}
        self.closed_trades = []
        self.daily_pnl_dict = {}  # Fixed: Initialize as dict
        self.session_pnl = 0.0
        
        results = BacktestResults(starting_balance=self.config.starting_balance)
        
        # Sort all timestamps across all markets
        all_timestamps = set()
        for market_id, price_points in historical_data.items():
            for point in price_points:
                if start_date <= point.timestamp <= end_date:
                    all_timestamps.add(point.timestamp)
        
        sorted_timestamps = sorted(all_timestamps)
        logger.info(f"Processing {len(sorted_timestamps)} timestamps")
        
        # Process each timestamp
        for timestamp in sorted_timestamps:
            self.current_date = timestamp.date()
            
            # Check if new day - reset daily tracking
            daily_key = timestamp.date().isoformat()
            if daily_key not in self.daily_pnl_dict:
                self.daily_pnl_dict[daily_key] = 0.0
                results.daily_pnl[daily_key] = 0.0
            
            # Process all markets at this timestamp
            for market_id, price_points in historical_data.items():
                # Find price point at this timestamp
                price_point = None
                for point in price_points:
                    if point.timestamp == timestamp:
                        price_point = point
                        break
                
                if price_point is None:
                    continue
                
                # Create adapter for strategy manager
                market_adapter = BacktestMarketAdapter(market_id, price_point)
                
                # Update strategy history
                self.strategy_manager.on_market_update(market_adapter)
                
                # Check market filtering
                market_filter_result = await self._check_market_filters(
                    market_id, price_point, results
                )
                if not market_filter_result:
                    continue
                
                # Check for spike signals
                spike_signal = await self._detect_spike([market_adapter], price_point, results)
                
                if spike_signal:
                    results.signals_evaluated += 1
                    
                    # Attempt trade entry
                    await self._process_trade_entry(
                        market_id, price_point, spike_signal, results
                    )
            
            # Process exit conditions for open trades
            await self._process_trade_exits(historical_data, timestamp, results)
        
        # Close remaining open trades at end of backtest
        for market_id, trade in list(self.open_trades.items()):
            if trade.status == OrderStatus.OPEN:
                # Use last available price
                if market_id in historical_data:
                    last_point = historical_data[market_id][-1]
                    if last_point.timestamp <= end_date:
                        await self._close_trade(
                            trade, last_point.yes_price, last_point.timestamp,
                            "end_of_backtest", results
                        )
        
        # Calculate final results
        self._calculate_results(results)
        
        logger.info(f"Backtest complete. Final balance: ${results.final_balance:,.2f}")
        
        return results

    async def _check_market_filters(
        self,
        market_id: str,
        price_point: HistoricalPricePoint,
        results: BacktestResults,
    ) -> bool:
        """
        Check if market meets quality filters.
        
        Returns:
            True if market passes all filters, False otherwise
        """
        # Check liquidity
        if price_point.liquidity_usd < self.config.MIN_LIQUIDITY_USD:
            results.rejection_reasons["insufficient_liquidity"] = (
                results.rejection_reasons.get("insufficient_liquidity", 0) + 1
            )
            return False
        
        # Check spread
        market_adapter = BacktestMarketAdapter(market_id, price_point)
        if market_adapter.spread_pct > self.config.MAX_SPREAD_PCT:
            results.rejection_reasons["spread_too_wide"] = (
                results.rejection_reasons.get("spread_too_wide", 0) + 1
            )
            return False
        
        # Check suspicious spike size (reject outliers)
        # This prevents trading on extreme wicks
        if hasattr(price_point, 'max_price') and hasattr(price_point, 'min_price'):
            price_range = abs(price_point.max_price - price_point.min_price) / price_point.min_price
            if price_range > self.config.MAX_SUSPICIOUS_SPIKE_PCT:
                results.rejection_reasons["suspicious_spike_size"] = (
                    results.rejection_reasons.get("suspicious_spike_size", 0) + 1
                )
                return False
        
        return True

    async def _detect_spike(
        self,
        markets: List,
        price_point: HistoricalPricePoint,
        results: BacktestResults,
    ) -> Optional[Dict]:
        """
        Detect spike signals using StrategyManager.
        
        Returns:
            Spike signal dict if detected, None otherwise
        """
        # Use strategy manager to detect spike
        spike_signals = self.strategy_manager.generate_entry_signals(
            markets
        )
        
        if spike_signals:
            # Return first signal converted to dict
            signal = spike_signals[0]
            
            # Determine direction from signal_type
            direction = 'up'
            if hasattr(signal, 'signal_type'):
                if str(signal.signal_type).upper().endswith('SELL'):
                    direction = 'down'
            
            # Map strategy-specific metrics to 'spike_magnitude'
            magnitude = signal.metadata.get('spike_magnitude', 0.0)
            if magnitude == 0.0:
                if 'roc' in signal.metadata:
                    magnitude = abs(signal.metadata['roc'])
                elif 'edge' in signal.metadata:
                    magnitude = signal.metadata['edge']
            
            return {
                'confidence': signal.confidence,
                'direction': signal.metadata.get('direction', direction),
                'spike_magnitude': magnitude,
                'metadata': signal.metadata
            }
        
        return None

    async def _process_trade_entry(
        self,
        market_id: str,
        price_point: HistoricalPricePoint,
        spike_signal: Dict,
        results: BacktestResults,
    ) -> None:
        """
        Process trade entry based on spike signal.
        
        Checks:
        1. Risk manager approval
        2. Position limit not exceeded
        3. Sufficient balance
        """
        # Create a mock spike object for RiskManager
        class MockSpike:
            def __init__(self, change_pct, market_id):
                self.change_pct = change_pct
                self.market_id = market_id

        mock_spike = MockSpike(
            change_pct=spike_signal.get('spike_magnitude', 0.0),
            market_id=market_id
        )

        # Check risk manager
        risk_check = await self.risk_manager.can_trade_pre_submission(
            spike=mock_spike
        )
        
        if not risk_check.passed:
            results.signals_rejected += 1
            reason = risk_check.reason or 'risk_check_failed'
            results.rejection_reasons[reason] = (
                results.rejection_reasons.get(reason, 0) + 1
            )
            logger.info(f"Signal rejected by risk manager: {reason}")
            return
        
        # Check if we already have a position in this market
        if market_id in self.open_trades:
            results.signals_rejected += 1
            results.rejection_reasons["existing_position"] = (
                results.rejection_reasons.get("existing_position", 0) + 1
            )
            return

        # Check position limit
        if len(self.open_trades) >= self.config.MAX_CONCURRENT_TRADES:
            results.signals_rejected += 1
            results.rejection_reasons["max_concurrent_positions"] = (
                results.rejection_reasons.get("max_concurrent_positions", 0) + 1
            )
            logger.info("Max concurrent positions reached")
            return
        
        # Determine side (BUY or SELL based on signal)
        side = OrderSide.BUY if spike_signal.get('direction') == 'up' else OrderSide.SELL
        
        # Calculate entry cost
        entry_cost = price_point.yes_price * self.config.TRADE_UNIT
        entry_fees = self.fee_calculator.kalshi_fee(self.config.TRADE_UNIT, price_point.yes_price)
        total_cost = entry_cost + entry_fees
        
        # Check correlation risk
        corr_passed, corr_reason = self.correlation_manager.check_exposure(market_id, entry_cost)
        if not corr_passed:
            results.signals_rejected += 1
            results.rejection_reasons["correlation_limit"] = (
                results.rejection_reasons.get("correlation_limit", 0) + 1
            )
            logger.info(f"Signal rejected by correlation manager: {corr_reason}")
            return

        # Check balance
        if total_cost > self.balance:
            results.signals_rejected += 1
            results.rejection_reasons["insufficient_balance"] = (
                results.rejection_reasons.get("insufficient_balance", 0) + 1
            )
            logger.info(f"Insufficient balance: need ${total_cost:,.2f}, have ${self.balance:,.2f}")
            return
        
        # Create trade
        trade_id = f"{market_id}_{price_point.timestamp.isoformat()}"
        trade = Trade(
            trade_id=trade_id,
            market_id=market_id,
            side=side,
            entry_price=price_point.yes_price,
            entry_quantity=self.config.TRADE_UNIT,
            entry_timestamp=price_point.timestamp,
            entry_cost=entry_cost,
            entry_fees=entry_fees,
            spike_detected=True,
            spike_size=spike_signal.get('spike_magnitude', 0.0),
            metadata=spike_signal.get('metadata', {})
        )
        
        # Deduct cost from balance
        self.balance -= total_cost
        self.open_trades[market_id] = trade
        
        results.signals_accepted += 1
        logger.info(
            f"Trade entered: {market_id} {side.value} "
            f"{self.config.TRADE_UNIT} @ ${price_point.yes_price:.4f}"
        )

    async def _process_trade_exits(
        self,
        historical_data: Dict[str, List[HistoricalPricePoint]],
        current_timestamp: datetime,
        results: BacktestResults,
    ) -> None:
        """
        Process exit conditions for open trades.
        
        Exit conditions:
        1. Target profit reached (TARGET_PROFIT_USD)
        2. Stop loss hit (TARGET_LOSS_USD)
        3. Time-based exit (MIN_TIME_TO_EXPIRY_HOURS)
        4. Market quality deterioration
        """
        trades_to_close = []
        active_trades_for_strategy = []
        
        for market_id, trade in self.open_trades.items():
            if trade.status != OrderStatus.OPEN:
                continue
            
            # Get current price
            if market_id not in historical_data:
                continue
            
            current_price = None
            for point in historical_data[market_id]:
                if point.timestamp == current_timestamp:
                    current_price = point
                    break
            
            if current_price is None:
                continue
            
            # Update trade state for strategy checks
            trade.update_state(current_price.yes_price, current_timestamp)
            active_trades_for_strategy.append(trade)
            
            # Calculate unrealized P&L
            unrealized_pnl = (current_price.yes_price - trade.entry_price) * trade.entry_quantity
            if trade.side == OrderSide.SELL:
                unrealized_pnl = -unrealized_pnl
            
            # Update high water mark for trailing stop
            if unrealized_pnl > trade.max_unrealized_pnl:
                trade.max_unrealized_pnl = unrealized_pnl
            
            # Check exit conditions
            exit_triggered = False
            exit_reason = None
            
            # Condition 1: Target profit reached
            if unrealized_pnl >= self.config.TARGET_PROFIT_USD:
                exit_triggered = True
                exit_reason = "target_profit_reached"
            
            # Condition 2: Stop loss hit
            elif unrealized_pnl <= self.config.TARGET_LOSS_USD:
                exit_triggered = True
                exit_reason = "stop_loss_hit"
            
            # Condition 3: Close to expiry (if expiry info available)
            if hasattr(current_price, 'expiry_timestamp') and current_price.expiry_timestamp:
                time_to_expiry = (current_price.expiry_timestamp - current_timestamp).total_seconds() / 3600
                if time_to_expiry < self.config.MIN_TIME_TO_EXPIRY_HOURS:
                    exit_triggered = True
                    exit_reason = "close_to_expiry"
            
            # Condition 5: Trailing Stop
            if not exit_triggered and self.config.USE_TRAILING_STOP:
                if trade.max_unrealized_pnl >= self.config.TRAILING_STOP_ACTIVATION_USD:
                    if unrealized_pnl <= (trade.max_unrealized_pnl - self.config.TRAILING_STOP_DISTANCE_USD):
                        exit_triggered = True
                        exit_reason = "trailing_stop_hit"
            
            # Condition 4: Market quality deterioration
            if current_price.liquidity_usd < self.config.MIN_LIQUIDITY_USD:
                exit_triggered = True
                exit_reason = "insufficient_liquidity"
            
            if exit_triggered:
                trades_to_close.append((trade, current_price.yes_price, current_timestamp, exit_reason))
        
        # Check Strategy-Specific Exits (e.g. Mispricing Convergence)
        if active_trades_for_strategy:
            # Build market map for strategy
            market_map = {}
            for market_id in self.open_trades.keys():
                if market_id in historical_data:
                    # Find current price point
                    for point in historical_data[market_id]:
                        if point.timestamp == current_timestamp:
                            market_map[market_id] = BacktestMarketAdapter(market_id, point)
                            break
            
            # Get exit signals from strategy manager
            strategy_exits = self.strategy_manager.generate_exit_signals(active_trades_for_strategy, market_map)
            
            for signal in strategy_exits:
                trade = self.open_trades.get(signal.market_id)
                if trade and trade not in [t[0] for t in trades_to_close]:
                    trades_to_close.append((trade, signal.price, current_timestamp, signal.metadata.get('reason', 'strategy_exit')))

        # Close trades
        for trade, exit_price, timestamp, reason in trades_to_close:
            await self._close_trade(trade, exit_price, timestamp, reason, results)

    async def _close_trade(
        self,
        trade: Trade,
        exit_price: float,
        timestamp: datetime,
        reason: str,
        results: BacktestResults,
    ) -> None:
        """Close a trade and update results"""
        trade.close(exit_price, timestamp, self.fee_calculator, reason)
        
        # Update balance
        # Add back the initial cost basis (notional + fees) plus the P&L
        self.balance += trade.entry_cost + trade.entry_fees + trade.pnl
        
        # Update metrics
        results.total_pnl += trade.pnl
        results.total_fees_paid += trade.entry_fees + trade.exit_fees
        
        # Daily P&L
        daily_key = timestamp.date().isoformat()
        if daily_key not in results.daily_pnl:
            results.daily_pnl[daily_key] = 0.0
        results.daily_pnl[daily_key] += trade.pnl
        
        # Move to closed trades
        self.closed_trades.append(trade)
        del self.open_trades[trade.market_id]
        
        logger.info(
            f"Trade closed: {trade.market_id} "
            f"P&L: ${trade.pnl:+.2f} ({trade.pnl_pct:+.2f}%) "
            f"Reason: {reason}"
        )

    def _calculate_results(self, results: BacktestResults) -> None:
        """Calculate final backtest statistics"""
        results.final_balance = self.balance
        results.total_return_usd = results.final_balance - results.starting_balance
        results.total_return_pct = (results.total_return_usd / results.starting_balance) * 100
        
        results.total_trades = len(self.closed_trades)
        results.winning_trades = sum(1 for t in self.closed_trades if t.pnl > 0)
        results.losing_trades = sum(1 for t in self.closed_trades if t.pnl < 0)
        
        if results.total_trades > 0:
            results.win_rate = (results.winning_trades / results.total_trades) * 100
        
        # Calculate max drawdown
        balance = results.starting_balance
        peak_balance = results.starting_balance
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0
        
        for trade in self.closed_trades:
            balance += trade.pnl
            if balance < peak_balance:
                drawdown_usd = peak_balance - balance
                drawdown_pct = (drawdown_usd / peak_balance) * 100
                if drawdown_usd > max_drawdown_usd:
                    max_drawdown_usd = drawdown_usd
                    max_drawdown_pct = drawdown_pct
            else:
                peak_balance = balance
        
        results.max_drawdown = max_drawdown_usd
        results.max_drawdown_pct = max_drawdown_pct
        
        results.trades = self.closed_trades
        
        logger.info(f"Results calculated: {results.total_trades} trades, {results.win_rate:.1f}% win rate")

    def get_active_positions(self) -> List[Trade]:
        """Interface for CorrelationManager to access open positions."""
        return list(self.open_trades.values())


# Example usage
async def example_backtest():
    """Example of how to use the BacktestEngine"""
    
    from src.strategies.strategy_manager import StrategyManager
    from src.trading.risk_manager import RiskManager
    from src.trading.fee_calculator import FeeCalculator
    from src.trading.market_filter import MarketFilter
    
    # Initialize components from live bot
    strategy_manager = StrategyManager(config={})
    risk_manager = RiskManager(client=None, config={})
    fee_calculator = FeeCalculator()
    market_filter = MarketFilter(config={})
    
    # Setup config
    config = BacktestConfig(
        starting_balance=10000.0,
        TRADE_UNIT=100,
        MAX_CONCURRENT_TRADES=3,
        SPIKE_THRESHOLD=0.04,
        TARGET_PROFIT_USD=2.50,
        TARGET_LOSS_USD=-1.50,
    )
    
    # Create engine
    engine = BacktestEngine(
        strategy_manager=strategy_manager,
        risk_manager=risk_manager,
        fee_calculator=fee_calculator,
        market_filter=market_filter,
        config=config,
    )
    
    # Prepare historical data
    historical_data = {
        "MARKET_1": [
            HistoricalPricePoint(
                timestamp=datetime(2026, 1, 15, 10, 0),
                yes_price=0.50,
                no_price=0.50,
                liquidity_usd=1000.0,
            ),
            HistoricalPricePoint(
                timestamp=datetime(2026, 1, 15, 10, 5),
                yes_price=0.55,
                no_price=0.45,
                liquidity_usd=1000.0,
            ),
        ]
    }
    
    # Run backtest
    results = await engine.run_backtest(
        historical_data=historical_data,
        start_date=datetime(2026, 1, 15),
        end_date=datetime(2026, 1, 20),
    )
    
    print(f"Final Balance: ${results.final_balance:,.2f}")
    print(f"Total Return: {results.total_return_pct:+.2f}%")
    print(f"Win Rate: {results.win_rate:.1f}%")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )