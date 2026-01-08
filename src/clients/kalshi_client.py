"""
Kalshi Client Wrapper

Based on official Kalshi starter code:
https://github.com/Kalshi/kalshi-starter-code-python/blob/main/clients.py
"""

import asyncio
import logging
import time
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import aiohttp
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


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
    """Market data structure."""
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
        return self.last_price_cents / 100.0 
    
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
        return self.is_open and self.liquidity_usd >= 200


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
        return self.avg_fill_price_cents / 100.0
    
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
        Initialize Kalshi client.
        
        Args:
            config: Configuration object with KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH, KALSHI_DEMO
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # API credentials
        self.key_id = config.KALSHI_API_KEY
        self.private_key_path = config.KALSHI_PRIVATE_KEY_PATH
        self.demo = config.KALSHI_DEMO
        
        # ✅ FIXED: Correct URLs from official code
        if self.demo:
            self.HTTP_BASE_URL = "https://demo-api.kalshi.co"  # Note: .co not .com
        else:
            self.HTTP_BASE_URL = "https://api.elections.kalshi.com"
        
        # API endpoints
        self.exchange_url = "/trade-api/v2/exchange"
        self.markets_url = "/trade-api/v2/markets"
        self.portfolio_url = "/trade-api/v2/portfolio"
        
        # Load private key
        self.private_key = self._load_private_key()
        
        # Rate limiting
        self.last_api_call = datetime.now()
        self.rate_limit_ms = 100  # 100ms between calls
        
        # Session
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.logger.info(f"KalshiClient initialized ({'DEMO' if self.demo else 'PROD'} mode)")
        self.logger.info(f"Base URL: {self.HTTP_BASE_URL}")
    
    def _load_private_key(self) -> rsa.RSAPrivateKey:
        """Load RSA private key from PEM file."""
        with open(self.private_key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        return private_key
    
    def _sign_pss_text(self, text: str) -> str:
        """
        Sign text using RSA-PSS and return base64 encoded signature.
        
        This is the official Kalshi authentication method.
        """
        message = text.encode('utf-8')
        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e
    
    def _request_headers(self, method: str, path: str) -> Dict[str, str]:
        """
        Generate authentication headers for API requests.
        
        Official Kalshi authentication format:
        - KALSHI-ACCESS-KEY: API key ID
        - KALSHI-ACCESS-SIGNATURE: PSS signature of timestamp+method+path
        - KALSHI-ACCESS-TIMESTAMP: Current timestamp in milliseconds
        """
        # Current time in milliseconds
        current_time_ms = int(time.time() * 1000)
        timestamp_str = str(current_time_ms)
        
        # Remove query params from path for signature
        path_parts = path.split('?')
        clean_path = path_parts[0]
        
        # Message to sign: timestamp + method + path
        msg_string = timestamp_str + method + clean_path
        
        # Sign with PSS
        signature = self._sign_pss_text(msg_string)
        
        # ✅ FIXED: Official Kalshi header format
        headers = {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
        }
        
        return headers
    
    async def _rate_limit(self):
        """Built-in rate limiter to prevent exceeding API rate limits."""
        now = datetime.now()
        threshold = timedelta(milliseconds=self.rate_limit_ms)
        
        if now - self.last_api_call < threshold:
            sleep_time = (threshold - (now - self.last_api_call)).total_seconds()
            await asyncio.sleep(sleep_time)
        
        self.last_api_call = datetime.now()
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with authentication.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API path (e.g., '/trade-api/v2/markets')
            params: Query parameters
            json: JSON body
        
        Returns:
            Response JSON
        """
        await self._rate_limit()
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = self.HTTP_BASE_URL + path
        headers = self._request_headers(method, path)
        
        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                # Handle errors
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited. Retrying after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self._request(method, path, params, json)
                
                if response.status == 401:
                    self.logger.critical("Authentication failed (401)")
                    raise Exception("Authentication failed - Invalid API key")
                
                if response.status == 403:
                    self.logger.critical("Account forbidden (403)")
                    raise Exception("Account forbidden - Possible suspension")
                
                if response.status not in range(200, 299):
                    error_text = await response.text()
                    self.logger.error(f"API error {response.status}: {error_text}")
                    raise Exception(f"API error {response.status}: {error_text}")
                
                return await response.json()
        
        except aiohttp.ClientError as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
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
        response = await self._request("GET", self.portfolio_url + "/balance")
        balance_cents = response.get("balance", 0)
        balance_usd = balance_cents / 100.0
        self.logger.debug(f"Account balance: ${balance_usd:.2f}")
        return balance_usd
    
    async def get_markets(
        self,
        status: str = "open",
        limit: int = 1000
    ) -> List[Market]:
        """
        Get available markets.
        
        Args:
            status: Filter by status ('open', 'closed', 'halted')
            limit: Maximum number of markets to return
        
        Returns:
            List of Market objects
        """
        params = {"status": status, "limit": limit}
        response = await self._request("GET", self.markets_url, params=params)
        
        markets = response.get("markets", [])
        market_objects = []
        
        for m in markets:
            try:
                market = Market(
                    market_id=m["id"],
                    title=m["title"],
                    status=m["status"],
                    close_ts=int(m["close_ts"]),
                    liquidity_cents=int(m.get("liquidity_cents", 0)),
                    last_price_cents=int(m.get("last_price_cents", 5000)),
                    best_bid_cents=int(m.get("best_bid_cents", 4900)),
                    best_ask_cents=int(m.get("best_ask_cents", 5100))
                )
                market_objects.append(market)
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Failed to parse market {m.get('id')}: {e}")
        
        self.logger.debug(f"Retrieved {len(market_objects)} markets")
        return market_objects
    
    async def create_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit"
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
        price_cents = int(price * 100)  # ✅ FIXED: *100 not *10000
        
        payload = {
            "ticker": market_id,
            "action": side.lower(),
            "count": quantity,
            "yes_price": price_cents if side.lower() == "buy" else None,
            "no_price": price_cents if side.lower() == "sell" else None,
            "type": order_type
        }
        
        response = await self._request("POST", self.portfolio_url + "/orders", json=payload)
        
        order = Order(
            order_id=response["order_id"],
            market_id=response["ticker"],
            side=response["action"],
            quantity=response["count"],
            price_cents=price_cents,
            status=response["status"],
            filled_quantity=response.get("filled_count", 0),
            avg_fill_price_cents=response.get("avg_fill_price_cents", 0)
        )
        
        self.logger.info(f"Order created: {order.order_id} | {side.upper()} {quantity} @ ${price:.4f}")
        return order
    
    async def verify_connection(self) -> bool:
        """Verify API connection."""
        return await self.authenticate()
    
    async def close(self):
        """Close client session."""
        if self.session:
            await self.session.close()
            self.logger.info("Session closed")
    
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
    demo: bool = False
) -> bool:
    """
    Test Kalshi connection before starting bot.
    
    Args:
        api_key_id: Kalshi API key ID
        private_key_path: Path to private key PEM file
        demo: Use demo endpoint
    
    Returns:
        True if connection successful
    """
    # Create temporary config-like object
    class TempConfig:
        KALSHI_API_KEY = api_key_id
        KALSHI_PRIVATE_KEY_PATH = private_key_path
        KALSHI_DEMO = demo
    
    async with KalshiClient(TempConfig()) as client:
        return await client.authenticate()
