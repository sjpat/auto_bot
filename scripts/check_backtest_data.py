#!/usr/bin/env python3
"""Check what data is available for backtesting"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient


async def main():
    print("=" * 80)
    print("BACKTEST DATA AVAILABILITY CHECK")
    print("=" * 80)

    config = Config(platform="kalshi")
    client = KalshiClient(config)

    try:
        await client.authenticate()
        print("✅ Connected to Kalshi\n")

        # Check settled markets
        print("🔍 Checking SETTLED markets...")
        settled = await client.get_markets(status="settled", limit=100)
        print(f"   Found: {len(settled)} settled markets")

        if settled:
            sample = settled[0]
            print(f"   Sample: {sample.market_id}")

            # Check what attributes the market has
            if hasattr(sample, "volume_24h"):
                print(f"   24h Volume: ${sample.volume_24h / 100:.2f}")
            if hasattr(sample, "liquidity_usd"):
                print(f"   Liquidity: ${sample.liquidity_usd:.2f}")
            if hasattr(sample, "result"):
                print(f"   Result: {sample.result}")

            # Print all available attributes for debugging
            print(
                f"\n   📋 Available attributes: {[attr for attr in dir(sample) if not attr.startswith('_')][:10]}"
            )

        # Check closed markets
        print("\n🔍 Checking CLOSED markets...")
        closed = await client.get_markets(status="closed", limit=100)
        print(f"   Found: {len(closed)} closed markets")

        # Check open markets with volume
        print("\n🔍 Checking OPEN markets with activity...")
        open_markets = await client.get_markets(status="open", limit=100)

        print(f"   Total open: {len(open_markets)}")

        # Filter by different volume/liquidity attributes
        with_liquidity = []
        for m in open_markets:
            liquidity = 0
            if hasattr(m, "liquidity_usd"):
                liquidity = m.liquidity_usd
            elif hasattr(m, "volume_24h"):
                liquidity = m.volume_24h / 100

            if liquidity > 0:
                with_liquidity.append((m, liquidity))

        with_liquidity.sort(key=lambda x: x[1], reverse=True)

        high_volume = [(m, vol) for m, vol in with_liquidity if vol >= 100]

        print(f"   With any activity: {len(with_liquidity)}")
        print(f"   With $100+ volume: {len(high_volume)}")

        if high_volume:
            print(f"\n📊 Top high-volume markets:")
            for i, (market, vol) in enumerate(high_volume[:5], 1):
                print(f"   {i}. {market.market_id[:50]}")
                print(f"      Volume: ${vol:.2f}, Price: ${market.price:.4f}")

        # Test fetching history for settled markets
        print(f"\n🧪 Testing history fetch for settled markets...")

        test_markets = settled[:3] if len(settled) >= 3 else settled
        histories_found = 0

        for i, market in enumerate(test_markets, 1):
            print(f"\n   [{i}] Market: {market.market_id}")

            try:
                history = await client.get_market_history(market_id=market.market_id)

                if history:
                    print(f"      ✅ {len(history)} historical data points")

                    # Show date range
                    first_ts = history[0].get("ts", 0)
                    last_ts = history[-1].get("ts", 0)

                    if first_ts and last_ts:
                        first_date = datetime.fromtimestamp(first_ts)
                        last_date = datetime.fromtimestamp(last_ts)
                        duration = (last_date - first_date).total_seconds() / 3600

                        print(f"      First: {first_date.strftime('%Y-%m-%d %H:%M')}")
                        print(f"      Last:  {last_date.strftime('%Y-%m-%d %H:%M')}")
                        print(f"      Duration: {duration:.1f} hours")

                        histories_found += 1
                else:
                    print(f"      ⚠️  No history data returned")

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"      ❌ Error: {e}")

        print("\n" + "=" * 80)
        print("RECOMMENDATION:")
        print("=" * 80)

        if histories_found >= 3:
            print(f"✅ Found {histories_found} settled markets with history!")
            print(f"✅ Total settled markets available: {len(settled)}")
            print(f"\n👉 You can run backtesting with these markets:")
            print(f"   python scripts/run_backtest.py")
            print(f"\n   The backtest will use the {len(settled)} settled markets")
        elif len(high_volume) >= 10:
            print("✅ Many open markets with activity")
            print("   Run: python scripts/backtest_open_markets.py")
        else:
            print("⚠️  Limited historical data currently available")
            print("   Options:")
            print("   1. Try backtesting with the available settled markets")
            print("   2. Run monitor for several hours to collect more data")
            print("   3. Lower volume thresholds in backtest config")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
