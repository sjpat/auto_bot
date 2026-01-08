# tests/test_risk_manager_critical.py

"""
Unit tests for CRITICAL risk management components.

Tests:
- Risk #12: Account Suspension Detection
- Risk #13: Daily Loss Limit
- Risk #8: Slippage Detection
- Risk #14: Settlement Tracking

Run: pytest tests/test_risk_manager_critical.py -v
"""

import pytest
from datetime import datetime, timedelta
from src.trading.risk_manager import (
    AccountStatusMonitor,
    DailyLossLimit,
    SlippageMonitor,
    SettlementTracker,
    RiskManager,
    RiskCheckResult
)


# ============================================================================
# RISK #12: Account Suspension Detection
# ============================================================================

class TestAccountStatusMonitor:
    """Test account suspension detection."""
    
    def test_401_triggers_suspension(self):
        """Test that 401 Unauthorized immediately triggers suspension."""
        monitor = AccountStatusMonitor()
        assert not monitor.is_suspended()
        
        # Handle 401 error
        result = monitor.handle_api_error(401, Exception("Unauthorized"))
        
        assert result is True
        assert monitor.is_suspended() is True
    
    def test_403_triggers_suspension(self):
        """Test that 403 Forbidden immediately triggers suspension."""
        monitor = AccountStatusMonitor()
        
        result = monitor.handle_api_error(403, Exception("Forbidden"))
        
        assert result is True
        assert monitor.is_suspended() is True
    
    def test_multiple_errors_trigger_suspension(self):
        """Test that 5+ errors without 401/403 trigger suspension."""
        monitor = AccountStatusMonitor()
        
        # Simulate 5 API errors
        for i in range(5):
            result = monitor.handle_api_error(500, Exception(f"Error {i}"))
            if i < 4:
                assert result is False
            else:
                assert result is True  # 5th error triggers
        
        assert monitor.is_suspended() is True
    
    def test_error_count_resets_after_window(self):
        """Test that error count resets after recovery window."""
        monitor = AccountStatusMonitor()
        monitor.error_recovery_window_seconds = 1  # 1 second for testing
        
        # Generate error
        monitor.handle_api_error(500, Exception("Error"))
        assert monitor.api_error_count == 1
        
        # Fast forward time
        monitor.last_error_timestamp = datetime.now() - timedelta(seconds=2)
        monitor.reset_error_count()
        
        assert monitor.api_error_count == 0
    
    def test_get_status(self):
        """Test status reporting."""
        monitor = AccountStatusMonitor()
        monitor.handle_api_error(401, Exception("Unauthorized"))
        
        status = monitor.get_status()
        
        assert status['suspended'] is True
        assert status['api_errors'] == 1
        assert status['last_error'] is not None


# ============================================================================
# RISK #13: Daily Loss Limit
# ============================================================================

class TestDailyLossLimit:
    """Test daily loss limit enforcement."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test daily limit initialization."""
        limit = DailyLossLimit(max_daily_loss_pct=0.15)
        
        limit.reset_daily_limits(starting_balance=1000.0)
        
        assert limit.daily_start_balance == 1000.0
        assert limit.trading_enabled is True
    
    @pytest.mark.asyncio
    async def test_no_loss_allows_trading(self):
        """Test that no loss allows trading."""
        limit = DailyLossLimit(max_daily_loss_pct=0.15)
        limit.reset_daily_limits(starting_balance=1000.0)
        
        result = await limit.check_daily_loss_limit(current_balance=1000.0)
        
        assert result['exceeded'] is False
        assert result['loss_dollars'] == 0
        assert result['trading_enabled'] is True
    
    @pytest.mark.asyncio
    async def test_small_loss_allows_trading(self):
        """Test that loss under threshold allows trading."""
        limit = DailyLossLimit(max_daily_loss_pct=0.15)
        limit.reset_daily_limits(starting_balance=1000.0)
        
        # 10% loss (under 15% limit)
        result = await limit.check_daily_loss_limit(current_balance=900.0)
        
        assert result['exceeded'] is False
        assert result['loss_pct'] == 0.1
        assert result['trading_enabled'] is True
    
    @pytest.mark.asyncio
    async def test_threshold_loss_halts_trading(self):
        """Test that loss at threshold halts trading."""
        limit = DailyLossLimit(max_daily_loss_pct=0.15)
        limit.reset_daily_limits(starting_balance=1000.0)
        
        # Exactly 15% loss
        result = await limit.check_daily_loss_limit(current_balance=850.0)
        
        assert result['exceeded'] is True
        assert abs(result['loss_pct'] - 0.15) < 0.001
        assert result['trading_enabled'] is False
    
    @pytest.mark.asyncio
    async def test_excessive_loss_halts_trading(self):
        """Test that excessive loss halts trading."""
        limit = DailyLossLimit(max_daily_loss_pct=0.15)
        limit.reset_daily_limits(starting_balance=1000.0)
        
        # 30% loss (way over 15% limit)
        result = await limit.check_daily_loss_limit(current_balance=700.0)
        
        assert result['exceeded'] is True
        assert result['loss_pct'] == 0.3
        assert result['trading_enabled'] is False
    
    def test_can_trade_reflects_enabled_status(self):
        """Test that can_trade() reflects enabled status."""
        limit = DailyLossLimit()
        
        assert limit.can_trade() is True
        
        limit.trading_enabled = False
        assert limit.can_trade() is False


# ============================================================================
# RISK #8: Slippage Detection
# ============================================================================

class TestSlippageMonitor:
    """Test slippage detection and rejection."""
    
    def test_no_slippage_buy(self):
        """Test that fill at exact price has no slippage."""
        monitor = SlippageMonitor(max_slippage_pct=0.025)
        
        slippage = monitor.measure_slippage(
            requested_price=0.65,
            actual_fill_price=0.65,
            side='buy'
        )
        
        assert slippage == 0
    
    def test_positive_slippage_buy(self):
        """Test positive slippage (good for buyer)."""
        monitor = SlippageMonitor()
        
        # Requested $0.65, filled at $0.64 (good!)
        slippage = monitor.measure_slippage(
            requested_price=0.65,
            actual_fill_price=0.64,
            side='buy'
        )
        
        assert slippage > 0
        assert abs(slippage - (0.0154)) < 0.001
    
    def test_negative_slippage_buy(self):
        """Test negative slippage (bad for buyer)."""
        monitor = SlippageMonitor()
        
        # Requested $0.65, filled at $0.67 (bad!)
        slippage = monitor.measure_slippage(
            requested_price=0.65,
            actual_fill_price=0.67,
            side='buy'
        )
        
        assert slippage < 0
        assert abs(slippage - (-0.0308)) < 0.001
    
    def test_slippage_symmetry_sell(self):
        """Test slippage calculation for sells."""
        monitor = SlippageMonitor()
        
        # Sell: requested $0.70, filled at $0.68 (bad!)
        slippage = monitor.measure_slippage(
            requested_price=0.70,
            actual_fill_price=0.68,
            side='sell'
        )
        
        assert slippage < 0
        assert abs(slippage - (-0.0286)) < 0.001
    
    def test_rejection_threshold(self):
        """Test that fills exceeding threshold are rejected."""
        monitor = SlippageMonitor(max_slippage_pct=0.025)
        
        # 3% negative slippage (exceeds 2.5% threshold)
        should_reject = monitor.should_reject_fill(
            requested_price=0.65,
            actual_fill_price=0.67,  # +3% slippage
            side='buy'
        )
        
        assert should_reject is True
    
    def test_acceptance_within_threshold(self):
        """Test that fills within threshold are accepted."""
        monitor = SlippageMonitor(max_slippage_pct=0.025)
        
        # 1% negative slippage (within 2.5% threshold)
        should_reject = monitor.should_reject_fill(
            requested_price=0.65,
            actual_fill_price=0.6565,  # +1% slippage
            side='buy'
        )
        
        assert should_reject is False
    
    def test_slippage_logging(self):
        """Test that slippage events are logged."""
        monitor = SlippageMonitor()
        
        monitor.log_slippage(
            market_id='market_123',
            requested_price=0.65,
            actual_fill_price=0.67,
            side='buy',
            quantity=100
        )
        
        assert len(monitor.slippage_events) == 1
        event = monitor.slippage_events[0]
        assert event['market_id'] == 'market_123'
        assert event['quantity'] == 100
    
    def test_slippage_stats(self):
        """Test slippage statistics."""
        monitor = SlippageMonitor()
        
        # Log 3 trades with different slippage
        monitor.log_slippage('m1', 0.65, 0.67, 'buy', 100)   # -3%
        monitor.log_slippage('m2', 0.65, 0.64, 'buy', 100)   # +1.5%
        monitor.log_slippage('m3', 0.65, 0.66, 'buy', 100)   # -1.5%
        
        stats = monitor.get_slippage_stats()
        
        assert stats['trades'] == 3
        assert 'avg_slippage_pct' in stats
        assert stats['total_slippage_cost'] > 0


# ============================================================================
# RISK #14: Settlement Tracking
# ============================================================================

class TestSettlementTracker:
    """Test settlement tracking."""
    
    def test_add_business_days_weekday(self):
        """Test adding business days on weekdays."""
        # Monday
        monday = datetime(2026, 1, 5, 12, 0, 0)
        
        result = SettlementTracker._add_business_days(monday, 1)
        
        # Should be Tuesday
        assert result.weekday() == 1
    
    def test_add_business_days_skip_weekend(self):
        """Test that business days skip weekends."""
        # Friday, Jan 9, 2026
        friday = datetime(2026, 1, 9, 12, 0, 0)
        
        result = SettlementTracker._add_business_days(friday, 2)
        
        # Should skip Saturday/Sunday, land on Tuesday
        assert result.weekday() == 1  # Tuesday
        assert result.day == 13
    
    def test_track_settlement(self):
        """Test settlement tracking."""
        tracker = SettlementTracker()
        
        tracker.track_settlement(
            position_id='pos_123',
            exit_amount=100.0,
            exit_time=datetime.now()
        )
        
        assert 'pos_123' in tracker.settled_positions
        assert tracker.settled_positions['pos_123'] == 100.0
    
    @pytest.mark.asyncio
    async def test_pending_settlement_amount(self):
        """Test calculation of pending settlement amount."""
        tracker = SettlementTracker()
        
        # Track settlement for future (2 days out)
        future = datetime.now() + timedelta(days=2)
        tracker.track_settlement('pos_1', 100.0, future)
        tracker.track_settlement('pos_2', 50.0, future)
        
        pending = await tracker.get_pending_settlement_amount()
        
        assert pending == 150.0
    
    @pytest.mark.asyncio
    async def test_available_withdrawal_amount(self):
        """Test calculation of available withdrawal amount."""
        tracker = SettlementTracker()
        
        # Track settled position (already past settlement time)
        past = datetime.now() - timedelta(days=5)
        tracker.track_settlement('pos_settled', 200.0, past)
        
        # Also track pending position
        future = datetime.now() + timedelta(days=2)
        tracker.track_settlement('pos_pending', 100.0, future)
        
        available = await tracker.get_available_for_withdrawal()
        
        assert available == 200.0
    
    def test_settlement_status(self):
        """Test settlement status reporting."""
        tracker = SettlementTracker()
        
        future = datetime.now() + timedelta(days=2)
        tracker.track_settlement('pos_1', 100.0, future)
        tracker.track_settlement('pos_2', 50.0, future)
        
        status = tracker.get_settlement_status()
        
        assert status['pending_settlements'] == 2
        assert status['total_pending_amount'] == 150.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestRiskCheckResult:
    """Test RiskCheckResult dataclass."""
    
    def test_passed_result(self):
        """Test creating a passed check result."""
        result = RiskCheckResult(passed=True)
        
        assert result.passed is True
        assert result.reason is None
    
    def test_failed_result(self):
        """Test creating a failed check result."""
        result = RiskCheckResult(
            passed=False,
            reason='test_failure',
            details={'key': 'value'}
        )
        
        assert result.passed is False
        assert result.reason == 'test_failure'
        assert result.details['key'] == 'value'


# ============================================================================
# Fixtures for Common Test Data
# ============================================================================

@pytest.fixture
def account_monitor():
    """Provide AccountStatusMonitor for tests."""
    return AccountStatusMonitor()


@pytest.fixture
def daily_loss_limit():
    """Provide DailyLossLimit for tests."""
    return DailyLossLimit(max_daily_loss_pct=0.15)


@pytest.fixture
def slippage_monitor():
    """Provide SlippageMonitor for tests."""
    return SlippageMonitor(max_slippage_pct=0.025)


@pytest.fixture
def settlement_tracker():
    """Provide SettlementTracker for tests."""
    return SettlementTracker()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
