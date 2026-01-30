"""
Kalshi Client Wrapper

Based on official Kalshi starter code:
https://github.com/Kalshi/kalshi-starter-code-python/blob/main/clients.py
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import websockets
import json

from src.utils.decorators import async_retry

try:
    from kalshi_python_async import Configuration, KalshiClient as AsyncKalshiClient
    from kalshi_python_async.models import CreateOrderRequest
    from kalshi_python_async.models.market import Market as SDKMarket
    from pydantic import ValidationError

    # Patch the SDK Market model to handle missing fields from the API
    # Some markets (like multivariate) return null for these fields, causing Pydantic to fail
    if hasattr(SDKMarket, "model_fields"):
        # Pydantic v2: Update annotations and field info to allow None
        if "category" in SDKMarket.model_fields:
            SDKMarket.__annotations__["category"] = Optional[str]
            SDKMarket.model_fields["category"].annotation = Optional[str]
            SDKMarket.model_fields["category"].default = None

        if "risk_limit_cents" in SDKMarket.model_fields:
            SDKMarket.__annotations__["risk_limit_cents"] = Optional[int]
            SDKMarket.model_fields["risk_limit_cents"].annotation = Optional[int]
            SDKMarket.model_fields["risk_limit_cents"].default = None

        SDKMarket.model_rebuild(force=True)

except ImportError:
    AsyncKalshiClient = None
    Configuration = None
    CreateOrderRequest = None
    SDKMarket = None
    ValidationError = Exception


logger = logging.getLogger(__name__)


class OrderSideEnum(str, Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    """Order type enumeration."""

    LIMIT = "limit"
    MARKET = "market"


@dataclass
class Market:
    """Market data structure with compatibility for both strategies."""

    market_id: str
    title: str
    status: str  # 'open', 'closed', 'halted'
    close_ts: int  # Unix timestamp
    liquidity_cents: int  # In cents
    last_price_cents: int  # Last traded price in cents
    best_bid_cents: int  # Best bid in cents
    best_ask_cents: int  # Best ask in cents

    @property
    def price(self) -> float:
        """Get last price as float (0.00-1.00)."""
        return self.last_price_cents / 10000.0

    @property
    def yes_price(self) -> float:
        """YES price (for compatibility with strategies)."""
        return self.price

    @property
    def no_price(self) -> float:
        """NO price (complement of YES price)."""
        return 1.0 - self.price

    @property
    def liquidity_usd(self) -> float:
        """Get liquidity in USD."""
        return self.liquidity_cents / 100.0

    @property
    def time_to_expiry_seconds(self) -> float:
        """Get seconds until market expires."""
        return self.close_ts - datetime.now().timestamp()

    @property
    def time_to_expiry_minutes(self) -> float:
        """Get minutes until market expires."""
        return self.time_to_expiry_seconds / 60

    @property
    def is_open(self) -> bool:
        """Check if market is currently open."""
        return self.status == "open"

    @property
    def is_tradeable(self) -> bool:
        """Check if market is tradeable (open + sufficient liquidity)."""
        return self.is_open and self.liquidity_usd >= 1.0

    def is_liquid(self, min_liquidity: float = 1.0) -> bool:
        """Check if market has sufficient liquidity (for strategy compatibility)."""
        return self.liquidity_usd >= min_liquidity


@dataclass
class Order:
    """Order data structure."""

    order_id: str
    market_id: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price_cents: int
    status: str  # 'open', 'filled', 'partially_filled', 'cancelled'
    filled_quantity: int = 0
    avg_fill_price_cents: int = 0
    created_at: Optional[datetime] = None

    @property
    def price(self) -> float:
        """Get price as float."""
        return self.price_cents / 100.0

    @property
    def avg_fill_price(self) -> float:
        """Get average fill price as float."""
        return self.avg_fill_price_cents / 10000.0

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == "filled"

    @property
    def is_open(self) -> bool:
        """Check if order is still open."""
        return self.status == "open"

    @property
    def unfilled_quantity(self) -> int:
        """Get unfilled quantity."""
        return self.quantity - self.filled_quantity


class KalshiClient:
    """
    Async wrapper for Kalshi REST API.

    Based on official Kalshi implementation with PSS signature authentication.
    """

    def __init__(self, config):
        """
        Initialize Kalshi client using official SDK.

        Args:
            config: Configuration object with KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH, KALSHI_DEMO
        """
        if AsyncKalshiClient is None:
            raise ImportError(
                "kalshi-python-async not installed. Please run: pip install kalshi-python-async"
            )

        self.logger = logging.getLogger(__name__)
        self.config = config

        # Setup SDK Configuration
        self.sdk_config = Configuration()
        if config.KALSHI_DEMO:
            self.sdk_config.host = "https://demo-api.kalshi.co/trade-api/v2"
            api_key = config.KALSHI_DEMO_API_KEY
            private_key_path = config.KALSHI_DEMO_PRIVATE_KEY_PATH
        else:
            self.sdk_config.host = "https://trading-api.kalshi.com/trade-api/v2"
            api_key = config.KALSHI_API_KEY
            private_key_path = config.KALSHI_PRIVATE_KEY_PATH

        self.sdk_config.api_key_id = api_key

        # Load private key
        with open(private_key_path, "r") as f:
            self.sdk_config.private_key_pem = f.read()

        # Initialize SDK Client
        self.client = AsyncKalshiClient(self.sdk_config)

        # Expose sub-clients for easier access and testing
        self.markets = self.client
        self.portfolio = self.client

        self.ws_client = None
        self.streaming = False

        self.logger.info(
            f"KalshiClient initialized with SDK ({'DEMO' if config.KALSHI_DEMO else 'PROD'})"
        )

    async def start_streaming(self, callback):
        """Connect to WebSocket and stream market data."""
        ws_host = self.sdk_config.host.replace("https://", "wss://").replace(
            "/trade-api/v2", "/trade-api/ws/v2"
        )
        self.streaming = True

        while self.streaming:
            try:
                self.logger.info(f"Connecting to WebSocket at {ws_host}")

                # Authenticate using headers, as per documentation
                ws_path = "/trade-api/ws/v2"
                auth_headers = (
                    self.client.api_client.get_authentication_params_for_path(ws_path)
                )

                async with websockets.connect(
                    ws_host, additional_headers=auth_headers
                ) as websocket:
                    self.ws_client = websocket
                    self.logger.info("WebSocket connected and authenticated.")

                    # Subscribe to ticker channel
                    await websocket.send(
                        json.dumps(
                            {
                                "id": 1,
                                "cmd": "subscribe",
                                "params": {"channels": ["ticker"]},
                            }
                        )
                    )
                    self.logger.info("Subscribed to ticker channel.")

                    async for message in websocket:
                        data = json.loads(message)
                        if "msg" in data and "market_ticker" in data["msg"]:
                            market = self._parse_ws_market(data["msg"])
                            if market:
                                await callback(market)
            except (
                websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK,
            ) as e:
                self.logger.warning(
                    f"WebSocket connection closed: {e}. Reconnecting in 5 seconds..."
                )
                self.ws_client = None
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in WebSocket streaming: {e}", exc_info=True)
                await asyncio.sleep(5)

    def _parse_ws_market(self, ws_data: Dict[str, Any]) -> Optional[Market]:
        """Parse WebSocket market data to Market dataclass."""
        try:
            market_id = ws_data.get("market_ticker")
            if not market_id:
                return None

            # Convert prices from cents to our internal format
            last_price_cents = ws_data.get("yes_last_price", 0)
            best_bid_cents = ws_data.get("yes_bid", 0)
            best_ask_cents = ws_data.get("yes_ask", 0)

            # The websocket feed doesn't contain all market info, so we can't fully populate the Market object.
            # We will create a partial market object with the most important info for the strategy manager.
            # A full market object can be fetched via REST if needed.
            return Market(
                market_id=market_id,
                title="",  # Not available in ticker feed
                status="open",  # Assume open if we're getting ticker data
                close_ts=0,  # Not available in ticker feed
                liquidity_cents=ws_data.get("volume", 0),
                last_price_cents=last_price_cents,
                best_bid_cents=best_bid_cents,
                best_ask_cents=best_ask_cents,
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse WebSocket market data: {e}")
            return None

    async def stop_streaming(self):
        """Stop WebSocket streaming."""
        self.streaming = False
        if self.ws_client:
            await self.ws_client.close()
            self.ws_client = None
        self.logger.info("WebSocket streaming stopped.")

    async def authenticate(self) -> bool:
        """
        Verify authentication by fetching account balance.

        Returns:
            True if authentication successful
        """
        try:
            balance_data = await self.get_balance()
            self.logger.info(f"✅ Authentication successful")
            return True
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False

    async def get_balance(self) -> float:
        """
        Get account balance in USD.

        Returns:
            Balance in USD
        """
        response = await self.portfolio.get_balance()
        balance_cents = response.balance
        balance_usd = balance_cents / 100.0
        self.logger.debug(f"Account balance: ${balance_usd:.2f}")
        return balance_usd

    def _parse_market(self, m: Any) -> Optional[Market]:
        """Parse SDK market model to Market dataclass."""
        try:
            # close_time handling
            if m.close_time:
                if isinstance(m.close_time, datetime):
                    close_ts = int(m.close_time.timestamp())
                else:
                    # Fallback if it's a string
                    close_dt = datetime.fromisoformat(
                        str(m.close_time).replace("Z", "+00:00")
                    )
                    close_ts = int(close_dt.timestamp())
            else:
                return None

            # Price handling
            last_price = m.last_price or 0
            yes_bid = m.yes_bid or 0
            yes_ask = m.yes_ask or 0
            volume = m.volume or 0

            yes_bid_cents = yes_bid * 100
            yes_ask_cents = yes_ask * 100

            # Better price estimation for markets that haven't traded yet
            if last_price > 0:
                last_price_cents = last_price * 100
            elif yes_bid_cents > 0 and yes_ask_cents > 0:
                # Use mid-price if no last trade but active book
                last_price_cents = (yes_bid_cents + yes_ask_cents) // 2
            else:
                last_price_cents = 5000  # Default to 50 cents

            # Validate price ranges
            if not (0 <= last_price_cents <= 10000):
                return None

            return Market(
                market_id=m.ticker,
                title=m.title,
                status=m.status,
                close_ts=close_ts,
                liquidity_cents=volume,
                last_price_cents=last_price_cents,
                best_bid_cents=yes_bid_cents,
                best_ask_cents=yes_ask_cents,
            )
        except Exception as e:
            self.logger.warning(
                f"Failed to parse market {getattr(m, 'ticker', 'Unknown')}: {e}"
            )
            return None

    def _parse_order(self, order_data: Any) -> Order:
        """Parse SDK order model to Order dataclass."""
        # Determine price in cents
        price_cents = 0
        if order_data.yes_price:
            price_cents = order_data.yes_price
        elif order_data.no_price:
            price_cents = order_data.no_price

        # Try to get fill price
        avg_fill_price_cents = 0
        if hasattr(order_data, "avg_fill_price") and order_data.avg_fill_price:
            avg_fill_price_cents = order_data.avg_fill_price

        return Order(
            order_id=order_data.order_id,
            market_id=order_data.ticker,
            side=order_data.action,
            quantity=order_data.count,
            price_cents=price_cents,
            status=order_data.status,
            filled_quantity=order_data.filled_count or 0,
            avg_fill_price_cents=avg_fill_price_cents,
            created_at=getattr(order_data, "created_time", None),
        )

    async def get_market_history(
        self, market_id: str, last_seen_ts: Optional[int] = None
    ) -> List[Dict]:
        """
        Get historical price statistics for a market.

        Args:
            market_id: Market ticker
            last_seen_ts: Optional timestamp to start from

        Returns:
            List of historical stat snapshots
        """
        try:
            response = await self.markets.get_market_history(
                market_id, last_seen_ts=last_seen_ts
            )

            # Convert SDK models to dicts
            if response.history:
                return [h.to_dict() for h in response.history]
            return []

        except Exception as e:
            self.logger.error(f"Failed to get market history for {market_id}: {e}")
            return []

    async def get_market_candlesticks(
        self, market_id: str, start_ts: int, end_ts: int, period_interval: int = 60
    ) -> Dict:
        """
        Get OHLCV candlestick data for a market.

        Args:
            market_id: Market ticker
            start_ts: Start timestamp (unix)
            end_ts: End timestamp (unix)
            period_interval: Period in minutes (1, 60, or 1440)

        Returns:
            Dict with candlesticks list
        """
        try:
            response = await self.markets.get_market_candlesticks(
                market_id,
                start_ts=start_ts,
                end_ts=end_ts,
                period_interval=period_interval,
            )

            return response.to_dict()

        except Exception as e:
            self.logger.error(f"Failed to get candlesticks for {market_id}: {e}")
            return {"candlesticks": []}

    async def get_market(self, market_id: str) -> Optional[Market]:
        """
        Get a single market by ID.

        Args:
            market_id: Market ticker

        Returns:
            Market object or None
        """
        try:
            response = await self.markets.get_market(ticker=market_id)
            return self._parse_market(response.market)
        except ValidationError as e:
            self.logger.error(f"SDK Validation error for market {market_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get market {market_id}: {e}")
            return None

    async def get_markets(
        self,
        status: str = "open",
        limit: int = 1000,
        event_ticker: Optional[str] = None,
        min_volume: int = 0,
        filter_untradeable: bool = True,
    ) -> List[Market]:
        """
        Get available markets.

        Args:
            status: Filter by status ('open', 'closed', 'halted')
            limit: Maximum number of parsed markets to return
            event_ticker: Optional filter for a specific event (e.g., 'NBA')
            min_volume: Minimum volume in cents (default 100 = $1)
            filter_untradeable: Skip markets with no trading activity (default True)

        Returns:
            List of Market objects
        """
        start_time = time.time()
        log_msg = f"Fetching markets: status={status}, limit={limit}"
        if event_ticker:
            log_msg += f", event={event_ticker}"
        self.logger.info(log_msg)

        # Fetch markets using SDK
        # Always fetch a large batch to ensure we don't miss sports markets further down the list
        fetch_limit = max(limit, 1000)
        try:
            response = await self.markets.get_markets(
                limit=fetch_limit, status=status, event_ticker=event_ticker
            )
            markets = response.markets or []
        except ValidationError as e:
            self.logger.error(
                f"SDK failed to parse market list due to validation errors: {e}"
            )
            return []

        market_objects = []
        parse_errors = []

        for m in markets:
            try:
                market = self._parse_market(m)
                if not market:
                    continue

                # Filter untradeable markets if requested
                if filter_untradeable:
                    # Skip markets with insufficient volume
                    if market.liquidity_cents < min_volume:
                        continue

                market_objects.append(market)

                # Stop if we have enough markets
                if len(market_objects) >= limit:
                    break

            except Exception as e:
                error_msg = (
                    f"Failed to parse market {getattr(m, 'ticker', 'Unknown')}: {e}"
                )
                self.logger.warning(error_msg)
                parse_errors.append(f"{getattr(m, 'ticker', 'Unknown')}: {str(e)}")
                continue

        # Log the results
        elapsed = time.time() - start_time

        self.logger.info(
            f"Retrieved {len(market_objects)} markets "
            f"(filtered from {len(markets)} raw) in {elapsed:.2f}s"
        )

        if parse_errors:
            self.logger.warning(f"Parse errors for {len(parse_errors)} markets:")
            for error in parse_errors[:10]:  # Show first 10 errors
                self.logger.warning(f"  - {error}")
            if len(parse_errors) > 10:
                self.logger.warning(f"  ... and {len(parse_errors) - 10} more")

        if filter_untradeable:
            self.logger.debug(
                f"Filtering stats: "
                f"{len([m for m in markets if (m.last_price or 0) == 0])} with no price, "
                f"{len([m for m in markets if (m.volume or 0) < min_volume])} below min_volume"
            )

        return market_objects

    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get a single order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order object or None
        """
        try:
            response = await self.portfolio.get_order(order_id)
            return self._parse_order(response.order)
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def create_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit",
    ) -> Order:
        """
        Create a limit order.

        Args:
            market_id: Market identifier
            side: 'buy' or 'sell'
            quantity: Number of contracts
            price: Limit price (0.00-1.00)
            order_type: 'limit' or 'market'

        Returns:
            Order object
        """
        price_cents = int(price * 100)

        # Create order request using SDK model
        req = CreateOrderRequest(
            ticker=market_id,
            action=side.lower(),
            side="yes",  # Default to 'yes' side for this bot's logic
            client_order_id=str(uuid.uuid4()),
            count=quantity,
            type=order_type,
            yes_price=price_cents,
        )

        response = await self.portfolio.create_order(req)
        order_data = response.order
        order = self._parse_order(order_data)

        self.logger.info(
            f"Order created: {order.order_id} | {side.upper()} {quantity} @ ${price:.4f}"
        )
        return order

    async def verify_connection(self) -> bool:
        """Verify API connection."""
        return await self.authenticate()

    async def close(self):
        """Close client session."""
        await self.stop_streaming()
        if self.client:
            # SDK client might have close method or rely on aiohttp session
            # AsyncKalshiClient usually has api_client which has close
            if hasattr(self.client, "api_client") and hasattr(
                self.client.api_client, "close"
            ):
                await self.client.api_client.close()
            elif hasattr(self.client, "close"):
                await self.client.close()
            self.logger.info("SDK Session closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Helper function for testing connection
async def verify_kalshi_connection(
    api_key_id: str,
    private_key_path: str,
    demo: bool = False,
    demo_api_key_id: Optional[str] = None,
    demo_private_key_path: Optional[str] = None,
) -> bool:
    """
    Test Kalshi connection before starting bot.

    Args:
        api_key_id: Kalshi API key ID for production
        private_key_path: Path to production private key PEM file
        demo: Use demo endpoint
        demo_api_key_id: Kalshi API key ID for demo
        demo_private_key_path: Path to demo private key PEM file

    Returns:
        True if connection successful
    """

    # Create temporary config-like object
    class TempConfig:
        KALSHI_API_KEY = api_key_id
        KALSHI_PRIVATE_KEY_PATH = private_key_path
        KALSHI_DEMO = demo
        KALSHI_DEMO_API_KEY = demo_api_key_id
        KALSHI_DEMO_PRIVATE_KEY_PATH = demo_private_key_path

    async with KalshiClient(TempConfig()) as client:
        return await client.authenticate()
