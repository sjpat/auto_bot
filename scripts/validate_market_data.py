"""
Quick diagnostic script to validate market data is being pulled correctly.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector
from datetime import datetime


async def main():
    print("=" * 60)
    print("MARKET DATA VALIDATION DIAGNOSTIC")
    print("=" * 60)
    
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    try:
        # Test 1: Authentication
        print("\n[1/5] Testing API authentication...")
        auth_success = await client.authenticate()
        if auth_success:
            print("✅ Authentication successful")
            balance = await client.get_balance()
            print(f"   Account balance: ${balance:.2f}")
        else:
            print("❌ Authentication failed")
            return
        
        # Test 2: Fetch markets
        print("\n[2/5] Fetching open markets...")
        markets = await client.get_markets(status="open", limit=50)
        print(f"✅ Retrieved {len(markets)} markets")
        
        if len(markets) == 0:
            print("❌ No markets found - check API status")
            return
        
        # Test 3: Analyze price data
        print("\n[3/5] Analyzing price data...")
        prices = [m.last_price_cents for m in markets]
        unique_prices = len(set(prices))
        
        print(f"   Unique price points: {unique_prices}/{len(markets)}")
        print(f"   Price range: {min(prices)} - {max(prices)} cents")
        print(f"   Average price: {sum(prices)/len(prices):.0f} cents")
        
        # Check for suspicious patterns
        default_count = sum(1 for p in prices if p == 5000)
        if default_count > len(markets) * 0.3:
            print(f"⚠️  WARNING: {default_count} markets at default price (5000 cents)")
            print(f"   This indicates price fields are not being parsed correctly!")
        
        # Test 4: Check market freshness
        print("\n[4/5] Checking market freshness...")
        now = datetime.now().timestamp()
        active_markets = [m for m in markets if m.close_ts > now]
        print(f"✅ {len(active_markets)}/{len(markets)} markets are active")
        
        # Test 5: Simulate spike detection
        print("\n[5/5] Testing spike detection integration...")
        if len(markets) > 0:
            test_market = markets[0]  # Fixed: markets is already a list of Market objects
            
            print(f"   Using test market: {test_market.market_id}")
            print(f"   Current price: ${test_market.price:.4f} ({test_market.last_price_cents} cents)")
            
            # Add historical prices
            for i in range(25):
                spike_detector.add_price(
                    market_id=test_market.market_id,
                    price=test_market.price,
                    timestamp=datetime.now()
                )
            
            spikes = spike_detector.detect_spikes(markets=[test_market], threshold=0.04)
            print(f"✅ Spike detection working (found {len(spikes)} spikes)")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✅ API connection: OK")
        print(f"✅ Markets retrieved: {len(markets)}")
        print(f"✅ Price diversity: {unique_prices} unique prices")
        print(f"✅ Active markets: {len(active_markets)}")
        print(f"✅ Spike detector: OK")
        
        # Show sample markets
        print("\n📊 Sample of markets (first 5):")
        for i, market in enumerate(markets[:5], 1):
            print(f"\n   {i}. {market.market_id}")
            print(f"      Title: {market.title[:60]}...")
            print(f"      Price: ${market.price:.4f} ({market.last_price_cents} cents)")
            print(f"      Liquidity: ${market.liquidity_usd:.2f}")
            print(f"      Closes: {datetime.fromtimestamp(market.close_ts).strftime('%Y-%m-%d %H:%M')}")
        
        # Recommendations
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        
        if unique_prices == 1 and prices[0] == 5000:
            print("🚨 CRITICAL: All prices are at default value (5000 cents)")
            print("   → The price field mapping in kalshi_client.py is WRONG")
            print("   → Run: python scripts/check_price_fields.py")
            print("   → This is why no spikes are detected!")
        elif unique_prices < len(markets) * 0.3:
            print("⚠️  Price diversity is low. Markets may have stale data.")
            print("   → Check if Kalshi API is returning live prices")
        
        if default_count > len(markets) * 0.2:
            print("⚠️  Many markets at default price (5000 cents).")
            print("   → This could indicate markets haven't traded recently")
        
        if len(active_markets) < len(markets) * 0.5:
            print("⚠️  Many markets are expired.")
            print("   → Consider filtering for markets with longer time to close")
        
        print("\n✅ Validation complete!")
        
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
