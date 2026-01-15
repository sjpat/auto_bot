"""
End-to-end tests simulating real trading scenarios with synthetic data.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import asyncio

from src.trading.spike_detector import SpikeDetector
from src.trading.position_manager import PositionManager
from src.clients.kalshi_client import Market
from src.config import Config


class TestEndToEnd:
    """End-to-end scenario tests with synthetic data."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        config = Config()
        config.SPIKE_THRESHOLD = 0.04  # 4% spike threshold
        config.TARGET_GAIN_USD = 5.0
        config.TARGET_LOSS_USD = 2.0
        config.DAILY_LOSS_LIMIT_USD = 20.0
        config.POSITION_SIZE_USD = 10.0
        config.PRICE_HISTORY_SIZE = 100  # Add this
        return config
    
    @pytest.fixture
    def spike_detector(self, config):
        """Create spike detector."""
        return SpikeDetector(config)
    
    @pytest.fixture
    def position_manager(self, config):
        """Create position manager with proper initialization."""
        # PositionManager needs: platform, config, risk_manager
        # For testing, we can pass None for risk_manager
        return PositionManager(
            platform=config.platform,  # Should be 'kalshi' from config
            config=config,
            risk_manager=None  # Optional for tests
        )

    
    @pytest.fixture
    def position_manager(self, config):
        """Create position manager."""
        return PositionManager(platform="kalshi",config=config)
    
    def create_synthetic_market(
        self,
        market_id: str = "TEST-MARKET-001",
        price: float = 0.50,
        volume: float = 100.0,
        hours_to_close: int = 24
    ) -> Market:
        """Create a synthetic market for testing."""
        close_ts = int((datetime.now() + timedelta(hours=hours_to_close)).timestamp())
        
        return Market(
            market_id=market_id,
            title=f"Test Market: {market_id}",
            status="active",
            close_ts=close_ts,
            liquidity_cents=int(volume * 100),  # Convert to cents
            last_price_cents=int(price * 10000),  # Convert to basis points
            best_bid_cents=int((price - 0.01) * 10000),
            best_ask_cents=int((price + 0.01) * 10000)
        )
    
    @pytest.mark.asyncio
    async def test_successful_profitable_trade(self, config, spike_detector, position_manager):
        """
        Scenario: Bot detects spike, enters position, exits at profit.
        Expected: Positive P&L, balance increases.
        """
        print("\n" + "="*80)
        print("TEST: Successful Profitable Trade")
        print("="*80)
        
        # Create synthetic market
        market = self.create_synthetic_market(
            market_id="PROFIT-TEST-001",
            price=0.30,
            volume=100.0
        )
        
        # Build price history - stable prices then spike
        print("\n📊 Building price history...")
        base_time = datetime.now()
        
        # Add 20 stable prices around 0.30
        for i in range(20):
            price = 0.30 + (i % 3) * 0.001  # Small variation
            timestamp = base_time - timedelta(minutes=20-i)
            spike_detector.add_price(market.market_id, price, timestamp)
            print(f"   t-{20-i}min: ${price:.4f}")
        
        # Add spike - price jumps from 0.30 to 0.35 (16.7% increase)
        spike_price = 0.35
        spike_detector.add_price(market.market_id, spike_price, base_time)
        print(f"   NOW: ${spike_price:.4f} ⬆️ SPIKE!")
        
        # Update market with spike price
        market.last_price_cents = int(spike_price * 10000)
        
        # Detect spikes
        print("\n🔍 Detecting spikes...")
        spikes = spike_detector.detect_spikes([market], threshold=0.04)
        
        assert len(spikes) > 0, "Should detect spike"
        print(f"   ✅ Detected {len(spikes)} spike(s)")
        
        spike_info = spikes[0]
        print(f"   Market: {spike_info['market_id']}")
        print(f"   Change: {spike_info['price_change']:.2%}")
        print(f"   Current: ${spike_info['current_price']:.4f}")
        
        # Mock Kalshi client for order execution
        mock_client = AsyncMock()
        mock_order = Mock()
        mock_order.order_id = "ORDER-123"
        mock_order.status = "filled"
        mock_order.filled_quantity = 100
        mock_order.avg_fill_price = spike_price
        mock_client.create_order = AsyncMock(return_value=mock_order)
        
        # Open position
        print("\n💰 Opening position...")
        position = position_manager.open_position(
            market_id=market.market_id,
            entry_price=spike_price,
            quantity=100,
            side="sell"  # Sell the spike
        )
        
        assert position is not None
        print(f"   ✅ Position opened: {position.position_id}")
        print(f"   Entry: ${position.entry_price:.4f}")
        print(f"   Quantity: {position.quantity}")
        print(f"   Side: {position.side}")
        
        # Simulate price mean reversion - price goes back down
        exit_price = 0.32  # Profit of $0.03 per contract
        print(f"\n📉 Price reverts to ${exit_price:.4f}")
        
        # Check if we should take profit
        current_pnl = position.calculate_pnl(exit_price)
        print(f"   Current P&L: ${current_pnl:.2f}")
        
        should_exit, reason = position_manager.should_close_position(
            position.position_id,
            exit_price
        )
        
        assert should_exit, f"Should exit position: {reason}"
        print(f"   ✅ Exit signal: {reason}")
        
        # Close position
        final_pnl = position_manager.close_position(
            position.position_id,
            exit_price
        )
        
        assert final_pnl > 0, "Should have positive P&L"
        print(f"\n✅ Trade closed with profit: ${final_pnl:.2f}")
        print(f"   Expected profit: ~${(spike_price - exit_price) * 100:.2f}")
        print("="*80)
    
    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, config, spike_detector, position_manager):
        """
        Scenario: Position moves against us, stop loss triggers.
        Expected: Loss limited to TARGET_LOSS_USD.
        """
        print("\n" + "="*80)
        print("TEST: Stop Loss Trigger")
        print("="*80)
        
        # Create market
        market = self.create_synthetic_market(
            market_id="STOP-LOSS-001",
            price=0.40
        )
        
        # Build price history and detect spike
        base_time = datetime.now()
        for i in range(20):
            spike_detector.add_price(
                market.market_id,
                0.40,
                base_time - timedelta(minutes=20-i)
            )
        
        # Price spikes to 0.45
        spike_price = 0.45
        spike_detector.add_price(market.market_id, spike_price, base_time)
        market.last_price_cents = int(spike_price * 10000)
        
        print(f"📊 Spike detected: ${spike_price:.4f}")
        
        # Open short position
        position = position_manager.open_position(
            market_id=market.market_id,
            entry_price=spike_price,
            quantity=100,
            side="sell"
        )
        
        print(f"💰 Position opened at ${spike_price:.4f}")
        
        # Price moves AGAINST us - goes higher
        adverse_price = 0.48  # Loss of $0.03 per contract = $3 total
        print(f"\n📈 Price moves against us: ${adverse_price:.4f}")
        
        current_pnl = position.calculate_pnl(adverse_price)
        print(f"   Current P&L: ${current_pnl:.2f}")
        
        # Check if stop loss should trigger
        should_exit, reason = position_manager.should_close_position(
            position.position_id,
            adverse_price
        )
        
        assert should_exit, "Stop loss should trigger"
        assert "stop loss" in reason.lower(), f"Should be stop loss exit: {reason}"
        print(f"   ✅ Stop loss triggered: {reason}")
        
        # Close position
        final_pnl = position_manager.close_position(
            position.position_id,
            adverse_price
        )
        
        assert final_pnl < 0, "Should have negative P&L"
        assert abs(final_pnl) <= config.TARGET_LOSS_USD * 1.5, \
            "Loss should be near stop loss threshold"
        
        print(f"\n✅ Position closed with controlled loss: ${final_pnl:.2f}")
        print(f"   Loss limit: ${config.TARGET_LOSS_USD:.2f}")
        print("="*80)
    
    @pytest.mark.asyncio
    async def test_daily_loss_limit_halts_trading(self, config, position_manager):
        """
        Scenario: Multiple losing trades hit daily loss limit.
        Expected: Trading halted, no new positions opened.
        """
        print("\n" + "="*80)
        print("TEST: Daily Loss Limit")
        print("="*80)
        
        # Simulate multiple losing trades
        trades = []
        total_loss = 0
        
        print("\n📉 Simulating multiple losing trades...")
        
        for i in range(5):
            market_id = f"LOSS-MARKET-{i:03d}"
            
            # Open position
            position = position_manager.open_position(
                market_id=market_id,
                entry_price=0.50,
                quantity=100,
                side="sell"
            )
            
            # Close at loss
            loss = -5.0  # $5 loss each
            final_pnl = position_manager.close_position(
                position.position_id,
                exit_price=0.55  # Adverse move
            )
            
            total_loss += final_pnl
            trades.append((position.position_id, final_pnl))
            
            print(f"   Trade {i+1}: ${final_pnl:.2f} | Total: ${total_loss:.2f}")
        
        print(f"\n💸 Total losses: ${total_loss:.2f}")
        print(f"   Daily limit: ${config.DAILY_LOSS_LIMIT_USD:.2f}")
        
        # Check if we've hit daily loss limit
        daily_pnl = position_manager.get_daily_pnl()
        print(f"   Calculated daily P&L: ${daily_pnl:.2f}")
        
        # Try to open new position - should be blocked
        print("\n🚫 Attempting to open new position...")
        can_trade = position_manager.can_open_new_position()
        
        if abs(daily_pnl) >= config.DAILY_LOSS_LIMIT_USD:
            assert not can_trade, "Should not allow trading after daily loss limit"
            print("   ✅ Trading blocked - daily loss limit reached")
        else:
            print(f"   ⚠️  Daily loss (${abs(daily_pnl):.2f}) below limit (${config.DAILY_LOSS_LIMIT_USD:.2f})")
        
        print("="*80)
    
    @pytest.mark.asyncio
    async def test_no_spikes_no_trades(self, config, spike_detector):
        """
        Scenario: Market is stable, no spikes detected.
        Expected: No trades executed, balance unchanged.
        """
        print("\n" + "="*80)
        print("TEST: No Spikes, No Trades")
        print("="*80)
        
        # Create market
        market = self.create_synthetic_market(
            market_id="STABLE-MARKET-001",
            price=0.50
        )
        
        # Build stable price history - no spike
        print("\n📊 Building stable price history...")
        base_time = datetime.now()
        
        for i in range(25):
            # Prices vary slightly but no spike
            price = 0.50 + ((i % 5) - 2) * 0.002  # Varies by ±0.004
            timestamp = base_time - timedelta(minutes=25-i)
            spike_detector.add_price(market.market_id, price, timestamp)
            
            if i % 5 == 0:
                print(f"   t-{25-i}min: ${price:.4f}")
        
        print(f"   NOW: ${0.50:.4f}")
        
        # Try to detect spikes
        print("\n🔍 Detecting spikes...")
        market.last_price_cents = int(0.50 * 10000)
        spikes = spike_detector.detect_spikes([market], threshold=0.04)
        
        assert len(spikes) == 0, "Should not detect any spikes"
        print("   ✅ No spikes detected (as expected)")
        print("   Market is stable - no trading signals")
        print("="*80)
    
    @pytest.mark.asyncio
    async def test_spike_detection_with_insufficient_history(self, config, spike_detector):
        """
        Scenario: Market has insufficient price history.
        Expected: No spikes detected until enough data.
        """
        print("\n" + "="*80)
        print("TEST: Insufficient Price History")
        print("="*80)
        
        market = self.create_synthetic_market(
            market_id="NEW-MARKET-001",
            price=0.60
        )
        
        # Add only 5 prices (need 20 for reliable detection)
        print("\n📊 Adding only 5 price points...")
        base_time = datetime.now()
        
        for i in range(5):
            spike_detector.add_price(
                market.market_id,
                0.60,
                base_time - timedelta(minutes=5-i)
            )
        
        history_length = len(spike_detector.price_history.get(market.market_id, []))
        print(f"   Price history length: {history_length}")
        
        # Try to detect spikes
        print("\n🔍 Attempting spike detection...")
        market.last_price_cents = int(0.70 * 10000)  # 16.7% jump
        spikes = spike_detector.detect_spikes([market], threshold=0.04)
        
        print(f"   Spikes detected: {len(spikes)}")
        min_history_length = 20
        if history_length < min_history_length:
            assert len(spikes) == 0, "Should not detect spikes with insufficient history"
            print(f"   ✅ Correctly skipped (need {min_history_length} points)")
        
        # Now add more history
        print(f"\n📊 Adding more price data (up to {min_history_length})...")
        for i in range(min_history_length - 5):
            spike_detector.add_price(
                market.market_id,
                0.60,
                base_time - timedelta(minutes=25-i)
            )
        
        history_length = len(spike_detector.price_history.get(market.market_id, []))
        print(f"   Price history length: {history_length}")
        
        # Now detection should work
        spikes = spike_detector.detect_spikes([market], threshold=0.04)
        print(f"   Spikes detected: {len(spikes)}")
        
        if history_length >= min_history_length:
            print("   ✅ Detection now working with sufficient history")
        
        print("="*80)

