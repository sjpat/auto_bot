"""
Tests for Kalshi API client.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.clients.kalshi_client import KalshiClient, Market


class TestKalshiClient:
    """Test Kalshi client functionality."""

    def test_client_initialization(self, config):
        """Test client can be initialized."""
        async def _test():
            client = KalshiClient(config)
            assert client is not None
        asyncio.run(_test())

    def test_authentication(self, config):
        """Test authentication flow."""
        async def _test():
            client = KalshiClient(config)

            client.portfolio = AsyncMock()
            client.portfolio.get_balance.return_value = Mock(balance=10000)

            result = await client.authenticate()
            assert result is True
        asyncio.run(_test())

    def test_get_balance(self, config):
        """Test balance retrieval."""
        async def _test():
            client = KalshiClient(config)

            client.portfolio = AsyncMock()
            client.portfolio.get_balance.return_value = Mock(balance=150000)

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
                        'close_time': '2026-01-27T01:00:00Z',
                        'volume': 50000,  # Changed from liquidity_cents
                        'last_price': 65,  # Changed from last_price_cents (and value from 6500 to 65)
                        'yes_bid': 64,  # Changed from best_bid_cents
                        'yes_ask': 66,  # Changed from best_ask_cents
                        'category': 'Politics',
                        'risk_limit_cents': 100000
                    }
                ]
            }

            client.markets = AsyncMock()
            client.markets.get_markets.return_value = Mock(markets=[Mock(**mock_markets['markets'][0])])

            markets = await client.get_markets(status='open', limit=10)
            assert len(markets) == 1
            assert markets[0].market_id == 'MARKET1'
            assert markets[0].price == 0.65 # verify float price conversion
        asyncio.run(_test())

    def test_get_nba_markets(self, config):
        """Test targeted retrieval of NBA markets."""
        async def _test():
            client = KalshiClient(config)
            
            mock_nba_market = {
                'ticker': 'KXNBA-26JAN26-LAL-CHI',
                'title': 'Lakers vs Bulls',
                'status': 'open',
                'close_time': '2026-01-27T03:00:00Z',
                'volume': 1000,
                'last_price': 0, # No trades yet
                'yes_bid': 52,
                'yes_ask': 54,
                'category': 'Sports',
                'risk_limit_cents': 100000
            }

            client.markets = AsyncMock()
            client.markets.get_markets.return_value = Mock(markets=[Mock(**mock_nba_market)])

            markets = await client.get_markets(event_ticker='NBA', limit=10)
            
            assert len(markets) == 1
            assert "NBA" in markets[0].market_id
            # Verify mid-price estimation ( (52+54)/2 = 53 )
            assert markets[0].last_price_cents == 5300
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

            client.portfolio = AsyncMock()

            # Mock SDK response object
            mock_resp = Mock()
            mock_resp.order = Mock(
                order_id='ORDER123',
                ticker='MARKET1',
                action='buy',
                count=100,
                status='filled',
                avg_fill_price=6500
            )
            client.portfolio.create_order.return_value = mock_resp

            order = await client.create_order(market_id='MARKET1',
                                                side='buy',
                                                quantity=100,
                                                price=0.65)

            assert order.order_id == 'ORDER123'
            assert order.quantity == 100
            assert order.avg_fill_price == 0.65
        asyncio.run(_test())
