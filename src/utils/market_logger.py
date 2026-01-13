"""
Specialized logger for market data and trading operations.
"""
import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path


class MarketLogger:
    """Logger for market data and trading operations."""
    
    def __init__(self, log_dir: str = "logs/markets"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("market_data")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler with daily rotation
        log_file = self.log_dir / f"markets_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
    
    def log_market_fetch(
        self,
        total_markets: int,
        tradeable_markets: int,
        filter_params: Dict[str, Any],
        response_time: float
    ):
        """Log market fetch operation."""
        self.logger.info(
            f"FETCH | Total: {total_markets} | Tradeable: {tradeable_markets} | "
            f"Filters: {json.dumps(filter_params)} | Time: {response_time:.2f}s"
        )
    
    def log_markets_snapshot(self, markets: List[Any]):
        """Log snapshot of current markets."""
        if not markets:
            return
        
        market_ids = [m.market_id for m in markets]
        prices = [m.price for m in markets]
        volumes = [m.liquidity_usd for m in markets]
        
        self.logger.info(
            f"SNAPSHOT | Markets: {len(markets)} | "
            f"Price range: ${min(prices):.4f}-${max(prices):.4f} | "
            f"Total volume: ${sum(volumes):.2f}"
        )
        
        # Log individual markets at DEBUG level
        for market in markets:
            self.logger.debug(
                f"MARKET | {market.market_id} | "
                f"Price: ${market.price:.4f} | "
                f"Vol: ${market.liquidity_usd:.2f}"
            )
    
    def log_market_change(
        self,
        market_id: str,
        old_price: float,
        new_price: float,
        change_pct: float
    ):
        """Log significant market price changes."""
        direction = "UP" if new_price > old_price else "DOWN"
        self.logger.info(
            f"CHANGE | {market_id} | {direction} {abs(change_pct):.2%} | "
            f"${old_price:.4f} -> ${new_price:.4f}"
        )
    
    def log_spike_detection(
        self,
        market_id: str,
        change_pct: float,
        threshold: float,
        current_price: float,
        previous_price: float
    ):
        """Log spike detection."""
        self.logger.warning(
            f"SPIKE | {market_id} | Change: {change_pct:.2%} "
            f"(threshold: {threshold:.1%}) | "
            f"${previous_price:.4f} -> ${current_price:.4f}"
        )
