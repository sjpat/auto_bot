"""
Historical data fetcher and cacher for Kalshi markets
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

@dataclass
class HistoricalPricePoint:
    """Single historical price point"""
    timestamp: datetime
    price: float
    yes_bid: float
    yes_ask: float
    volume: int
    liquidity: float
    market_id: str
    expiry_timestamp: Optional[datetime] = None
    
    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        if self.expiry_timestamp:
            data['expiry_timestamp'] = self.expiry_timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('expiry_timestamp'):
            data['expiry_timestamp'] = datetime.fromisoformat(data['expiry_timestamp'])
        return cls(**data)

@dataclass
class Candlestick:
    """OHLCV candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    market_id: str

class HistoricalDataFetcher:
    """Fetch and cache historical market data from Kalshi API"""
    
    def __init__(self, client, cache_dir: str = "data/backtest_cache"):
        self.client = client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
    async def fetch_market_history(
        self,
        market_id: str,
        start_ts: Optional[int] = None,
        use_cache: bool = True,
        market_expiry: Optional[datetime] = None
    ) -> List[HistoricalPricePoint]:
        """
        Fetch historical price data for a market.
        
        Args:
            market_id: Kalshi market ticker
            start_ts: Optional timestamp to start from
            use_cache: Use cached data if available
            market_expiry: Expiration time of the market
            
        Returns:
            List of historical price points
        """
        cache_file = self.cache_dir / f"{market_id}_history.json"
        
        # Check cache first
        if use_cache and cache_file.exists():
            self.logger.info(f"Loading cached history for {market_id}")
            points = self._load_from_cache(cache_file)
            # Backfill expiry if provided and missing
            if market_expiry:
                for p in points:
                    if not p.expiry_timestamp:
                        p.expiry_timestamp = market_expiry
            return points
        
        try:
            self.logger.info(f"Fetching history for {market_id}")
            
            # Kalshi API call - get_market_history endpoint
            # Returns list of historical stats snapshots
            history_data = await self.client.get_market_history(
                market_id=market_id,
                last_seen_ts=start_ts
            )
            
            # Convert to HistoricalPricePoint objects
            price_points = []
            for point in history_data:
                price_points.append(HistoricalPricePoint(
                    timestamp=datetime.fromtimestamp(point['ts']),
                    price=point.get('last_price', 0) / 100.0,  # Convert cents to dollars
                    yes_bid=point.get('yes_bid', 0) / 100.0,
                    yes_ask=point.get('yes_ask', 0) / 100.0,
                    volume=point.get('volume', 0),
                    liquidity=point.get('liquidity', 0) / 100.0,
                    market_id=market_id,
                    expiry_timestamp=market_expiry
                ))
            
            # Cache the data
            self._save_to_cache(cache_file, price_points)
            
            self.logger.info(f"Fetched {len(price_points)} historical points for {market_id}")
            return price_points
            
        except Exception as e:
            self.logger.error(f"Failed to fetch history for {market_id}: {e}")
            return []
    
    async def fetch_settled_markets(
        self,
        start_date: datetime,
        end_date: datetime,
        min_volume: float = 1000,
        category: Optional[str] = None
    ) -> List:
        """
        Fetch markets that have closed and settled within a date range.
        """
        try:
            # Fetch settled markets
            markets = await self.client.get_markets(status="settled", limit=1000)
            self.logger.info(f"Found {len(markets)} settled markets")
            
            if len(markets) < 10:
                # If not many settled, also get closed markets
                self.logger.info("Few settled markets found, also fetching closed markets...")
                closed_markets = await self.client.get_markets(status="closed", limit=1000)
                markets.extend(closed_markets)
                self.logger.info(f"Total markets (settled + closed): {len(markets)}")
            
            # Filter by volume/activity
            filtered_markets = []
            for market in markets:
                # Get volume/liquidity (try different attributes)
                volume = 0
                if hasattr(market, 'volume_24h'):
                    volume = market.volume_24h / 100  # Convert cents to dollars
                elif hasattr(market, 'liquidity_usd'):
                    volume = market.liquidity_usd
                
                # Check if meets minimum threshold
                if volume >= min_volume:
                    # Check category if specified
                    if category is None or (hasattr(market, 'category') and market.category == category):
                        filtered_markets.append(market)
            
            self.logger.info(
                f"After filtering (min_volume=${min_volume}): {len(filtered_markets)} markets"
            )
            return filtered_markets
            
        except Exception as e:
            self.logger.error(f"Failed to fetch markets: {e}")
            import traceback
            traceback.print_exc()
            return []

    
    async def fetch_candlesticks(
        self,
        market_id: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 60,
        use_cache: bool = True
    ) -> List[Candlestick]:
        """
        Fetch OHLCV candlestick data for a market.
        
        Args:
            market_id: Kalshi market ticker
            start_ts: Start timestamp (unix)
            end_ts: End timestamp (unix)
            period_interval: Candle period in minutes (1, 60, or 1440)
            use_cache: Use cached data if available
            
        Returns:
            List of candlesticks
        """
        cache_file = self.cache_dir / f"{market_id}_candles_{period_interval}m.json"
        
        if use_cache and cache_file.exists():
            self.logger.info(f"Loading cached candlesticks for {market_id}")
            return self._load_candlesticks_from_cache(cache_file)
        
        try:
            # Kalshi candlesticks endpoint
            response = await self.client.get(
                f"/markets/{market_id}/candlesticks",
                params={
                    'start_ts': start_ts,
                    'end_ts': end_ts,
                    'period_interval': period_interval
                }
            )
            
            candlesticks = []
            for candle in response.get('candlesticks', []):
                candlesticks.append(Candlestick(
                    timestamp=datetime.fromtimestamp(candle['ts']),
                    open=candle['open'] / 100.0,
                    high=candle['high'] / 100.0,
                    low=candle['low'] / 100.0,
                    close=candle['close'] / 100.0,
                    volume=candle['volume'],
                    market_id=market_id
                ))
            
            self._save_candlesticks_to_cache(cache_file, candlesticks)
            return candlesticks
            
        except Exception as e:
            self.logger.error(f"Failed to fetch candlesticks for {market_id}: {e}")
            return []
    
    def _save_to_cache(self, cache_file: Path, price_points: List[HistoricalPricePoint]):
        """Save price points to cache file"""
        try:
            data = [p.to_dict() for p in price_points]
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
    
    def _load_from_cache(self, cache_file: Path) -> List[HistoricalPricePoint]:
        """Load price points from cache file"""
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return [HistoricalPricePoint.from_dict(d) for d in data]
        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")
            return []
    
    def _save_candlesticks_to_cache(self, cache_file: Path, candlesticks: List[Candlestick]):
        """Save candlesticks to cache"""
        try:
            data = [asdict(c) for c in candlesticks]
            # Convert datetime to string
            for d in data:
                d['timestamp'] = d['timestamp'].isoformat()
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save candlesticks cache: {e}")
    
    def _load_candlesticks_from_cache(self, cache_file: Path) -> List[Candlestick]:
        """Load candlesticks from cache"""
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            for d in data:
                d['timestamp'] = datetime.fromisoformat(d['timestamp'])
            return [Candlestick(**d) for d in data]
        except Exception as e:
            self.logger.error(f"Failed to load candlesticks cache: {e}")
            return []
    
    async def build_backtest_dataset(
        self,
        start_date: datetime,
        end_date: datetime,
        min_volume: float = 1000,
        max_markets: int = 50
    ) -> Dict[str, List[HistoricalPricePoint]]:
        """
        Build a complete dataset for backtesting.
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            min_volume: Minimum volume filter
            max_markets: Maximum number of markets to include
            
        Returns:
            Dictionary mapping market_id to list of historical price points
        """
        self.logger.info(f"Building backtest dataset from {start_date.date()} to {end_date.date()}")
        
        # Fetch settled markets in date range
        markets = await self.fetch_settled_markets(
            start_date=start_date,
            end_date=end_date,
            min_volume=min_volume
        )
        
        if not markets:
            self.logger.warning("No markets found for backtest period")
            return {}
        
        # Limit number of markets
        markets = markets[:max_markets]
        self.logger.info(f"Fetching history for {len(markets)} markets")
        
        # Fetch history for each market
        dataset = {}
        for i, market in enumerate(markets, 1):
            self.logger.info(f"Fetching {i}/{len(markets)}: {market.market_id}")
            
            # Get expiry from market object
            expiry = None
            if hasattr(market, 'expiration_time') and market.expiration_time:
                if isinstance(market.expiration_time, str):
                    expiry = datetime.fromisoformat(market.expiration_time.replace('Z', '+00:00'))
                elif isinstance(market.expiration_time, datetime):
                    expiry = market.expiration_time
            
            history = await self.fetch_market_history(
                market_id=market.market_id,
                use_cache=True,
                market_expiry=expiry
            )
            
            if history:
                # Filter to date range
                filtered_history = [
                    p for p in history
                    if start_date <= p.timestamp <= end_date
                ]
                dataset[market.market_id] = filtered_history
            
            # Rate limiting - don't hammer API
            await asyncio.sleep(0.5)
        
        self.logger.info(f"Built dataset with {len(dataset)} markets")
        return dataset
