"""
Check what price fields are actually in the API response.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient


async def main():
    config = Config(platform="kalshi")
    client = KalshiClient(config)

    try:
        await client.authenticate()

        params = {"status": "open", "limit": 3}
        response = await client._request("GET", client.markets_url, params=params)

        if "markets" in response and len(response["markets"]) > 0:
            print("=" * 60)
            print("FIRST MARKET - ALL FIELDS")
            print("=" * 60)
            market = response["markets"][0]
            print(json.dumps(market, indent=2))

            print("\n" + "=" * 60)
            print("PRICE-RELATED FIELDS")
            print("=" * 60)
            for key, value in market.items():
                if any(
                    word in key.lower()
                    for word in ["price", "bid", "ask", "last", "yes", "no"]
                ):
                    print(f"  {key}: {value} (type: {type(value).__name__})")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
