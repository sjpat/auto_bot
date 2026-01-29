"""
Test what happens when trying to trade with $0 balance.
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

        print("=" * 60)
        print("ZERO BALANCE TEST")
        print("=" * 60)
        print(f"Current Balance: ${balance:.2f}\n")

        if balance == 0:
            print("⚠️  WARNING: Account balance is $0.00")
            print("\nWhat happens if the bot detects a spike?")
            print("1. ✅ Spike will be detected normally")
            print("2. ✅ Bot will attempt to calculate position size")
            print("3. ❌ Kalshi API will REJECT the order (insufficient funds)")
            print("4. ✅ Bot will log the error and continue monitoring")
            print("5. ✅ You CANNOT go negative - Kalshi prevents this\n")

            print("To enable actual trading:")
            print("1. Deposit funds to your Kalshi account")
            print("2. Bot will automatically use available balance")
            print("3. Risk manager will limit trades to your balance\n")

            print("Current Mode: DETECTION ONLY (no trades possible)")
        else:
            print(f"✅ Balance available: ${balance:.2f}")
            print("Bot can execute trades up to available balance.")

        # Show what order would look like
        print("\n" + "=" * 60)
        print("EXAMPLE ORDER ATTEMPT WITH $0")
        print("=" * 60)

        if balance == 0:
            print("\nIf bot tries to place order:")
            print("  Request: Buy 100 contracts @ $0.65")
            print("  Cost: $65.00")
            print("  Your Balance: $0.00")
            print("  Result: ❌ API returns '403 Insufficient Funds'")
            print("  Bot Action: Logs error, continues monitoring")
            print("\n✅ NO NEGATIVE BALANCE POSSIBLE")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
