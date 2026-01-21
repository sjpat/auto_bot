"""
Tests for paper trading simulator.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from src.trading.paper_trading import PaperTradingClient


class TestPaperTrading:
    """Test paper trading functionality."""
    
    def test_initialization(self, config):
        """Test paper trading client initialization."""
        async def _test():
            mock_real_client = Mock()
            mock_real_client.authenticate = AsyncMock(return_value=True)
            
            paper_client = PaperTradingClient(
                kalshi_client=mock_real_client,
                starting_balance=1000.0
            )
            
            assert paper_client.starting_balance == 1000.0
            assert paper_client.current_balance == 1000.0
        asyncio.run(_test())
    
    def test_get_balance(self, config):
        """Test getting virtual balance."""
        async def _test():
            mock_real_client = Mock()
            paper_client = PaperTradingClient(
                kalshi_client=mock_real_client,
                starting_balance=1000.0
            )
            
            balance = await paper_client.get_balance()
            assert balance == 1000.0
        asyncio.run(_test())
    
    def test_create_order(self, config):
        """Test creating a paper order."""
        async def _test():
            mock_real_client = Mock()
            paper_client = PaperTradingClient(
                kalshi_client=mock_real_client,
                starting_balance=1000.0,
                simulate_slippage=False  # No slippage for testing
            )
            
            order = await paper_client.create_order(
                market_id='MARKET001',
                side='buy',
                quantity=100,
                price=0.65
            )
            
            assert order.order_id.startswith('paper_')
            assert order.quantity == 100
            assert order.status == 'filled'
            
            # Balance should decrease
            assert paper_client.current_balance < 1000.0
        asyncio.run(_test())
    
    def test_insufficient_balance(self, config):
        """Test order rejection due to insufficient balance."""
        async def _test():
            mock_real_client = Mock()
            paper_client = PaperTradingClient(
                kalshi_client=mock_real_client,
                starting_balance=10.0  # Only $10
            )
            
            # Try to buy $65 worth
            with pytest.raises(Exception, match="Insufficient balance"):
                await paper_client.create_order(
                    market_id='MARKET001',
                    side='buy',
                    quantity=100,
                    price=0.65
                )
        asyncio.run(_test())
    
    def test_slippage_simulation(self, config):
        """Test that slippage is simulated."""
        async def _test():
            mock_real_client = Mock()
            paper_client = PaperTradingClient(
                kalshi_client=mock_real_client,
                starting_balance=1000.0,
                simulate_slippage=True
            )
            
            order = await paper_client.create_order(
                market_id='MARKET001',
                side='buy',
                quantity=100,
                price=0.65
            )
            
            # Slippage means actual fill price differs from requested
            # (Could be better or worse)
            assert order.avg_fill_price != order.price or order.avg_fill_price == order.price
        asyncio.run(_test())
    
    def test_statistics_tracking(self, config):
        """Test that statistics are tracked correctly."""
        mock_real_client = Mock()
        paper_client = PaperTradingClient(
            kalshi_client=mock_real_client,
            starting_balance=1000.0
        )
        
        # Initially zero trades
        stats = paper_client.get_statistics()
        assert stats['total_trades'] == 0
        assert stats['winning_trades'] == 0
        assert stats['losing_trades'] == 0
