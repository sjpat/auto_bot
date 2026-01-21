"""
Unit tests for MomentumStrategy.
"""

import pytest
from unittest.mock import Mock
from src.strategies.momentum_strategy import MomentumStrategy
from src.models.market import Market
from src.strategies.base_strategy import SignalType

class TestMomentumStrategy:
    @pytest.fixture
    def config(self):
        return {
            'MOMENTUM_WINDOW': 3,
            'MOMENTUM_THRESHOLD': 0.05,
            'MIN_CONFIDENCE': 0.6,
            'MIN_LIQUIDITY_REQUIREMENT': 100.0,
            'TARGET_PROFIT_USD': 2.0,
            'TARGET_LOSS_USD': -1.0,
            'HOLDING_TIME_LIMIT': 3600
        }

    @pytest.fixture
    def strategy(self, config):
        return MomentumStrategy(config)

    def test_initialization(self, strategy):
        assert strategy.momentum_window == 3
        assert strategy.momentum_threshold == 0.05

    def test_no_signal_insufficient_history(self, strategy):
        market = Mock(spec=Market)
        market.market_id = "test_market"
        market.yes_price = 0.50
        market.is_open = True
        market.is_liquid.return_value = True

        # Add 1 price point
        strategy.on_market_update(market)
        
        signals = strategy.generate_entry_signals([market])
        assert len(signals) == 0

    def test_momentum_buy_signal(self, strategy):
        market = Mock(spec=Market)
        market.market_id = "test_market"
        market.is_open = True
        market.is_liquid.return_value = True

        # Price history: 0.50 -> 0.51 -> 0.52 -> 0.55 (Jump!)
        # Window is 3. Compare 0.55 (current) vs 0.50 (3 steps ago)
        prices = [0.50, 0.51, 0.52, 0.55]
        
        for p in prices:
            market.yes_price = p
            strategy.on_market_update(market)
        
        # ROC = (0.55 - 0.50) / 0.50 = 0.10 (10%)
        # Threshold is 0.05 (5%). Should trigger.

        signals = strategy.generate_entry_signals([market])
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.BUY
        assert signals[0].market_id == "test_market"
        assert signals[0].metadata['roc'] == pytest.approx(0.10)
        assert signals[0].metadata['strategy'] == 'momentum'

    def test_momentum_sell_signal(self, strategy):
        market = Mock(spec=Market)
        market.market_id = "test_market_down"
        market.is_open = True
        market.is_liquid.return_value = True

        # Price history: 0.50 -> 0.49 -> 0.48 -> 0.40 (Drop!)
        prices = [0.50, 0.49, 0.48, 0.40]
        
        for p in prices:
            market.yes_price = p
            strategy.on_market_update(market)
            
        # ROC = (0.40 - 0.50) / 0.50 = -0.20 (-20%)
        # Abs(ROC) > 0.05. Should trigger SELL.

        signals = strategy.generate_entry_signals([market])
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.SELL
        assert signals[0].metadata['roc'] == pytest.approx(-0.20)