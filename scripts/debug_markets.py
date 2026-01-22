#!/usr/bin/env python3
"""
Debug script to check raw market availability from Kalshi API.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient

async def main():
    print("🔍 Debugging Market Fetching...")
    
    config = Config()
    env_type = 'DEMO' if config.KALSHI_DEMO else 'PRODUCTION'
    print(f"Environment: {env_type}")
    print(f"API Key: {config.KALSHI_API_KEY[:5]}..." if config.KALSHI_API_KEY else "❌ Missing API Key")
    
    if config.KALSHI_DEMO:
        print("⚠️  NOTE: You are in DEMO mode. Kalshi Demo often has very few or no open markets.")
    
    client = KalshiClient(config)
    
    try:
        print("\n1. Authenticating...")
        await client.authenticate()
        print("✅ Authenticated")
        
        print("\n2. Fetching Markets (status='open')...")
        # Try fetching with minimal filtering
        markets = await client.get_markets(status="open", limit=10, filter_untradeable=False)
        
        print(f"Response count: {len(markets)}")
        
        if not markets:
            print("❌ No markets returned. This confirms the API is returning an empty list.")
        else:
            print(f"✅ Found {len(markets)} markets. First 3:")
            for m in markets[:3]:
                print(f"   - {m.market_id} | Price: {m.price} | Liquidity: ${getattr(m, 'liquidity_usd', 0):.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())