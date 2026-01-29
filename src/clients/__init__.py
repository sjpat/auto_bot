# src/clients/__init__.py

from typing import Literal

# from src.clients.polymarket_client import PolymarketClient
from src.clients.kalshi_client import KalshiClient
from src.config import Config


def create_client(platform: Literal["polymarket", "kalshi"], config: Config):
    """
    Factory function to create platform-specific client

    Usage:
        client = create_client("kalshi", config)
    """
    # if platform == "polymarket":
    #     return PolymarketClient(config)
    if platform == "kalshi":
        return KalshiClient(config)
    else:
        raise ValueError(f"Unknown platform: {platform}")
