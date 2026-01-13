"""
Check how long markets last before closing.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient


async def main():
    config = Config()
    client = KalshiClient(config)
    
    try:
        await client.authenticate()
        
        markets = await client.get_markets(
            status="open",
            limit=100,
            min_volume=0,
            filter_untradeable=False
        )
        
        now = datetime.now().timestamp()
        
        print("=" * 80)
        print("MARKET LIFESPAN ANALYSIS")
        print("=" * 80)
        
        print(f"\nTotal markets: {len(markets)}")
        
        # Categorize by time until close
        buckets = {
            "< 5 min": 0,
            "5-15 min": 0,
            "15-30 min": 0,
            "30-60 min": 0,
            "1-2 hours": 0,
            "2-6 hours": 0,
            "6-24 hours": 0,
            "> 24 hours": 0
        }
        
        for market in markets:
            minutes_left = (market.close_ts - now) / 60
            
            if minutes_left < 5:
                buckets["< 5 min"] += 1
            elif minutes_left < 15:
                buckets["5-15 min"] += 1
            elif minutes_left < 30:
                buckets["15-30 min"] += 1
            elif minutes_left < 60:
                buckets["30-60 min"] += 1
            elif minutes_left < 120:
                buckets["1-2 hours"] += 1
            elif minutes_left < 360:
                buckets["2-6 hours"] += 1
            elif minutes_left < 1440:
                buckets["6-24 hours"] += 1
            else:
                buckets["> 24 hours"] += 1
        
        print("\nMarkets by time until close:")
        for label, count in buckets.items():
            pct = count / len(markets) * 100 if markets else 0
            bar = "█" * int(pct / 2)
            print(f"  {label:12} {count:3} ({pct:5.1f}%) {bar}")
        
        print("\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)
        
        long_lived = buckets["1-2 hours"] + buckets["2-6 hours"] + buckets["6-24 hours"] + buckets["> 24 hours"]
        
        if long_lived == 0:
            print("\n❌ No long-lived markets available!")
            print("   All markets close within 1 hour.")
            print("\n   OPTIONS:")
            print("   1. Run bot during times with more markets (mornings/evenings)")
            print("   2. Use production API instead of demo")
            print("   3. Accept shorter monitoring windows (30 min)")
        elif long_lived < 10:
            print(f"\n⚠️  Only {long_lived} markets last 1+ hours")
            print("   This may not be enough for reliable spike detection.")
            print("\n   TIP: Lower time threshold to 30 minutes")
        else:
            print(f"\n✅ {long_lived} markets last 1+ hours")
            print("   Good! You have enough markets to build history.")
            print(f"\n   Use: python scripts/monitor_long_lived_markets.py")
        
        # Show some example long-lived markets
        long_markets = [
            m for m in markets
            if (m.close_ts - now) > 3600  # 1+ hour
        ]
        
        if long_markets:
            print(f"\n📊 SAMPLE LONG-LIVED MARKETS ({len(long_markets)} total):")
            print("-" * 80)
            for i, market in enumerate(long_markets[:5], 1):
                hours = (market.close_ts - now) / 3600
                time_str = f"{hours:.1f}h" if hours < 24 else f"{hours/24:.1f}d"
                print(f"{i}. {market.market_id[:60]}")
                print(f"   Closes in: {time_str} | Price: ${market.price:.4f} | Vol: ${market.liquidity_usd:.2f}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
