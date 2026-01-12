"""
Tests for order execution.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.trading.order_executor import OrderExecutor

class TestOrderExecutor:
    """Test order executor functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, config):
        """Test order executor initialization."""
        mock_client = Mock()
        executor = OrderExecutor(client=mock_client, config=config)
        
        assert executor is not None
        assert executor.client == mock_client
    
    @pytest.mark.asyncio
    async def test_submit_order_success(self, config, sample_order):
        """Test successful order submission."""
        mock_client = Mock()
        mock_client.create_order = AsyncMock(return_value={
            'order_id': 'test_order_001',
            'market_id': 'TESTMARKET-001',
            'side': 'buy',
            'quantity': 100,
            'price_cents': 6500,
            'status': 'filled',
            'filled_quantity': 100,
            'avg_fill_price_cents': 6500
        })
        
        executor = OrderExecutor(client=mock_client, config=config)
        
        order = await executor.submit_order(
            market_id='TESTMARKET-001',
            side='buy',
            size=100,
            price=0.65,
            order_type='limit'
        )
        
        assert order is not None
        assert order['order_id'] == 'test_order_001'
        assert order['order']['quantity'] == 100
    
    @pytest.mark.asyncio
    async def test_submit_order_with_retry(self, config):
        """Test order submission with retry on failure."""
        mock_client = Mock()
        # Fail first time, succeed second time
        mock_client.create_order = AsyncMock(
            side_effect=[Exception("API Error"), {
                'order_id': 'test_order_001',
                'quantity': 100
            }]
        )
        
        executor = OrderExecutor(client=mock_client, config=config)
        
        # Should retry and succeed
        with patch('asyncio.sleep', return_value=None):  # Skip sleep delays
            order = await executor.submit_order(
                market_id='TESTMARKET-001',
                side='buy',
                size=100,
                price=0.65
            )
        
        assert mock_client.create_order.call_count == 2
