"""
Pytest fixtures for trading bot tests.
"""

import pytest
import os
from datetime import datetime
from src.config import Config
from src.clients.kalshi_client import Market, Order
from src.trading.fee_calculator import FeeCalculator
from src.trading.risk_manager import RiskManager


@pytest.fixture
def config():
    """Create test configuration."""
    # Set test environment variables
    os.environ['KALSHI_DEMO'] = 'True'
    os.environ['PAPER_TRADING'] = 'True'
    return Config(platform='kalshi')


@pytest.fixture
def fee_calculator():
    """Create fee calculator instance."""
    return FeeCalculator()


@pytest.fixture
def sample_market():
    """Create sample market for testing."""
    return Market(
        market_id='TESTMARKET-001',
        title='Test Market',
        status='open',
        close_ts=int((datetime.now().timestamp() + 86400)),  # Tomorrow
        liquidity_cents=100000,  # $1000
        last_price_cents=6500,   # $0.65
        best_bid_cents=6450,
        best_ask_cents=6550
    )


@pytest.fixture
def sample_order():
    """Create sample order for testing."""
    return Order(
        order_id='test_order_001',
        market_id='TESTMARKET-001',
        side='buy',
        quantity=100,
        price_cents=6500,
        status='filled',
        filled_quantity=100,
        avg_fill_price_cents=6500,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_spike():
    """Create sample spike for testing."""
    class Spike:
        market_id = 'TESTMARKET-001'
        current_price = 0.68
        previous_price = 0.65
        change_pct = 0.046  # 4.6% spike
        direction = 'buy'
        timestamp = datetime.now()
    
    return Spike()
