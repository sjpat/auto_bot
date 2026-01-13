"""
Debug why no markets are being returned.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient


async def main():
    config = Config()
    client = KalshiClient(config)
    
    try:
        await client.authenticate()
        
        print("=" * 60)
        print("DEBUGGING MARKET FILTERING")
        print("=" * 60)
        
        # Test 1: Get markets WITHOUT filtering
        print("\n[1] Raw markets (no filtering):")
        raw_markets = await client.get_markets(
            status="open", 
            limit=50, 
            filter_untradeable=False
        )
        print(f"   Total markets returned: {len(raw_markets)}")
        
        if len(raw_markets) > 0:
            # Show details of first few markets
            print(f"\n   First 5 markets:")
            for i, m in enumerate(raw_markets[:5], 1):
                print(f"   {i}. {m.market_id[:40]}")
                print(f"      Price: ${m.price:.4f} ({m.last_price_cents} cents)")
                print(f"      Volume: ${m.liquidity_usd:.2f}")
        
        # Test 2: With default filtering (min_volume=1)
        print(f"\n[2] With filtering (min_volume=1):")
        filtered_markets_1 = await client.get_markets(
            status="open",
            limit=50,
            min_volume=1,
            filter_untradeable=True
        )
        print(f"   Tradeable markets: {len(filtered_markets_1)}")
        
        # Test 3: With NO volume requirement
        print(f"\n[3] With filtering (min_volume=0):")
        filtered_markets_0 = await client.get_markets(
            status="open",
            limit=50,
            min_volume=0,
            filter_untradeable=True
        )
        print(f"   Markets with any price: {len(filtered_markets_0)}")
        
        # Analyze why markets are filtered out
        print("\n" + "=" * 60)
        print("ANALYSIS")
        print("=" * 60)
        
        if len(raw_markets) == 0:
            print("❌ No markets returned from API at all")
            print("   Possible causes:")
            print("   - Using demo API with no active markets")
            print("   - Need to switch to production API")
            print("   - API connection issue")
        else:
            print(f"✅ API returned {len(raw_markets)} markets")
            
            # Check how many have prices
            markets_with_prices = [m for m in raw_markets if m.last_price_cents > 0]
            print(f"   Markets with prices > 0: {len(markets_with_prices)}")
            
            # Check how many have volume
            markets_with_volume = [m for m in raw_markets if m.liquidity_cents > 0]
            print(f"   Markets with volume > 0: {len(markets_with_volume)}")
            
            # Check both criteria
            tradeable = [m for m in raw_markets 
                        if m.last_price_cents > 0 and m.liquidity_cents >= 1]
            print(f"   Markets meeting both criteria: {len(tradeable)}")
            
            if len(tradeable) == 0:
                print("\n⚠️  No markets meet trading criteria:")
                print("   All markets have either:")
                print("   - No trading activity (price = 0)")
                print("   - No volume (liquidity < $0.01)")
                print("\n   RECOMMENDATION: Use filter_untradeable=False to monitor all markets")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
