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

        print("=" * 60)
        print("BUILDING PRICE HISTORY")
        print("=" * 60)

        # Try different filtering approaches
        print("\nAttempting to fetch markets...")

        # Try 1: With minimal filtering
        markets = await client.get_markets(
            status="open", limit=50, min_volume=0, filter_untradeable=False
        )

        if len(markets) == 0:
            print("❌ No markets found!")
            print("\nTroubleshooting steps:")
            print("1. Check if using demo vs production API")
            print("2. Verify API credentials")
            print("3. Check Kalshi website for available markets")
            return

        print(f"✅ Found {len(markets)} markets\n")

        # Build history over several checks
        print("Building price history over 5 checks...")
        for i in range(5):
            markets = await client.get_markets(
                status="open", limit=50, min_volume=0, filter_untradeable=False
            )

            added_count = 0
            for market in markets:
                spike_detector.add_price(
                    market_id=market.market_id,
                    price=market.price,
                    timestamp=datetime.now(),
                )
                added_count += 1

            print(f"  Check {i+1}: Added prices for {added_count} markets")
            await asyncio.sleep(2)

        # Check history depth
        print("\n" + "=" * 60)
        print("PRICE HISTORY DEPTH")
        print("=" * 60)

        if len(spike_detector.price_history) == 0:
            print("\n❌ No price history built!")
            print("   This means markets had no valid prices.")
        else:
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

            print(f"\n✅ Total markets tracked: {len(spike_detector.price_history)}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
