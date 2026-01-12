"""
Check how much price history has been built up.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


async def main():
    config = Config()
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    try:
        await client.authenticate()
        
        # Simulate several checks to build history
        print("Building price history over 5 checks...")
        for i in range(5):
            markets = await client.get_markets(status="open", limit=10, min_volume=1)
            
            for market in markets:
                spike_detector.add_price(
                    market_id=market.market_id,
                    price=market.price,
                    timestamp=datetime.now()
                )
            
            print(f"  Check {i+1}: Added prices for {len(markets)} markets")
            await asyncio.sleep(2)
        
        # Check history depth
        print("\n" + "=" * 60)
        print("PRICE HISTORY DEPTH")
        print("=" * 60)
        
        for market_id, history in spike_detector.price_history.items():
            print(f"\nMarket: {market_id[:40]}...")
            print(f"  History points: {len(history)}")
            if len(history) >= 20:
                print(f"  Status: ✅ Ready for spike detection")
            else:
                print(f"  Status: ⏳ Need {20 - len(history)} more points")
            
            # Show price range
            if len(history) > 0:
                prices = [p[0] if isinstance(p, tuple) else p for p in history]
                print(f"  Price range: ${min(prices):.4f} - ${max(prices):.4f}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
