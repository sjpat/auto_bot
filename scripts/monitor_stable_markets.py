"""
Monitor a stable set of markets to build price history.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


async def main():
    config = Config()
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)

    # Track a stable set of market IDs
    stable_markets: Set[str] = set()
    market_details = {}  # Store market objects by ID

    print("=" * 80)
    print("STABLE MARKET MONITORING")
    print("Building history for a consistent set of markets")
    print("=" * 80)

    try:
        await client.authenticate()
        balance = await client.get_balance()
        print(f"Account Balance: ${balance:.2f}\n")

        # Initial market selection - pick markets to track
        print("🔍 Finding stable markets to track...")
        all_markets = await client.get_markets(
            status="open", limit=100, min_volume=0, filter_untradeable=False
        )

        # Select top 20 markets by volume + liquidity
        markets_by_volume = sorted(
            all_markets, key=lambda m: m.liquidity_usd, reverse=True
        )

        # Lock onto these markets
        for market in markets_by_volume[:20]:
            stable_markets.add(market.market_id)
            market_details[market.market_id] = {
                "title": market.title,
                "initial_price": market.price,
            }

        print(f"✅ Locked onto {len(stable_markets)} markets for tracking\n")
        print("TRACKED MARKETS:")
        print("-" * 80)
        for i, market_id in enumerate(list(stable_markets)[:10], 1):
            details = market_details[market_id]
            print(f"{i:2}. {market_id[:50]}")
            print(f"    Initial price: ${details['initial_price']:.4f}")
        if len(stable_markets) > 10:
            print(f"... and {len(stable_markets) - 10} more")

        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'=' * 80}")
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{iteration}"
            )
            print("=" * 80)

            # Fetch ALL markets
            all_markets = await client.get_markets(
                status="open", limit=200, min_volume=0, filter_untradeable=False
            )

            # Filter to only our stable markets
            current_markets = {
                m.market_id: m for m in all_markets if m.market_id in stable_markets
            }

            print(f"\n📊 MONITORING STATUS")
            print("-" * 80)
            print(f"   Stable markets tracked: {len(stable_markets)}")
            print(
                f"   Markets currently available: {len(current_markets)}/{len(stable_markets)}"
            )

            missing = stable_markets - set(current_markets.keys())
            if missing:
                print(f"   ⚠️  Markets not found: {len(missing)}")

            # Add prices for available markets
            added_count = 0
            for market_id, market in current_markets.items():
                spike_detector.add_price(
                    market_id=market_id, price=market.price, timestamp=datetime.now()
                )
                added_count += 1

            print(f"   ✅ Prices added: {added_count}")

            # Show history depth
            print(f"\n�� PRICE HISTORY")
            print("-" * 80)

            markets_ready = 0
            markets_building = 0

            for market_id in sorted(stable_markets):
                history_depth = len(spike_detector.price_history.get(market_id, []))

                if history_depth >= 20:
                    markets_ready += 1
                elif history_depth > 0:
                    markets_building += 1

            print(f"   Ready (20+ points): {markets_ready}")
            print(f"   Building (1-19 points): {markets_building}")
            print(
                f"   Not started: {len(stable_markets) - markets_ready - markets_building}"
            )

            # Show detailed status for first few markets
            print(f"\n   Detailed Status (first 5 markets):")
            for i, market_id in enumerate(list(stable_markets)[:5], 1):
                history_depth = len(spike_detector.price_history.get(market_id, []))
                status = "✅" if history_depth >= 20 else f"⏳{history_depth}"

                if market_id in current_markets:
                    price = current_markets[market_id].price
                    print(f"   {i}. {market_id[:40]}... [{status:>4}] ${price:.4f}")
                else:
                    print(f"   {i}. {market_id[:40]}... [{status:>4}] (not available)")

            # Detect spikes (only for markets with sufficient history)
            markets_for_detection = [
                m
                for m in current_markets.values()
                if len(spike_detector.price_history.get(m.market_id, [])) >= 20
            ]

            if markets_for_detection:
                spikes = spike_detector.detect_spikes(
                    markets=markets_for_detection, threshold=config.SPIKE_THRESHOLD
                )

                if spikes:
                    print(f"\n🚨 SPIKES DETECTED: {len(spikes)}")
                    print("=" * 80)
                    for spike in spikes:
                        print(f"  Market: {spike.market_id[:50]}")
                        print(f"  Change: {spike.change_pct:.2%}")
                        print(
                            f"  ${spike.previous_price:.4f} -> ${spike.current_price:.4f}"
                        )
                else:
                    print(
                        f"\n✓ No spikes detected (checking {len(markets_for_detection)} markets)"
                    )
            else:
                print(f"\n⏳ Waiting for markets to build history (20+ points needed)")

            print(f"\n⏳ Waiting 60 seconds...")
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped")

        # Show final summary
        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)
        print(f"Total checks: {iteration}")
        print(f"Markets tracked: {len(stable_markets)}")

        markets_ready = sum(
            1
            for mid in stable_markets
            if len(spike_detector.price_history.get(mid, [])) >= 20
        )
        print(f"Markets with 20+ history: {markets_ready}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
