#!/usr/bin/env python3
"""Quick test of backtesting system"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.backtesting import HistoricalDataFetcher

async def main():
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    
    try:
        await client.authenticate()
        print("✅ Connected to Kalshi")
        
        fetcher = HistoricalDataFetcher(client)
        
        # Test: Fetch one settled market's history
        markets = await fetcher.fetch_settled_markets(
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
            min_volume=500
        )
        
        if markets:
            test_market = markets[0]
            print(f"\n📊 Testing with market: {test_market.market_id}")
            
            history = await fetcher.fetch_market_history(
                market_id=test_market.market_id,
                use_cache=False
            )
            
            print(f"✅ Fetched {len(history)} historical data points")
            
            if history:
                print(f"   First point: {history[0].timestamp} - ${history[0].price:.4f}")
                print(f"   Last point: {history[-1].timestamp} - ${history[-1].price:.4f}")
        else:
            print("❌ No settled markets found")
            
    except Exception as e:
        print(f"❌ Error during backtest: {e}")