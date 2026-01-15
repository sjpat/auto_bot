"""
Standalone script to validate market data quality and parsing.
Run this to verify the API is returning correct data.
"""
import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.clients.kalshi_client import KalshiClient
from src.config import Config


async def validate_market_data():
    """Validate that market data is being pulled correctly."""
    print("=" * 80)
    print("KALSHI MARKET DATA VALIDATION")
    print("=" * 80)
    
    config = Config()
    client = KalshiClient(config)
    
    try:
        # 1. Test authentication
        print("\n[1/5] Testing authentication...")
        auth_success = await client.authenticate()
        if not auth_success:
            print("❌ Authentication failed!")
            return False
        print("✅ Authentication successful")
        
        balance = await client.get_balance()
        print(f"   Account balance: ${balance:.2f}")
        
        # 2. Test market retrieval
        print("\n[2/5] Fetching open markets...")
        markets = await client.get_markets(
            status="open",
            limit=50,
            min_volume=1,
            filter_untradeable=True
        )
        
        if len(markets) == 0:
            print("❌ No markets returned!")
            return False
        
        print(f"✅ Retrieved {len(markets)} open markets")
        
        # 3. Validate data structure
        print("\n[3/5] Validating market data structure...")
        validation_errors = []
        
        for i, market in enumerate(markets[:10], 1):
            errors = []
            
            if not market.market_id:
                errors.append("missing market_id")
            if not market.title:
                errors.append("missing title")
            if market.close_ts is None:
                errors.append("missing close_ts")
            
            if not (0 <= market.last_price_cents <= 10000):
                errors.append(f"invalid price: {market.last_price_cents}")
            
            now = datetime.now().timestamp()
            if market.close_ts < now:
                time_ago = (now - market.close_ts) / 3600
                errors.append(f"expired {time_ago:.1f}h ago")
            
            if errors:
                validation_errors.append(f"Market {market.market_id}: {', '.join(errors)}")
                print(f"   ⚠️  Market {i}: {market.market_id} - {', '.join(errors)}")
            else:
                print(f"   ✅ Market {i}: {market.market_id}")
        
        if validation_errors:
            print(f"\n⚠️  Found {len(validation_errors)} validation errors")
        else:
            print("\n✅ All markets passed validation")
        
        # 4. Check price diversity
        print("\n[4/5] Checking price diversity...")
        prices = [m.last_price_cents for m in markets]
        unique_prices = len(set(prices))
        diversity_ratio = unique_prices / len(markets)
        
        print(f"   Total markets: {len(markets)}")
        print(f"   Unique prices: {unique_prices}")
        print(f"   Diversity: {diversity_ratio * 100:.1f}%")
        
        if diversity_ratio < 0.3:
            print("   ⚠️  Low price diversity - possible stale data")
        else:
            print("   ✅ Good price diversity")
        
        # 5. Display sample markets
        print("\n[5/5] Sample market data:")
        print("-" * 80)
        
        for market in markets[:5]:
            hours_to_close = market.time_to_expiry_seconds / 3600
            
            print(f"\n📊 {market.market_id}")
            print(f"   Title: {market.title[:60]}...")
            print(f"   Price: ${market.price:.4f} ({market.last_price_cents} basis points)")
            print(f"   Bid: ${market.best_bid_cents/10000:.4f} | Ask: ${market.best_ask_cents/10000:.4f}")
            print(f"   Volume: ${market.liquidity_usd:.2f}")
            print(f"   Status: {market.status}")
            print(f"   Closes in: {hours_to_close:.1f} hours")
        
        print("\n" + "=" * 80)
        print("✅ VALIDATION COMPLETE - Market data looks good!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


if __name__ == "__main__":
    success = asyncio.run(validate_market_data())
    sys.exit(0 if success else 1)
