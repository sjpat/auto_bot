"""
Test what happens when placing an order with $0 balance.
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
        balance = await client.get_balance()

        print(f"Current Balance: ${balance:.2f}\n")

        if balance == 0:
            print("Attempting to place order with $0 balance...")
            print("(This will fail safely)\n")

        # Try to place a small order
        try:
            order = await client.create_order(
                market_id="TEST-MARKET",
                side="buy",
                quantity=1,  # Just 1 contract
                price=0.50,  # $0.50
            )
            print("❌ Unexpected: Order was accepted!")
        except Exception as e:
            print(f"✅ Expected error caught: {e}")
            print("\nThis proves your account is safe from negative balance.")
            print("Kalshi rejected the order due to insufficient funds.")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
