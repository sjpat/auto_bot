import unittest
from unittest.mock import Mock
from src.strategies.momentum_strategy import MomentumStrategy
from src.strategies.base_strategy import SignalType

class TestMomentumStrategy(unittest.TestCase):
    def setUp(self):
        self.config = {
            'MOMENTUM_WINDOW': 3,
            'MOMENTUM_THRESHOLD': 0.10, # 10% threshold
            'MIN_CONFIDENCE': 0.0,
            'TARGET_PROFIT_USD': 100.0,
            'TARGET_LOSS_USD': -100.0,
            'HOLDING_TIME_LIMIT': 3600,
            'MIN_LIQUIDITY_REQUIREMENT': 0,
            'MOMENTUM_REVERSAL_MULTIPLIER': 0.5 # Exit if reverses > 5%
        }
        self.strategy = MomentumStrategy(self.config)

    def _create_mock_market(self, price):
        market = Mock()
        market.market_id = "m1"
        market.yes_price = price
        market.is_open = True
        market.is_liquid.return_value = True
        return market

    def _create_mock_position(self, side="buy"):
        position = Mock()
        position.market_id = "m1"
        position.side = side
        position.is_open = True
        position.unrealized_pnl = 0.0
        position.holding_time_seconds = 0
        # Mock update_current_price to do nothing
        position.update_current_price = Mock()
        return position

    def test_trend_reversal_exit_buy(self):
        """Test that a long position exits when price trend reverses."""
        market = self._create_mock_market(0.50)
        position = self._create_mock_position("buy")
        
        # 1. Build upward trend history
        # Window=3. History needs to be populated.
        prices = [0.50, 0.55, 0.60, 0.65]
        for p in prices:
            market.yes_price = p
            self.strategy.on_market_update(market)
            
        # Current state: Price 0.65. 
        # Past price (window+1 back) would be 0.50. ROC = +30%.
        # No exit should be generated yet.
        signals = self.strategy.generate_exit_signals([position], {"m1": market})
        self.assertEqual(len(signals), 0)
        
        # 2. Reversal
        # Price drops sharply to 0.50
        market.yes_price = 0.50
        self.strategy.on_market_update(market)
        
        # History is now [0.50, 0.55, 0.60, 0.65, 0.50]
        # Window=3. Comparison is Current(0.50) vs Past(0.55) (index -4)
        # ROC = (0.50 - 0.55) / 0.55 = -0.09 (-9%)
        # Threshold is 10%. Reversal trigger is -10% * 0.5 = -5%.
        # -9% < -5%, so it should trigger exit.
        
        signals = self.strategy.generate_exit_signals([position], {"m1": market})
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].metadata['reason'], 'trend_reversal')
        self.assertEqual(signals[0].signal_type, SignalType.SELL)

    def test_minor_pullback_ignored(self):
        """Test that small pullbacks do not trigger exit."""
        market = self._create_mock_market(0.50)
        position = self._create_mock_position("buy")
        
        # Build upward trend
        prices = [0.50, 0.55, 0.60, 0.65]
        for p in prices:
            market.yes_price = p
            self.strategy.on_market_update(market)
            
        # Minor pullback to 0.64
        market.yes_price = 0.64
        self.strategy.on_market_update(market)
        
        # ROC calculation: 0.64 vs 0.55 = +16%. Still positive momentum.
        signals = self.strategy.generate_exit_signals([position], {"m1": market})
        self.assertEqual(len(signals), 0)

if __name__ == '__main__':
    unittest.main()