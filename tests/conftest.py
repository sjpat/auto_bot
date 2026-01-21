"""
Pytest configuration and fixtures for auto_bot tests.
"""
import pytest
from datetime import datetime
from src.config import Config
from src.clients.kalshi_client import Market, Order
from src.trading.fee_calculator import FeeCalculator


@pytest.fixture
def config():
    """Provide test configuration."""
    cfg = Config()
    # Override defaults to match test expectations
    cfg.SPIKE_THRESHOLD = 0.04
    cfg.TARGET_PROFIT_USD = 2.50
    return cfg


@pytest.fixture
def fee_calculator():
    """Provide fee calculator instance."""
    return FeeCalculator()


@pytest.fixture
def sample_market():
    """Provide a sample Market object for testing."""
    return Market(
        market_id="TEST-MARKET-001",
        title="Test Market",
        status="open",
        close_ts=int((datetime.now().timestamp() + 86400)),  # Closes in 24 hours
        liquidity_cents=100000,  # $1000
        last_price_cents=6500,   # $0.65
        best_bid_cents=6450,     # $0.6450
        best_ask_cents=6550      # $0.6550
    )


@pytest.fixture
def sample_order():
    """Provide a sample Order object for testing."""
    return Order(
        order_id="TEST-ORDER-001",
        market_id="TEST-MARKET-001",
        side="buy",
        quantity=100,
        price_cents=6500,
        status="filled",
        filled_quantity=100,
        avg_fill_price_cents=6500,
        created_at=datetime.now()
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", 
        "integration: marks tests as integration tests that make real API calls (deselect with '-m \"not integration\"')"
    )
