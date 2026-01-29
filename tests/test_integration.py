"""
Integration tests for complete trading flow.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.config import Config
from src.clients.kalshi_client import Market, Order
from src.trading.spike_detector import SpikeDetector
from src.trading.position_manager import PositionManager
from src.trading.risk_manager import RiskManager
from src.trading.fee_calculator import FeeCalculator
from datetime import datetime
from src.strategies.strategy_manager import StrategyManager


class TestIntegration:
    """Integration tests for complete trading workflows."""

    def test_complete_trade_flow(self, config, sample_market, sample_order):
        """Test complete trade flow: spike detection -> order -> position -> exit."""

        async def _test():
            # Setup components
            fee_calc = FeeCalculator()
            spike_detector = SpikeDetector(config)
            position_manager = PositionManager("kalshi", config)
            threshold = config.SPIKE_THRESHOLD

            mock_client = Mock()
            mock_client.get_balance = AsyncMock(return_value=1000.0)
            mock_client.create_order = AsyncMock(return_value=sample_order)

            risk_manager = RiskManager(mock_client, config, fee_calc)

            # 1. Initialize risk manager
            await risk_manager.initialize_daily(1000.0)

            # 2. Build price history
            for i in range(25):
                spike_detector.add_price(
                    market_id=sample_market.market_id,
                    price=0.60,
                    timestamp=datetime.now(),
                )

            # 3. Create spike
            sample_market.last_price_cents = 6500  # 0.65 (8.3% increase)
            spikes = spike_detector.detect_spikes(
                markets=[sample_market], threshold=threshold
            )

            assert len(spikes) > 0
            spike = spikes[0]

            # 4. Risk check

            risk_check = await risk_manager.can_trade_pre_submission(spike)
            assert risk_check.passed is True

            # 5. Execute entry order
            order = await mock_client.create_order(
                market_id=spike.market_id,
                side="buy",
                quantity=100,
                price=spike.current_price,
            )

            # 6. Add position
            position_manager.add_position(
                order_id=order.order_id,
                market_id=order.market_id,
                entry_price=order.avg_fill_price,
                quantity=order.filled_quantity,
                side=order.side,
            )

            assert len(position_manager.get_active_positions()) == 1

            # 7. Evaluate for exit (profitable)
            exit_decision = position_manager.evaluate_position_for_exit(
                order.order_id, 0.71  # Price moved up
            )

            print(
                f"DEBUG: entry_price={order.avg_fill_price}, current_price=0.68, quantity={order.filled_quantity}"
            )
            print(
                f"DEBUG: config.TARGET_PROFIT_USD={getattr(config, 'TARGET_PROFIT_USD', 'NOT SET')}"
            )
            print(f"DEBUG: exit_decision={exit_decision}")

            assert exit_decision["should_exit"] is True
            assert exit_decision["reason"] == "profit_target_met"

            # 8. Close position
            result = position_manager.close_position(order.order_id, 0.72)

            assert result["success"] is True
            assert result["net_pnl"] > 0

        asyncio.run(_test())

    def test_risk_management_prevents_bad_trade(self, config, sample_market):
        """Test that risk management prevents trading during unsafe conditions."""

        async def _test():
            mock_client = Mock()
            mock_client.get_balance = AsyncMock(return_value=1000.0)

            fee_calc = FeeCalculator()
            risk_manager = RiskManager(mock_client, config, fee_calc)

            # Initialize with starting balance
            await risk_manager.initialize_daily(1000.0)

            # Simulate large loss
            await risk_manager.check_daily_loss(850.0)  # 15% loss

            # Create a spike
            class MockSpike:
                market_id = "TEST"
                current_price = 0.65
                change_pct = 0.05

            spike = MockSpike()

            # Risk check should fail
            risk_check = await risk_manager.can_trade_pre_submission(spike)
            assert risk_check.passed is False
            assert (
                "daily_loss_limit_exceeded" in risk_check.reason.lower()
                or not risk_check.passed
            )

        asyncio.run(_test())

    def test_slippage_rejection(self, config):
        """Test that excessive slippage is rejected."""

        async def _test():
            mock_client = Mock()
            mock_client.get_balance = AsyncMock(return_value=1000.0)

            fee_calc = FeeCalculator()
            risk_manager = RiskManager(mock_client, config, fee_calc)

            await risk_manager.initialize_daily(1000.0)

            # Test slippage validation
            requested_price = 0.65
            actual_price = 0.68  # 4.6% slippage (above 2.5% threshold)

            risk_check = await risk_manager.validate_fill(
                requested_price=requested_price,
                actual_fill_price=actual_price,
                side="buy",
                quantity=100,
                market_id="TEST",
            )

            # Should reject due to excessive slippage
            assert risk_check.passed is False

        asyncio.run(_test())

    def test_momentum_strategy_integration(self, config, sample_market):
        """Test that momentum strategy is correctly integrated and generating signals."""

        async def _test():
            # Enable momentum strategy in config
            config.ENABLE_MOMENTUM_STRATEGY = True
            config.MOMENTUM_WINDOW = 3
            config.MOMENTUM_THRESHOLD = 0.05
            config.MIN_CONFIDENCE_MOMENTUM = 0.6

            # Initialize Strategy Manager
            strategy_manager = StrategyManager(config)

            # Verify momentum strategy is loaded
            strategy_names = [name for name, _ in strategy_manager.strategies]
            assert "momentum" in strategy_names

            # Simulate price run (Momentum)
            # 0.50 -> 0.51 -> 0.52 -> 0.56 (12% move over 3 steps)
            prices = [0.50, 0.51, 0.52, 0.56]

            for price in prices:
                sample_market.last_price_cents = int(price * 10000)
                strategy_manager.on_market_update(sample_market)

            # Generate signals
            signals = strategy_manager.generate_entry_signals([sample_market])

            # Should detect momentum signal
            assert len(signals) > 0
            signal = signals[0]

            assert signal.market_id == sample_market.market_id
            assert signal.signal_type == "buy"
            assert signal.metadata["strategy"] == "momentum"
            assert signal.metadata["roc"] > 0.05

            print(f"\n✅ Momentum Integration Test Passed")
            print(f"   Signal: {signal.signal_type} on {signal.market_id}")
            print(f"   ROC: {signal.metadata['roc']:.2%}")

        asyncio.run(_test())
