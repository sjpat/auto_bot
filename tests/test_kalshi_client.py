"""
Tests for Kalshi API client.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.clients.kalshi_client import KalshiClient, Market


class TestKalshiClient:
    """Test Kalshi client functionality."""
    
    def test_client_initialization(self, config):
        """Test client can be initialized."""
        async def _test():
            client = KalshiClient(config)
            assert client is not None
            assert client.HTTP_BASE_URL == "https://api.elections.kalshi.com"
        asyncio.run(_test())
    
    def test_authentication(self, config):
        """Test authentication flow."""
        async def _test():
            client = KalshiClient(config)
            
            # Mock the request
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = {'balance': 100000}  # $1000 in cents
                
                result = await client.authenticate()
                assert result is True
        asyncio.run(_test())
    
    def test_get_balance(self, config):
        """Test balance retrieval."""
        async def _test():
            client = KalshiClient(config)
            
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = {'balance': 150000}  # $1500
                
                balance = await client.get_balance()
                assert balance == 1500.0
        asyncio.run(_test())
    
    def test_get_markets(self, config):
        """Test market data retrieval."""
        async def _test():
            client = KalshiClient(config)
            
            mock_markets = {
                'markets': [
                    {
                        'ticker': 'MARKET1',  # Changed from 'id'
                        'title': 'Test Market 1',
                        'status': 'open',
                        'close_time': '2026-01-27T01:00:00Z',  # Changed from close_ts
                        'volume': 50000,  # Changed from liquidity_cents
                        'last_price': 65,  # Changed from last_price_cents (and value from 6500 to 65)
                        'yes_bid': 64,  # Changed from best_bid_cents
                        'yes_ask': 66  # Changed from best_ask_cents
                    }
                ]
            }
            
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_markets
                
                markets = await client.get_markets(status='open', limit=10, filter_untradeable=False)
                assert len(markets) == 1
                assert markets[0].market_id == 'MARKET1'
                assert markets[0].price == 0.65  # 65 cents * 100 / 10000 = 0.65
        asyncio.run(_test())
    
    def test_price_conversion(self, sample_market):
        """Test cents to dollar conversion."""
        async def _test():
            assert sample_market.price == 0.65
            assert sample_market.liquidity_usd == 1000.0
        asyncio.run(_test())
    
    def test_create_order(self, config):
        """Test order creation."""
        async def _test():
            client = KalshiClient(config)
            
            mock_order = {
                'order_id': 'ORDER123',
                'ticker': 'MARKET1',
                'action': 'buy',
                'count': 100,
                'status': 'filled',
                'filled_count': 100,
                'avg_fill_price_cents': 6500
            }
            
            with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_order
                
                order = await client.create_order(
                    market_id='MARKET1',
                    side='buy',
                    quantity=100,
                    price=0.65
                )
                
                assert order.order_id == 'ORDER123'
                assert order.quantity == 100
                assert order.avg_fill_price == 0.65
        asyncio.run(_test())
