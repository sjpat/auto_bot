"""
Integration tests for complete trading flow.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.config import Config
from src.clients.kalshi_client import Market, Order
from src.trading.spike_detector import SpikeDetector
from src.trading.position_manager import PositionManager
from src.trading.risk_manager import RiskManager
from src.trading.fee_calculator import FeeCalculator
from datetime import datetime


class TestIntegration:
    """Integration tests for complete trading workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_trade_flow(self, config, sample_market, sample_order):
        """Test complete trade flow: spike detection -> order -> position -> exit."""
        
        # Setup components
        fee_calc = FeeCalculator()
        spike_detector = SpikeDetector(config)
        position_manager = PositionManager('kalshi', config, fee_calc)
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
                timestamp=datetime.now()
            )
        
        # 3. Create spike
        sample_market.last_price_cents = 6500  # 0.65 (8.3% increase)
        spikes = spike_detector.detect_spikes(markets=[sample_market],threshold=threshold)
        
        assert len(spikes) > 0
        spike = spikes[0]
        
        # 4. Risk check
        risk_check = await risk_manager.can_trade_pre_submission(spike)
        assert risk_check.passed is True
        
        # 5. Execute entry order
        order = await mock_client.create_order(
            market_id=spike.market_id,
            side='buy',
            quantity=100,
            price=spike.current_price
        )
        
        # 6. Add position
        position_manager.add_position(
            order_id=order.order_id,
            market_id=order.market_id,
            entry_price=order.avg_fill_price,
            quantity=order.filled_quantity,
            side=order.side
        )
        
        assert len(position_manager.get_active_positions()) == 1
        
        # 7. Evaluate for exit (profitable)
        exit_decision = position_manager.evaluate_position_for_exit(
            order.order_id,
            0.68  # Price moved up
        )
        
        assert exit_decision['should_exit'] is True
        assert exit_decision['reason'] == 'profit_target_met'
        
        # 8. Close position
        result = position_manager.close_position(order.order_id, 0.68)
        
        assert result['success'] is True
        assert result['net_pnl'] > 0
    
    @pytest.mark.asyncio
    async def test_risk_management_prevents_bad_trade(self, config, sample_market):
        """Test that risk management prevents trading during unsafe conditions."""
        
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
            market_id = 'TEST'
            current_price = 0.65
            change_pct = 0.05
        
        spike = MockSpike()
        
        # Risk check should fail
        risk_check = await risk_manager.can_trade_pre_submission(spike)
        assert risk_check.passed is False
        assert 'daily_loss_limit_exceeded' in risk_check.reason.lower() or \
               not risk_check.passed
    
    @pytest.mark.asyncio
    async def test_slippage_rejection(self, config):
        """Test that excessive slippage is rejected."""
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
            side='buy',
            quantity=100,
            market_id='TEST'
        )
        
        # Should reject due to excessive slippage
        assert risk_check.passed is False
