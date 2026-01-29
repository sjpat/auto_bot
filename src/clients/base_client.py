# src/clients/base_client.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseClient(ABC):
    """Abstract base class for market API clients"""

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Verify API connectivity"""
        pass

    @abstractmethod
    async def get_balance(self) -> float:
        """Get available balance in USD"""
        pass

    @abstractmethod
    async def get_markets(self) -> List[Dict[str, Any]]:
        """Get all available markets"""
        pass

    @abstractmethod
    async def get_market_prices(self, market_id: str) -> Dict[str, float]:
        """Get current prices for a market"""
        pass

    @abstractmethod
    async def create_order(self, order: Dict) -> Dict:
        """Create an order"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass

    @abstractmethod
    async def close(self):
        """Cleanup resources"""
        pass


# Both PolymarketClient and KalshiClient should inherit from BaseClient
