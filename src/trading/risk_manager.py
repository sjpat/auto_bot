# src/trading/risk_manager.py

"""
Risk Management System for Kalshi Spike Bot

Implements 14 risk vectors with 3-layer defense strategy:
- Layer 1: Pre-trade checks (prevent bad trades)
- Layer 2: During-trade monitoring (catch execution problems)
- Layer 3: Post-trade management (exit quickly)

Priority Order:
1. CRITICAL (Week 1): Risks #12, #13, #8, #14 (5 hours)
2. HIGH (Week 2): Risks #1-7, #10 (12 hours)
3. MEDIUM (Week 3): Risks #9, #11 (3 hours)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional, List
from collections import deque
from dataclasses import dataclass, field


# ============================================================================
# CRITICAL RISK #12: Account Suspension Detection
# ============================================================================

class AccountStatusMonitor:
    """
    Monitors for account suspension indicators.
    
    Detects:
    - 401 Unauthorized (credentials invalid)
    - 403 Forbidden (account locked)
    - 5+ consecutive API errors (likely suspension)
    
    Action: Halts all trading immediately
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.suspended = False
        self.api_error_count = 0
        self.api_error_threshold = 5
        self.last_error_timestamp = None
        self.last_error = None
        self.error_recovery_window_seconds = 300  # 5 minutes
    
    def handle_api_error(self, status_code: int, error: Exception) -> bool:
        """
        Handle API error and check for suspension indicators.
        
        Args:
            status_code: HTTP status code from API
            error: Exception object
        
        Returns:
            True if account likely suspended, False otherwise
        """
        self.last_error = error
        self.last_error_timestamp = datetime.now()

        # Immediate suspension indicators
        if status_code in [401, 403]:
            self.logger.critical(
                f"🔴 ACCOUNT SUSPENSION DETECTED: {status_code} {error}"
            )
            self.suspended = True
            self.api_error_count += 1
            return True
        
        # Track general errors (5+ = likely suspension)
        self.api_error_count += 1
        self.last_error_timestamp = datetime.now()
        
        if self.api_error_count >= self.api_error_threshold:
            self.logger.error(
                f"🔴 Too many API errors ({self.api_error_count}); "
                f"account may be suspended"
            )
            self.suspended = True
            return True
        
        return False
    
    def reset_error_count(self):
        """Reset error count after successful operation."""
        if self.last_error_timestamp:
            age = (datetime.now() - self.last_error_timestamp).total_seconds()
            if age > self.error_recovery_window_seconds:
                if self.api_error_count > 0:
                    self.logger.info(
                        f"Error count reset from {self.api_error_count} to 0"
                    )
                self.api_error_count = 0
    
    def is_suspended(self) -> bool:
        """Check if account is suspended."""
        return self.suspended
    
    def get_status(self) -> Dict[str, Any]:
        """Get current account status."""
        return {
            'suspended': self.suspended,
            'api_errors': self.api_error_count,
            'last_error': self.last_error,
            'recovery_window': self.error_recovery_window_seconds
        }


# ============================================================================
# CRITICAL RISK #13: Daily Loss Limit (Circuit Breaker)
# ============================================================================

class DailyLossLimit:
    """
    Enforces daily loss limit to prevent account spirals.
    
    Mechanism:
    - Track starting balance each day
    - Calculate cumulative loss percentage
    - Halt all trading if loss exceeds threshold
    
    Default: Halt if down 15% for the day
    """
    
    def __init__(self, max_daily_loss_pct: float = 0.15):
        self.logger = logging.getLogger(__name__)
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_start_balance: Optional[float] = None
        self.daily_start_time: Optional[datetime] = None
        self.trading_enabled = True
    
    def reset_daily_limits(self, starting_balance: float):
        """
        Reset for new trading day (call at market open).
        
        Args:
            starting_balance: Account balance at start of day
        """
        self.daily_start_balance = starting_balance
        self.daily_start_time = datetime.now()
        self.trading_enabled = True
        
        self.logger.info(
            f"Daily limits reset: Starting balance ${starting_balance:.2f}, "
            f"Max loss: ${starting_balance * self.max_daily_loss_pct:.2f} "
            f"({self.max_daily_loss_pct:.1%})"
        )
    
    async def check_daily_loss_limit(
        self,
        current_balance: float
    ) -> Dict[str, Any]:
        """
        Check if daily loss exceeds limit.
        
        Returns:
            {
                'exceeded': bool,
                'loss_dollars': float,
                'loss_pct': float,
                'max_loss_dollars': float,
                'max_loss_pct': float,
                'trading_enabled': bool
            }
        """
        if not self.daily_start_balance:
            return {
                'exceeded': False,
                'trading_enabled': True,
                'message': 'Daily limits not initialized'
            }
        
        # Calculate loss
        loss_dollars = self.daily_start_balance - current_balance
        loss_pct = loss_dollars / self.daily_start_balance
        max_loss_dollars = self.daily_start_balance * self.max_daily_loss_pct
        
        # Check if exceeded
        exceeded = loss_pct >= self.max_daily_loss_pct
        
        if exceeded and self.trading_enabled:
            self.logger.critical(
                f"🔴 DAILY LOSS LIMIT EXCEEDED\n"
                f"   Current loss: ${loss_dollars:.2f} ({loss_pct:.1%})\n"
                f"   Max allowed: ${max_loss_dollars:.2f} ({self.max_daily_loss_pct:.1%})\n"
                f"   TRADING HALTED"
            )
            self.trading_enabled = False
        
        return {
            'exceeded': exceeded,
            'loss_dollars': loss_dollars,
            'loss_pct': loss_pct,
            'max_loss_dollars': max_loss_dollars,
            'max_loss_pct': self.max_daily_loss_pct,
            'trading_enabled': self.trading_enabled
        }
    
    def can_trade(self) -> bool:
        """Check if trading is enabled."""
        return self.trading_enabled
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'trading_enabled': self.trading_enabled,
            'daily_start_balance': self.daily_start_balance,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'daily_start_time': self.daily_start_time
        }


# ============================================================================
# CRITICAL RISK #8: Slippage Detection & Rejection
# ============================================================================

class SlippageMonitor:
    """
    Monitor and guard against execution slippage.
    
    Measures difference between requested price and actual fill price.
    Rejects fills that exceed maximum slippage tolerance.
    
    Default: Reject if slippage > 2.5%
    """
    
    def __init__(self, max_slippage_pct: float = 0.025):
        self.logger = logging.getLogger(__name__)
        self.max_slippage_pct = max_slippage_pct
        self.slippage_events: List[Dict[str, Any]] = []
    
    def measure_slippage(
        self,
        requested_price: float,
        actual_fill_price: float,
        side: str  # 'buy' or 'sell'
    ) -> float:
        """
        Calculate slippage percentage.
        
        For BUY: actual > requested = negative slippage (bad)
        For SELL: actual < requested = negative slippage (bad)
        
        Args:
            requested_price: Limit price submitted
            actual_fill_price: Price actually filled at
            side: 'buy' or 'sell'
        
        Returns:
            Slippage percentage (negative = bad, positive = good)
        """

        if requested_price == 0:
            return 0.0
        
        if side.lower() == 'buy':
            slippage = (requested_price - actual_fill_price) / requested_price
        else:  # sell
            slippage = (actual_fill_price - requested_price) / requested_price
        
        return slippage
    
    def should_reject_fill(
        self,
        requested_price: float,
        actual_fill_price: float,
        side: str
    ) -> bool:
        """
        Check if slippage exceeds maximum threshold.
        
        Returns: True if fill should be rejected/cancelled
        """
        slippage = self.measure_slippage(requested_price, actual_fill_price, side)
        
        # Negative slippage exceeding threshold = reject
        if slippage < -self.max_slippage_pct:
            self.logger.warning(
                f"🟠 SLIPPAGE REJECTION: {slippage:.2%} exceeds {-self.max_slippage_pct:.2%}\n"
                f"   Requested: ${requested_price:.4f} | "
                f"Actual: ${actual_fill_price:.4f}"
            )
            return True
        
        return False
    
    def log_slippage(
        self,
        market_id: str,
        requested_price: float,
        actual_fill_price: float,
        side: str,
        quantity: int
    ):
        """Log slippage event for analysis."""
        slippage = self.measure_slippage(requested_price, actual_fill_price, side)
        
        event = {
            'timestamp': datetime.now(),
            'market_id': market_id,
            'side': side,
            'quantity': quantity,
            'requested_price': requested_price,
            'actual_fill_price': actual_fill_price,
            'slippage': slippage,
            'cost_dollars': abs((actual_fill_price - requested_price) * quantity)
        }
        self.slippage_events.append(event)
    
    def get_slippage_stats(self) -> Dict[str, Any]:
        """Get summary statistics on slippage."""
        if not self.slippage_events:
            return {'trades': 0}
        
        slippages = [e['slippage'] for e in self.slippage_events]
        costs = [e['cost_dollars'] for e in self.slippage_events]
        
        return {
            'trades': len(slippages),
            'avg_slippage_pct': sum(slippages) / len(slippages) * 100,
            'worst_slippage_pct': min(slippages) * 100,  # Most negative
            'best_slippage_pct': max(slippages) * 100,   # Least negative
            'total_slippage_cost': sum(costs),
            'avg_slippage_cost': sum(costs) / len(costs) if costs else 0,
            'rejection_count': sum(1 for s in slippages if s < -self.max_slippage_pct)
        }


# ============================================================================
# CRITICAL RISK #14: Settlement Delay Tracking
# ============================================================================

class SettlementTracker:
    """
    Track settlement status of completed trades.
    
    Kalshi uses ACH settlement (1-2 business days).
    Funds from exited positions aren't available immediately.
    
    Tracks:
    - When funds will settle
    - Amount pending settlement
    - Amount available for withdrawal
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settled_positions: Dict[str, float] = {}  # position_id -> amount
        self.pending_settlements: Dict[str, datetime] = {}  # position_id -> settlement_time
    
    def track_settlement(
        self,
        position_id: str,
        exit_amount: float,
        exit_time: Optional[datetime] = None
    ):
        """
        Track when a position's funds will settle.
        
        ACH settlement typically: 1-2 business days
        
        Args:
            position_id: Unique position identifier
            exit_amount: Amount from exited position
            exit_time: When position was exited (default: now)
        """
        if exit_time is None:
            exit_time = datetime.now()
        
        settlement_time = self._add_business_days(exit_time, 2)
        
        self.settled_positions[position_id] = exit_amount
        
        # if settlement_time > datetime.now():
        #     self.pending_settlements[position_id] = settlement_time
        self.pending_settlements[position_id] = settlement_time
        
        self.logger.info(
            f"Settlement tracked: ${exit_amount:.2f} from {position_id} "
            f"Will settle: {settlement_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    @staticmethod
    def _add_business_days(date: datetime, days: int) -> datetime:
        """Add business days, skipping weekends."""
        current = date
        while days > 0:
            current += timedelta(days=1)
            # weekday(): 0=Mon, 1=Tue, ..., 4=Fri, 5=Sat, 6=Sun
            if current.weekday() < 5:  # Not a weekend
                days -= 1
        return current
    
    async def get_available_for_withdrawal(self) -> float:
        """
        Get amount available for withdrawal (already settled).
        
        Returns: Dollar amount ready to withdraw
        """
        now = datetime.now()
        available = 0

        # First, accumulate all available amounts
        to_remove = []
        for position_id, settlement_time in self.pending_settlements.items():
            if settlement_time <= now:
                if position_id in self.settled_positions:
                    available += self.settled_positions[position_id]
                to_remove.append(position_id)
        
        # Then remove from pending (after accumulation)
        for position_id in to_remove:
            del self.pending_settlements[position_id]
        
        return available
    
    async def get_pending_settlement_amount(self) -> float:
        """
        Get amount still waiting to be settled.
        
        Returns: Dollar amount locked until settlement
        """
        now = datetime.now()
        pending = 0
        
        for position_id, settlement_time in self.pending_settlements.items():
            if settlement_time > now and position_id in self.settled_positions:
                pending += self.settled_positions[position_id]
        
        return pending
    
    def get_settlement_status(self) -> Dict[str, Any]:
        """Get detailed settlement status."""
        now = datetime.now()
        pending_count = sum(
            1 for st in self.pending_settlements.values() if st > now
        )
        
        return {
            'pending_settlements': pending_count,
            'total_pending_amount': sum(
                v for k, v in self.settled_positions.items()
                if k in self.pending_settlements
                and self.pending_settlements[k] > now
            ),
            'next_settlement': min(
                self.pending_settlements.values()
            ) if self.pending_settlements else None,
            'settled_positions': len(
                [k for k in self.settled_positions.keys()
                 if k not in self.pending_settlements or
                 self.pending_settlements[k] <= now]
            )
        }


# ============================================================================
# MAIN RISK MANAGER (Orchestrates All Checks)
# ============================================================================

@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    passed: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class RiskManager:
    """
    Comprehensive risk management system for Kalshi spike bot.
    
    Orchestrates all 14 risk mitigations with 3-layer defense:
    - Layer 1: Pre-trade checks (before order submission)
    - Layer 2: During-trade monitoring (while order executes)
    - Layer 3: Post-trade management (after position opened)
    """
    
    def __init__(self, client, config, fee_calculator=None):
        """
        Initialize risk manager.
        
        Args:
            client: KalshiClient instance
            config: Configuration object with risk parameters
            fee_calculator: FeeCalculator for entry cost calculation
        """
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.config = config
        self.fee_calculator = fee_calculator
        
        # CRITICAL Risk Components (Week 1)
        self.account_monitor = AccountStatusMonitor()
        self.daily_loss_limit = DailyLossLimit(
            max_daily_loss_pct=getattr(config, 'MAX_DAILY_LOSS_PCT', 0.15)
        )
        self.slippage_monitor = SlippageMonitor(
            max_slippage_pct=getattr(config, 'MAX_SLIPPAGE_TOLERANCE', 0.025)
        )
        self.settlement_tracker = SettlementTracker()
        
        # Statistics
        self.checks_passed = 0
        self.checks_failed: Dict[str, int] = {}
    
    async def initialize_daily(self, starting_balance: float):
        """
        Initialize daily limits (call at market open).
        
        Args:
            starting_balance: Account balance at start of day
        """
        self.daily_loss_limit.reset_daily_limits(starting_balance)
        self.logger.info(
            f"🟢 Daily risk limits initialized\n"
            f"   Starting balance: ${starting_balance:.2f}\n"
            f"   Max daily loss: {self.config.MAX_DAILY_LOSS_PCT:.1%}"
        )
    
    # ========================================================================
    # LAYER 1: PRE-TRADE CHECKS (Before order submission)
    # ========================================================================
    
    async def can_trade_pre_submission(self, spike) -> RiskCheckResult:
        """
        Run all pre-trade checks before submitting order.
        
        Checks (in priority order):
        1. Account not suspended (Risk #12)
        2. Daily loss limit not exceeded (Risk #13)
        3. Other validations (placeholder for later risks)
        
        Args:
            spike: Spike detection result
        
        Returns:
            RiskCheckResult with pass/fail and details
        """
        
        # Check 1: Account Suspension
        if self.account_monitor.is_suspended():
            return RiskCheckResult(
                passed=False,
                reason='account_suspended',
                details=self.account_monitor.get_status()
            )
        
        # Check 2: Daily Loss Limit
        if not self.daily_loss_limit.can_trade():
            return RiskCheckResult(
                passed=False,
                reason='daily_loss_limit_exceeded',
                details=self.daily_loss_limit.get_status()
            )
        
        # Additional checks from config
        if spike.change_pct < getattr(self.config, 'SPIKE_THRESHOLD', 0.04):
            return RiskCheckResult(
                passed=False,
                reason='insufficient_spike',
                details={'threshold': self.config.SPIKE_THRESHOLD, 'actual': spike.change_pct}
            )
        
        # All checks passed
        self.checks_passed += 1
        return RiskCheckResult(passed=True)
    
    # ========================================================================
    # LAYER 2: DURING-TRADE MONITORING (While order executes)
    # ========================================================================
    
    async def validate_fill(
        self,
        requested_price: float,
        actual_fill_price: float,
        side: str,
        quantity: int,
        market_id: str
    ) -> RiskCheckResult:
        """
        Validate execution fill for slippage (Risk #8).
        
        Args:
            requested_price: Limit price submitted
            actual_fill_price: Price filled at
            side: 'buy' or 'sell'
            quantity: Number of contracts
            market_id: Market identifier
        
        Returns:
            RiskCheckResult with pass/fail
        """
        
        # Check slippage
        if self.slippage_monitor.should_reject_fill(
            requested_price, actual_fill_price, side
        ):
            return RiskCheckResult(
                passed=False,
                reason='slippage_exceeded',
                details={
                    'requested_price': requested_price,
                    'actual_fill_price': actual_fill_price,
                    'slippage': self.slippage_monitor.measure_slippage(
                        requested_price, actual_fill_price, side
                    )
                }
            )
        
        # Log slippage for analytics
        self.slippage_monitor.log_slippage(
            market_id, requested_price, actual_fill_price, side, quantity
        )
        
        self.checks_passed += 1
        return RiskCheckResult(passed=True)
    
    # ========================================================================
    # LAYER 3: POST-TRADE MANAGEMENT
    # ========================================================================
    
    async def track_exit(
        self,
        position_id: str,
        exit_amount: float
    ):
        """
        Track settlement of exited position (Risk #14).
        
        Args:
            position_id: Unique position identifier
            exit_amount: Proceeds from exit
        """
        self.settlement_tracker.track_settlement(position_id, exit_amount)
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def handle_api_error(self, status_code: int, error: Exception) -> bool:
        """
        Handle API error and check for suspension (Risk #12).
        
        Returns:
            True if account likely suspended
        """

        is_suspended = self.account_monitor.handle_api_error(status_code, error)
        
        if is_suspended:
            self.logger.critical(
                "🔴 ACCOUNT SUSPENSION DETECTED - TRADING HALTED"
            )
        
        return is_suspended
    
    async def check_daily_loss(self, current_balance: float) -> Dict[str, Any]:
        """
        Check daily loss limit and update status (Risk #13).
        
        Call frequently (before each trade or every few seconds).
        """
        return await self.daily_loss_limit.check_daily_loss_limit(current_balance)
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk management summary."""
        return {
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'account_status': self.account_monitor.get_status(),
            'daily_loss_status': self.daily_loss_limit.get_status(),
            'slippage_stats': self.slippage_monitor.get_slippage_stats(),
            'settlement_status': self.settlement_tracker.get_settlement_status()
        }
