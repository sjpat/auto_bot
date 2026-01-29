"""
Tests for position management.
"""

import pytest
from src.trading.position_manager import PositionManager
from src.trading.fee_calculator import FeeCalculator


class TestPositionManager:
    """Test position manager functionality."""

    def test_initialization(self, config):
        """Test position manager initialization."""
        pm = PositionManager(platform="kalshi", config=config)
        assert pm is not None
        assert pm.platform == "kalshi"

    def test_add_position(self, config, fee_calculator):
        """Test adding a position."""
        pm = PositionManager(platform="kalshi", config=config)

        pm.add_position(
            order_id="ORDER001",
            market_id="MARKET001",
            entry_price=0.65,
            quantity=100,
            side="buy",
        )

        assert len(pm.positions) == 1
        assert "ORDER001" in pm.positions
        assert pm.positions["ORDER001"]["entry_price"] == 0.65

    def test_get_active_positions(self, config, fee_calculator):
        """Test retrieving active positions."""
        pm = PositionManager(platform="kalshi", config=config)

        pm.add_position("ORDER001", "MARKET001", 0.65, 100, "buy")
        pm.add_position("ORDER002", "MARKET002", 0.70, 50, "sell")

        active = pm.get_active_positions()
        assert len(active) == 2

    def test_evaluate_position_profit_target(self, config, fee_calculator):
        """Test position evaluation - profit target met."""
        pm = PositionManager(platform="kalshi", config=config)

        # Add position at 0.60
        pm.add_position("ORDER001", "MARKET001", 0.60, 100, "buy")

        # Evaluate at 0.68 (should hit profit target)
        decision = pm.evaluate_position_for_exit("ORDER001", 0.68)

        assert decision["should_exit"] is True
        assert decision["reason"] == "profit_target_met"
        assert decision["net_pnl"] > config.TARGET_PROFIT_USD

    def test_evaluate_position_stop_loss(self, config, fee_calculator):
        """Test position evaluation - stop loss hit."""
        pm = PositionManager(platform="kalshi", config=config)

        # Add position at 0.65
        pm.add_position("ORDER001", "MARKET001", 0.65, 100, "buy")

        # Evaluate at 0.62 (should hit stop loss)
        decision = pm.evaluate_position_for_exit("ORDER001", 0.62)

        assert decision["should_exit"] is True
        assert decision["reason"] == "stop_loss_hit"

    def test_calculate_pnl(self, config, fee_calculator):
        """Test P&L calculation."""
        pm = PositionManager(platform="kalshi", config=config)

        pm.add_position("ORDER001", "MARKET001", 0.60, 100, "buy")
        position = pm.positions["ORDER001"]

        # Calculate P&L for exit at 0.68
        pnl = pm.calculate_pnl(position, 0.68)

        # Should be positive (bought at 0.60, selling at 0.68)
        assert pnl > 0

    def test_remove_position(self, config, fee_calculator):
        """Test removing a position."""
        pm = PositionManager(platform="kalshi", config=config)

        pm.add_position("ORDER001", "MARKET001", 0.65, 100, "buy")
        pm.remove_position("ORDER001")

        assert len(pm.positions) == 0
        assert "ORDER001" not in pm.positions

    def test_close_position(self, config, fee_calculator):
        """Test closing a position."""
        pm = PositionManager(platform="kalshi", config=config)

        pm.add_position("ORDER001", "MARKET001", 0.60, 100, "buy")

        # Close position
        result = pm.close_position("ORDER001", 0.68)

        assert result["success"] is True
        assert result["net_pnl"] > 0
        assert "ORDER001" not in pm.positions
