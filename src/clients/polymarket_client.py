# src/clients/polymarket_client.py

from py_clob_client.client import ClobClient
from typing import List, Dict, Any
import json

class PolymarketClient:
    """Wrapper around py-clob-client for Polymarket"""
    
    def __init__(self, config):
        self.config = config
        self.client = ClobClient(
            network_id=137,  # Polygon
            host=config.CLOB_HOST
        )
        self.web3_client = Web3Client(config)
    
    async def verify_connection(self) -> bool:
        """Test API connectivity"""
        try:
            # Polymarket: list markets
            markets = self.client.get_markets()
            return len(markets) > 0
        except Exception as e:
            raise ConnectionError(f"Polymarket API unavailable: {e}")
    
    async def get_balance(self) -> float:
        """Get USDC balance on Polygon"""
        # Use Web3 to check USDC contract balance
        balance_wei = self.web3_client.get_usdc_balance(
            self.config.BOT_TRADER_ADDRESS
        )
        # Convert from wei (18 decimals) to dollars
        balance_usd = balance_wei / 1e6
        return balance_usd
    
    async def get_markets(self) -> List[Dict[str, Any]]:
        """Fetch all markets"""
        markets = self.client.get_markets()
        return markets
    
    async def get_market_prices(self, market_id: str) -> float:
        """Get current price for a market"""
        book = self.client.get_order_book(market_id)
        # Order book has bids (buy orders) and asks (sell orders)
        # Current price is best ask (lowest sell) or best bid (highest buy)
        if book['bids']:
            return book['bids']['price']
        elif book['asks']:
            return book['asks']['price']
        else:
            return 0.5  # Default
    
    async def submit_order(self, order: Dict) -> Dict:
        """Submit limit order to CLOB"""
        response = self.client.post_order(order)
        return response
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        response = self.client.delete_order(order_id)
        return response.get('status') == 'success'
    
    async def close(self):
        """Cleanup (Polymarket doesn't require special cleanup)"""
        pass
