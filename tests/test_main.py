"""
Unit tests for the main TradingBot class.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from main import TradingBot
from src.strategies.base_strategy import Signal, SignalType

class TestTradingBot:
    """Unit tests for the main TradingBot class."""

    @pytest.fixture
    def mock_config(self):
        with patch('main.Config') as MockConfig:
            config = MockConfig.return_value
            config.LOG_FILE = "test.log"
            config.LOG_LEVEL = "INFO"
            config.PAPER_TRADING = True
            config.PAPER_STARTING_BALANCE = 10000.0
            config.PAPER_SIMULATE_SLIPPAGE = False
            config.PAPER_MAX_SLIPPAGE_PCT = 0.01
            config.PAPER_SAVE_HISTORY = False
            config.PAPER_HISTORY_FILE = "test_paper.json"
            
            config.MIN_ACCOUNT_BALANCE = 100.0
            config.MIN_LIQUIDITY_USD = 500.0
            config.MAX_SPREAD_PCT = 0.05
            config.TRADE_UNIT = 10
            config.PRICE_UPDATE_INTERVAL = 0.1
            config.POSITION_CHECK_INTERVAL = 0.1
            config.MAX_SLIPPAGE_TOLERANCE = 0.01
            yield config

    @pytest.fixture
    def bot(self, mock_config):
        with patch('main.setup_logger'), \
             patch('main.KalshiClient'), \
             patch('main.StrategyManager'), \
             patch('main.OrderExecutor'), \
             patch('main.PositionManager'), \
             patch('main.RiskManager'), \
             patch('main.FeeCalculator'), \
             patch('main.MarketFilter'), \
             patch('main.NotificationManager'):
            
            bot = TradingBot(platform="kalshi")
            
            # Mock the client instance created inside __init__
            bot.client = Mock()
            bot.client.get_balance = AsyncMock(return_value=1000.0)
            bot.client.verify_connection = AsyncMock()
            bot.client.get_markets = AsyncMock(return_value=[])
            
            # Mock risk manager
            bot.risk_manager.initialize_daily = AsyncMock()
            bot.risk_manager.can_trade_pre_submission = AsyncMock()
            
            # Mock order executor
            bot.order_executor.submit_order = AsyncMock()
            
            # Mock notification manager methods to be awaitable
            bot.notification_manager.send_message = AsyncMock()
            bot.notification_manager.send_trade_alert = AsyncMock()
            bot.notification_manager.send_exit_alert = AsyncMock()
            bot.notification_manager.send_error = AsyncMock()
            
            return bot

    def test_initialization(self, bot):
        """Test that bot initializes components correctly."""
        assert bot.platform == "kalshi"
        assert bot.client is not None
        assert bot.strategy_manager is not None
        assert bot.risk_manager is not None

    def test_initialize_sequence(self, bot):
        """Test the async initialization sequence."""
        async def _test():
            await bot.initialize()
            
            bot.client.verify_connection.assert_called_once()
            bot.client.get_balance.assert_called_once()
            bot.risk_manager.initialize_daily.assert_called_once_with(1000.0)
            assert bot.running is True
        asyncio.run(_test())

    def test_initialize_insufficient_balance(self, bot):
        """Test initialization fails with low balance."""
        async def _test():
            bot.client.get_balance.return_value = 50.0  # Below 100.0 min
            
            with pytest.raises(ValueError, match="Insufficient balance"):
                await bot.initialize()
        asyncio.run(_test())

    def test_should_trade_signal_success(self, bot):
        """Test trade validation logic - Success case."""
        async def _test():
            # Setup Market
            market = Mock()
            market.liquidity_usd = 1000.0
            market.best_ask_cents = 51
            market.best_bid_cents = 49
            market.last_price_cents = 50
            market.price = 0.50
            
            # Setup Signal
            signal = Mock(spec=Signal)
            signal.market_id = "test_market"
            signal.confidence = 0.8
            signal.metadata = {'spike_magnitude': 0.05}
            
            # Mock risk check pass
            risk_result = Mock()
            risk_result.passed = True
            bot.risk_manager.can_trade_pre_submission.return_value = risk_result
            
            # Test
            result = await bot.should_trade_signal(market, signal)
            assert result is True
        asyncio.run(_test())

    def test_should_trade_signal_risk_fail(self, bot):
        """Test trade validation logic - Risk check failure."""
        async def _test():
            market = Mock()
            market.liquidity_usd = 1000.0
            
            signal = Mock(spec=Signal)
            signal.market_id = "test_market"
            signal.metadata = {'spike_magnitude': 0.05}
            
            # Mock risk check fail
            risk_result = Mock()
            risk_result.passed = False
            risk_result.reason = "too risky"
            bot.risk_manager.can_trade_pre_submission.return_value = risk_result
            
            result = await bot.should_trade_signal(market, signal)
            assert result is False
        asyncio.run(_test())

    def test_should_trade_signal_low_liquidity(self, bot):
        """Test trade validation logic - Low liquidity."""
        async def _test():
            market = Mock()
            market.liquidity_usd = 100.0  # Below 500.0 min
            
            signal = Mock(spec=Signal)
            signal.market_id = "test_market"
            signal.metadata = {'spike_magnitude': 0.05}
            
            # Risk check passes (pre-check)
            bot.risk_manager.can_trade_pre_submission.return_value = Mock(passed=True)
            
            result = await bot.should_trade_signal(market, signal)
            assert result is False
        asyncio.run(_test())

    def test_execute_signal_trade(self, bot):
        """Test trade execution flow."""
        async def _test():
            # Setup
            signal = Mock(spec=Signal)
            signal.market_id = "test_market"
            signal.signal_type = SignalType.BUY
            signal.price = 0.50
            
            market = Mock()
            
            # Mock successful order submission
            bot.order_executor.submit_order.return_value = {
                'success': True,
                'order': Mock(order_id="123")
            }
            
            # Test
            await bot.execute_signal_trade(signal, market)
            
            # Verify calls
            bot.order_executor.submit_order.assert_called_once()
            bot.position_manager.add_position.assert_called_once()
            
            # Verify arguments
            call_args = bot.order_executor.submit_order.call_args[1]
            assert call_args['market_id'] == "test_market"
            assert call_args['side'] == "buy"
            assert call_args['price'] == 0.50
        asyncio.run(_test())

    def test_volume_signal_processing(self, bot):
        """Test that volume strategy signals are processed correctly."""
        async def _test():
            # Setup Market
            market = Mock()
            market.liquidity_usd = 1000.0
            market.best_ask_cents = 51
            market.best_bid_cents = 49
            market.last_price_cents = 50
            market.price = 0.50
            
            # Setup Signal from Volume Strategy
            signal = Mock(spec=Signal)
            signal.market_id = "test_market"
            signal.signal_type = SignalType.BUY
            signal.confidence = 0.8
            signal.price = 0.50
            signal.metadata = {
                'strategy': 'volume_spike',
                'vol_ratio': 5.0,
                'spike_magnitude': 0.02
            }
            
            # Mock risk check pass
            risk_result = Mock()
            risk_result.passed = True
            bot.risk_manager.can_trade_pre_submission.return_value = risk_result
            
            # Mock successful order submission
            bot.order_executor.submit_order.return_value = {
                'success': True,
                'order': Mock(order_id="vol_123")
            }
            
            # Test should_trade_signal
            should_trade = await bot.should_trade_signal(market, signal)
            assert should_trade is True
            
            # Test execute_signal_trade
            await bot.execute_signal_trade(signal, market)
            
            # Verify order submission
            bot.order_executor.submit_order.assert_called_once()
            call_args = bot.order_executor.submit_order.call_args[1]
            assert call_args['market_id'] == "test_market"
            assert call_args['side'] == "buy"
            
            # Verify position tracking
            bot.position_manager.add_position.assert_called_once()
            
        asyncio.run(_test())
