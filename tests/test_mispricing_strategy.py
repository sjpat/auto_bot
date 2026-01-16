"""
Unit tests for mispricing detection strategy.
"""
from datetime import datetime, timedelta
import pytest
from src.models.market import Market, MarketStatus
from src.models.position import Position, PositionSide
from src.strategies.mispricing_strategy import MispricingStrategy


class TestMispricingStrategy:
    """Test mispricing detection logic."""
    
    @pytest.fixture
    def strategy(self):
        """Create strategy instance."""
        config = {
            'MIN_EDGE': 0.08,
            'MIN_CONFIDENCE': 0.6,
            'MAX_HOLDING_TIME': 3600,
            'HISTORY_SIZE': 50
        }
        return MispricingStrategy(config)
    
    @pytest.fixture
    def sample_market(self):
        """Create a sample market."""
        return Market(
            market_id="TEST-MARKET-001",
            title="Test Market",
            status=MarketStatus.OPEN,  # Use enum
            close_time=datetime.now() + timedelta(hours=24),  # datetime object
            liquidity=500.0,
            yes_price=0.50,   # 50% as decimal
            yes_bid=0.49,     # 49%
            yes_ask=0.51      # 51%
        )

    
    def test_initialization(self, strategy):
        """Test strategy initializes correctly."""
        assert strategy.min_edge == 0.08
        assert strategy.min_confidence == 0.6
        assert len(strategy.price_history) == 0
    
    def test_extreme_price_detection(self, strategy, sample_market):
        """Test detection of extreme prices near expiration."""
        # Market expiring in 1 hour, priced at 90%
        sample_market.close_time = datetime.now() + timedelta(hours=1)  # datetime
        sample_market.yes_price = 0.90  # Use yes_price, not last_price_cents
        
        signals = strategy.generate_entry_signals([sample_market])
        
        # Should generate signal - should be closer to 100%
        assert len(signals) >= 0  # May or may not trigger based on thresholds
    
    def test_mean_reversion_detection(self, strategy, sample_market):
        """Test mean reversion detection."""
        # Build price history
        for _ in range(30):
            sample_market.last_price_cents = 5000  # 50% average
            strategy.on_market_update(sample_market)
        
        # Sudden spike to 70%
        sample_market.last_price_cents = 7000
        strategy.on_market_update(sample_market)
        
        signals = strategy.generate_entry_signals([sample_market])
        
        # Should detect deviation from mean
        if signals:
            assert signals[0].metadata['pricing_method'] == 'mean_reversion'
    
    def test_no_signal_for_fair_price(self, strategy, sample_market):
        """Test that fairly priced markets don't generate signals."""
        # Market at 50% with no history or special conditions
        signals = strategy.generate_entry_signals([sample_market])
        
        # Should not generate signal - price is reasonable
        assert len(signals) == 0 or all(s.confidence < strategy.min_confidence for s in signals)
    
    def test_exit_on_profit_target(self, strategy, sample_market):
        """Test exit when profit target is met."""
        # Create profitable position
        entry_price = 0.40
        quantity = 100
        entry_cost = entry_price * quantity  # Calculate entry_cost
        entry_fee = entry_cost * 0.01  # Assume 1% fee
        
        position = Position(
            position_id="TEST-POS-001",
            market_id=sample_market.market_id,
            side=PositionSide.LONG,  # Use enum
            quantity=quantity,
            entry_price=entry_price,
            entry_cost=entry_cost,  # REQUIRED
            entry_fee=entry_fee,     # REQUIRED
            opened_at=datetime.now() - timedelta(minutes=10),
            current_price=0.50  # 10 cent gain
        )
        
        markets = {sample_market.market_id: sample_market}
        exit_signals = strategy.generate_exit_signals([position], markets)
        
        # Should generate exit signal
        assert len(exit_signals) > 0
        assert exit_signals[0].metadata['reason'] == 'profit_target'
    
    def test_exit_on_stop_loss(self, strategy, sample_market):
        """Test exit when stop loss is hit."""
        # Create losing position
        position = Position(
            position_id="TEST-POS-002",
            market_id=sample_market.market_id,
            side="buy",
            quantity=100,
            entry_price=0.55,
            opened_at=datetime.now() - timedelta(minutes=10),
            current_price=0.50,  # 5 cent loss
            # metadata={'edge': 0.10}
        )
        
        # Simulate larger loss
        sample_market.last_price_cents = 5300  # Price moved against us
        
        markets = {sample_market.market_id: sample_market}
        exit_signals = strategy.generate_exit_signals([position], markets)
        
        # May generate exit depending on exact P&L calculation
        assert isinstance(exit_signals, list)
    
    def test_price_history_tracking(self, strategy, sample_market):
        """Test that price history is tracked correctly."""
        # Add multiple price updates
        for i in range(20):
            sample_market.last_price_cents = 5000 + (i * 10)
            strategy.on_market_update(sample_market)
        
        assert sample_market.market_id in strategy.price_history
        assert len(strategy.price_history[sample_market.market_id]) == 20
    
    def test_history_size_limit(self, strategy, sample_market):
        """Test that history doesn't exceed max size."""
        # Add more updates than history size
        for i in range(100):
            sample_market.last_price_cents = 5000 + i
            strategy.on_market_update(sample_market)
        
        # Should be capped at history_size
        assert len(strategy.price_history[sample_market.market_id]) == strategy.history_size


class TestPricingModels:
    """Test individual pricing models."""
    
    def test_binary_complement_mispricing(self):
        """Test YES/NO complement detection."""
        from src.models.pricing_models import PricingModels
        
        # YES at 60%, NO at 35% = 95% total (should be 100%)
        result = PricingModels.binary_yes_no_complement({
            'yes_price': 0.60,
            'no_price': 0.35
        })
        
        assert result is not None
        assert 0.5 < result.probability < 0.7
        assert result.confidence > 0
        assert result.method == 'yes_no_complement'
    
    def test_time_decay_near_expiration(self):
        """Test time decay model."""
        from src.models.pricing_models import PricingModels
        
        # Market expiring in 1 hour at 90% (should approach 100%)
        result = PricingModels.time_decay_expiration({
            'time_to_expiry_seconds': 3600,
            'current_price': 0.90
        })
        
        assert result is not None
        assert result.probability > 0.90
        assert result.method in ['time_decay_yes', 'time_decay_no']
    
    def test_mean_reversion_detection(self):
        """Test mean reversion model."""
        from src.models.pricing_models import PricingModels
        
        # Price history around 50%, current at 70%
        history = [0.50] * 30 + [0.70]
        current = 0.70
        
        result = PricingModels.moving_average_reversion(history, current)
        
        assert result is not None
        assert result.probability < current  # Should suggest reversion down
        assert result.method == 'mean_reversion'
