"""
Debug script to see the actual raw API response from Kalshi.
This will show us the exact field names being returned.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient


async def main():
    print("=" * 60)
    print("KALSHI API RAW RESPONSE DEBUG")
    print("=" * 60)

    config = Config(platform="kalshi")
    client = KalshiClient(config)

    try:
        # Authenticate
        print("\n[1/2] Authenticating...")
        await client.authenticate()
        print("✅ Authenticated")

        # Make raw API call
        print("\n[2/2] Fetching raw market data...")
        params = {"status": "open", "limit": 5}
        raw_response = await client._request("GET", client.markets_url, params=params)

        print("\n" + "=" * 60)
        print("RAW API RESPONSE")
        print("=" * 60)
        print(json.dumps(raw_response, indent=2))

        # Show structure
        if "markets" in raw_response:
            markets = raw_response["markets"]
            if len(markets) > 0:
                print("\n" + "=" * 60)
                print("FIRST MARKET STRUCTURE")
                print("=" * 60)
                first_market = markets[0]
                print("Available fields:")
                for key in first_market.keys():
                    value = first_market[key]
                    print(
                        f"  - {key}: {type(value).__name__} = {value if not isinstance(value, (dict, list)) else '...'}"
                    )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
