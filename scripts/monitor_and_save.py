#!/usr/bin/env python3
"""
Monitor markets and save price history for later backtesting
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


async def main():
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)

    # Data storage
    data_file = Path("data/price_history.json")
    data_file.parent.mkdir(exist_ok=True)

    print("=" * 80)
    print("COLLECTING PRICE HISTORY FOR BACKTESTING")
    print("=" * 80)
    print(f"💾 Saving to: {data_file}")
    print("Press Ctrl+C to stop and save data\n")

    iteration = 0

    try:
        await client.authenticate()

        while True:
            iteration += 1

            # Fetch markets
            markets = await client.get_markets(status="open", limit=200, min_volume=100)

            timestamp = datetime.now()

            # Add prices to spike detector (builds history)
            for market in markets:
                spike_detector.add_price(
                    market_id=market.market_id, price=market.price, timestamp=timestamp
                )

            # Save history periodically
            if iteration % 10 == 0:
                save_history(spike_detector, data_file)

                tracked = len(spike_detector.price_history)
                total_points = sum(
                    len(h) for h in spike_detector.price_history.values()
                )

                print(f"[{timestamp.strftime('%H:%M:%S')}] Check #{iteration}")
                print(f"  Markets tracked: {tracked}")
                print(f"  Total data points: {total_points}")
                print(f"  Saved to: {data_file}\n")

            await asyncio.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping data collection...")
        save_history(spike_detector, data_file)
        print(f"✅ Final data saved to: {data_file}")

        tracked = len(spike_detector.price_history)
        total_points = sum(len(h) for h in spike_detector.price_history.values())
        print(f"\n📊 Collection Summary:")
        print(f"   Markets tracked: {tracked}")
        print(f"   Total data points: {total_points}")
        print(f"   Duration: {iteration} minutes")

    finally:
        await client.close()


def save_history(spike_detector, data_file):
    """Save price history to JSON file"""
    data = {}

    for market_id, history in spike_detector.price_history.items():
        data[market_id] = [
            {
                "timestamp": (
                    point[1].isoformat()
                    if len(point) > 1
                    else datetime.now().isoformat()
                ),
                "price": point[0] if isinstance(point, tuple) else point,
            }
            for point in history
        ]

    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
