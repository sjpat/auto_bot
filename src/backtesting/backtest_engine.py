"""
Main backtesting engine for spike trading strategy
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

from .performance_metrics import BacktestResults, TradeRecord
from .historical_data import HistoricalPricePoint

@dataclass
class BacktestConfig:
    """Configuration for backtest run"""
    starting_balance: float = 10000
    spike_threshold: float = 0.10
    max_position_size: float = 100
    position_size_pct: float = 0.02
    stop_loss_pct: float = 0.20
    take_profit_pct: float = 0.30
    max_hold_time: timedelta = timedelta(hours=24)
    min_liquidity: float = 100
    enable_fees: bool = True
    fee_rate: float = 0.07
    max_concurrent_positions: int = 10  # ← Add this line

class BacktestEngine:
    """
    Run spike detection strategy on historical data
    """
    
    def __init__(
        self,
        spike_detector,
        config: BacktestConfig,
        fee_calculator=None
    ):
        self.spike_detector = spike_detector
        self.config = config
        self.fee_calculator = fee_calculator
        self.logger = logging.getLogger(__name__)
        
        # State
        self.balance = config.starting_balance
        self.positions = {}  # market_id -> TradeRecord
        self.closed_trades = []
        self.trade_counter = 0
        
        # Results tracking
        self.equity_curve = [(datetime.now(), self.balance)]
        self.spikes_detected = 0
        self.spikes_traded = 0
        self.rejection_reasons = {}
    
    async def run_backtest(
        self,
        historical_data: Dict[str, List[HistoricalPricePoint]],
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResults:
        """
        Run backtest on historical data.
        
        Args:
            historical_data: Dict mapping market_id to list of price points
            start_date: Start date for backtest
            end_date: End date for backtest
            
        Returns:
            BacktestResults with complete performance metrics
        """
        self.logger.info(f"Starting backtest from {start_date.date()} to {end_date.date()}")
        self.logger.info(f"Testing on {len(historical_data)} markets")
        
        # Reset state
        self.balance = self.config.starting_balance
        self.positions = {}
        self.closed_trades = []
        self.equity_curve = [(start_date, self.balance)]
        
        # Create time-ordered events from all markets
        events = self._create_event_timeline(historical_data, start_date, end_date)
        self.logger.info(f"Processing {len(events)} price events")
        
        # Process events chronologically
        for i, (timestamp, market_id, price_point) in enumerate(events):
            # Update spike detector with new price
            self.spike_detector.add_price(
                market_id=market_id,
                price=price_point.price,
                timestamp=timestamp
            )
            
            # Check for position exits
            await self._check_position_exits(timestamp, price_point)
            
            # Detect spikes
            spikes = self.spike_detector.detect_spikes(
                threshold=self.config.spike_threshold
            )
            
            if spikes:
                self.spikes_detected += len(spikes)
                
                # Evaluate each spike for trading
                for spike in spikes:
                    if spike.market_id == market_id:
                        await self._evaluate_spike(timestamp, spike, price_point)
            
            # Update equity curve periodically
            if i % 100 == 0:
                self.equity_curve.append((timestamp, self.balance))
            
            # Progress logging
            if i % 1000 == 0 and i > 0:
                self.logger.info(f"Processed {i}/{len(events)} events, Balance: ${self.balance:.2f}")
        
        # Close any remaining positions
        await self._close_all_positions(end_date, "backtest_end")
        
        # Calculate final results
        results = self._generate_results(start_date, end_date)
        
        self.logger.info(f"Backtest complete. Final balance: ${results.final_balance:.2f}")
        self.logger.info(f"Total trades: {results.total_trades}, Win rate: {results.win_rate:.1%}")
        
        return results
    
    def _create_event_timeline(
        self,
        historical_data: Dict[str, List[HistoricalPricePoint]],
        start_date: datetime,
        end_date: datetime
    ) -> List[tuple]:
        """
        Create chronological timeline of all price events.
        
        Returns:
            List of (timestamp, market_id, price_point) tuples, sorted by time
        """
        events = []
        
        for market_id, price_points in historical_data.items():
            for point in price_points:
                if start_date <= point.timestamp <= end_date:
                    events.append((point.timestamp, market_id, point))
        
        # Sort by timestamp
        events.sort(key=lambda x: x[0])
        return events
    
    async def _evaluate_spike(
        self,
        timestamp: datetime,
        spike,
        price_point: HistoricalPricePoint
    ):
        """Evaluate whether to trade a detected spike"""
        
        # Skip if already have position in this market
        if spike.market_id in self.positions:
            self._reject_spike("already_in_position")
            return
        
        # Check max concurrent positions
        if len(self.positions) >= self.config.max_concurrent_positions:
            self._reject_spike("max_concurrent_positions")
            return
        
        # Check liquidity
        if price_point.liquidity < self.config.min_liquidity:
            self._reject_spike("insufficient_liquidity")
            return
        
        # Calculate position size
        position_value = self.balance * self.config.position_size_pct
        contracts = int(position_value / spike.current_price)
        
        if contracts == 0:
            self._reject_spike("insufficient_balance")
            return
        
        contracts = min(contracts, self.config.max_position_size)
        
        # Calculate costs
        entry_cost = contracts * spike.current_price
        entry_fee = self._calculate_fee(entry_cost) if self.config.enable_fees else 0
        total_cost = entry_cost + entry_fee
        
        # Check if we can afford it
        if total_cost > self.balance:
            self._reject_spike("insufficient_funds")
            return
        
        # Execute trade
        await self._open_position(
            timestamp=timestamp,
            market_id=spike.market_id,
            entry_price=spike.current_price,
            contracts=contracts,
            entry_cost=entry_cost,
            entry_fee=entry_fee,
            spike=spike,
            price_point=price_point
        )
    
    async def _open_position(
        self,
        timestamp: datetime,
        market_id: str,
        entry_price: float,
        contracts: int,
        entry_cost: float,
        entry_fee: float,
        spike,
        price_point: HistoricalPricePoint
    ):
        """Open a new position"""
        self.trade_counter += 1
        
        # Determine side based on spike direction
        entry_side = 'yes' if spike.direction == 'up' else 'no'
        
        # Create trade record
        trade = TradeRecord(
            trade_id=self.trade_counter,
            market_id=market_id,
            market_title=f"Market_{market_id}",  # Would need to fetch actual title
            entry_time=timestamp,
            entry_price=entry_price,
            entry_side=entry_side,
            contracts=contracts,
            entry_cost=entry_cost,
            entry_fee=entry_fee,
            spike_change_pct=spike.change_pct,
            spike_direction=spike.direction
        )
        
        # Update balance
        self.balance -= (entry_cost + entry_fee)
        
        # Track position
        self.positions[market_id] = trade
        self.spikes_traded += 1
        
        self.logger.info(
            f"[{timestamp}] OPEN {entry_side.upper()}: {market_id} | "
            f"{contracts} contracts @ ${entry_price:.4f} | "
            f"Spike: {spike.change_pct:+.1%}"
        )
    
    async def _check_position_exits(
        self,
        timestamp: datetime,
        price_point: HistoricalPricePoint
    ):
        """Check if any open positions should be closed"""
        
        if price_point.market_id not in self.positions:
            return
        
        trade = self.positions[price_point.market_id]
        current_price = price_point.price
        
        # Calculate current P&L
        hold_time = timestamp - trade.entry_time
        
        if trade.entry_side == 'yes':
            unrealized_pnl = (current_price - trade.entry_price) * trade.contracts
        else:  # 'no' side
            unrealized_pnl = (trade.entry_price - current_price) * trade.contracts
        
        pnl_pct = unrealized_pnl / trade.entry_cost if trade.entry_cost > 0 else 0
        
        # Check exit conditions
        exit_reason = None
        
        # Stop loss
        if pnl_pct <= -self.config.stop_loss_pct:
            exit_reason = "stop_loss"
        
        # Take profit
        elif pnl_pct >= self.config.take_profit_pct:
            exit_reason = "take_profit"
        
        # Max hold time
        elif hold_time >= self.config.max_hold_time:
            exit_reason = "max_hold_time"
        
        # Execute exit if triggered
        if exit_reason:
            await self._close_position(
                timestamp=timestamp,
                market_id=price_point.market_id,
                exit_price=current_price,
                exit_reason=exit_reason
            )
    
    async def _close_position(
        self,
        timestamp: datetime,
        market_id: str,
        exit_price: float,
        exit_reason: str
    ):
        """Close an open position"""
        
        if market_id not in self.positions:
            return
        
        trade = self.positions[market_id]
        
        # Calculate exit details
        exit_revenue = trade.contracts * exit_price
        exit_fee = self._calculate_fee(exit_revenue) if self.config.enable_fees else 0
        
        # Close the trade
        trade.close_trade(
            exit_time=timestamp,
            exit_price=exit_price,
            exit_fee=exit_fee,
            exit_reason=exit_reason
        )
        
        # Update balance
        self.balance += exit_revenue - exit_fee
        
        # Move to closed trades
        self.closed_trades.append(trade)
        del self.positions[market_id]
        
        # Update equity curve
        self.equity_curve.append((timestamp, self.balance))
        
        self.logger.info(
            f"[{timestamp}] CLOSE {trade.entry_side.upper()}: {market_id} | "
            f"Exit @ ${exit_price:.4f} | P&L: ${trade.net_pnl:+.2f} ({trade.return_pct:+.1%}) | "
            f"Reason: {exit_reason}"
        )
    
    async def _close_all_positions(self, timestamp: datetime, reason: str):
        """Close all open positions at end of backtest"""
        for market_id in list(self.positions.keys()):
            trade = self.positions[market_id]
            # Close at entry price (neutral exit)
            await self._close_position(
                timestamp=timestamp,
                market_id=market_id,
                exit_price=trade.entry_price,
                exit_reason=reason
            )
    
    def _calculate_fee(self, notional: float) -> float:
        """Calculate trading fees"""
        # if self.fee_calculator:
        #     return self.fee_calculator.kalshi_fee(notional)
        return notional * self.config.fee_rate
    
    def _reject_spike(self, reason: str):
        """Track rejected spike"""
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
    
    def _generate_results(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResults:
        """Generate final backtest results"""
        
        results = BacktestResults(
            start_date=start_date,
            end_date=end_date,
            starting_balance=self.config.starting_balance,
            spike_threshold=self.config.spike_threshold,
            final_balance=self.balance,
            spikes_detected=self.spikes_detected,
            spikes_traded=self.spikes_traded,
            spikes_rejected=self.spikes_detected - self.spikes_traded,
            rejection_reasons=self.rejection_reasons,
            trades=self.closed_trades,
            equity_curve=self.equity_curve
        )
        
        # Calculate all metrics
        results.calculate_metrics()
        
        return results

