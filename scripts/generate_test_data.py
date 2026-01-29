#!/usr/bin/env python3
"""
Generate synthetic historical data for backtesting
Based on real-world volatile events
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import random


def generate_election_night_data():
    """
    Simulate 2024 Presidential Election market
    Real event: Trump odds went from 55% → 95% on election night
    """
    base_time = datetime(2024, 11, 5, 20, 0, 0)  # 8 PM Election Night
    prices = []

    # Pre-results: Stable around 55%
    for i in range(10):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 5)).isoformat(),
                "price": 0.55 + random.uniform(-0.02, 0.02),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    # Results start coming in: Sharp spike
    base_time = base_time + timedelta(minutes=50)
    spike_prices = [0.57, 0.62, 0.68, 0.75, 0.82, 0.88, 0.92, 0.95]  # ~72% spike!

    for i, price in enumerate(spike_prices):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 3)).isoformat(),
                "price": price + random.uniform(-0.005, 0.005),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    # Stabilization
    for i in range(20):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=24 + i * 5)).isoformat(),
                "price": 0.95 + random.uniform(-0.01, 0.01),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    return prices


def generate_nfl_playoff_spike():
    """
    Simulate NFL playoff game market
    Example: Team winning probability spikes when they score
    """
    base_time = datetime(2025, 1, 12, 19, 0, 0)  # Playoff game
    prices = []

    # Game start: Even odds
    for i in range(15):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 2)).isoformat(),
                "price": 0.50 + random.uniform(-0.03, 0.03),
                "liquidity": 25000,
                "volume": 5000,
            }
        )

    # Big touchdown: 15% spike
    base_time = base_time + timedelta(minutes=30)
    spike_sequence = [0.52, 0.57, 0.62, 0.65, 0.64, 0.63]

    for i, price in enumerate(spike_sequence):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": price,
                "liquidity": 25000,
                "volume": 5000,
            }
        )

    # Game continues
    for i in range(30):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=6 + i * 2)).isoformat(),
                "price": 0.63 + random.uniform(-0.04, 0.04),
                "liquidity": 25000,
                "volume": 5000,
            }
        )

    return prices


def generate_fed_decision_spike():
    """
    Simulate Fed rate decision market
    Sharp moves when decision announced
    """
    base_time = datetime(2024, 12, 18, 14, 0, 0)  # Fed decision day 2 PM
    prices = []

    # Pre-announcement: Stable
    for i in range(25):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 2)).isoformat(),
                "price": 0.72 + random.uniform(-0.02, 0.02),
                "liquidity": 100000,
                "volume": 20000,
            }
        )

    # Decision announced: 20% spike
    base_time = base_time + timedelta(minutes=50)
    spike_sequence = [0.73, 0.80, 0.85, 0.88, 0.87]

    for i, price in enumerate(spike_sequence):
        prices.append(
            {
                "timestamp": (base_time + timedelta(seconds=i * 30)).isoformat(),
                "price": price,
                "liquidity": 100000,
                "volume": 20000,
            }
        )

    # Post-announcement
    for i in range(20):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=2.5 + i * 3)).isoformat(),
                "price": 0.86 + random.uniform(-0.02, 0.02),
                "liquidity": 100000,
                "volume": 20000,
            }
        )

    return prices


def generate_nba_finals_comeback():
    """
    Simulate NBA Finals game with dramatic comeback
    """
    base_time = datetime(2025, 6, 12, 20, 0, 0)
    prices = []

    # Team A leading: High probability
    for i in range(20):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 2)).isoformat(),
                "price": 0.75 + random.uniform(-0.03, 0.03),
                "liquidity": 15000,
                "volume": 3000,
            }
        )

    # Team B makes comeback: Sharp decline (inverse spike)
    base_time = base_time + timedelta(minutes=40)
    spike_sequence = [0.74, 0.68, 0.61, 0.54, 0.48, 0.42, 0.38]  # ~50% drop!

    for i, price in enumerate(spike_sequence):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 1.5)).isoformat(),
                "price": price,
                "liquidity": 15000,
                "volume": 3000,
            }
        )

    # Final minutes
    for i in range(15):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=10.5 + i * 2)).isoformat(),
                "price": 0.38 + random.uniform(-0.03, 0.03),
                "liquidity": 15000,
                "volume": 3000,
            }
        )

    return prices


def generate_earnings_surprise():
    """
    Simulate market reaction to major earnings surprise
    """
    base_time = datetime(2025, 1, 25, 16, 0, 0)  # After market close
    prices = []

    # Pre-earnings: Stable
    for i in range(15):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 3)).isoformat(),
                "price": 0.45 + random.uniform(-0.02, 0.02),
                "liquidity": 40000,
                "volume": 8000,
            }
        )

    # Earnings released: Massive beat → 35% spike
    base_time = base_time + timedelta(minutes=45)
    spike_sequence = [0.46, 0.52, 0.58, 0.64, 0.68, 0.70]

    for i, price in enumerate(spike_sequence):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": price,
                "liquidity": 40000,
                "volume": 8000,
            }
        )

    # Settlement
    for i in range(10):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=6 + i * 5)).isoformat(),
                "price": 0.69 + random.uniform(-0.01, 0.02),
                "liquidity": 40000,
                "volume": 8000,
            }
        )

    return prices


def generate_sustained_momentum():
    """
    Simulate a sustained trend that triggers momentum but not necessarily spikes.
    Gradual increase over time (e.g. 1.5% per tick).
    """
    base_time = datetime(2025, 5, 1, 12, 0, 0)
    prices = []

    # Stable start
    current_price = 0.40
    for i in range(20):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price + random.uniform(-0.005, 0.005),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    # Sustained trend (Momentum)
    # Increase by ~1.5% per minute for 20 minutes
    # Total move is significant, but per-tick is below spike threshold (4%)
    # Momentum strategy (window=6, threshold=3%) should catch this.
    base_time = base_time + timedelta(minutes=20)
    for i in range(20):
        current_price *= 1.015  # 1.5% increase
        if current_price > 0.98:
            current_price = 0.98

        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price,
                "liquidity": 60000,
                "volume": 20000,
            }
        )

    # Reversal / Profit taking
    base_time = base_time + timedelta(minutes=20)
    for i in range(15):
        current_price *= 0.99  # Slow drift down
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price,
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    return prices


def generate_march_madness_upset():
    """
    Simulate March Madness upset (15 seed beats 2 seed)
    High volatility and eventual crash for the favorite.
    """
    base_time = datetime(2025, 3, 21, 19, 0, 0)  # March Madness First Round
    prices = []

    # Favorite starts strong
    current_price = 0.82
    for i in range(10):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i * 2)).isoformat(),
                "price": current_price + random.uniform(-0.01, 0.01),
                "liquidity": 80000,
                "volume": 15000,
            }
        )

    # Underdog makes a run (Momentum down for favorite)
    base_time = base_time + timedelta(minutes=20)
    for i in range(15):
        current_price -= 0.02  # Drops 2% per tick (sustained momentum)
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price + random.uniform(-0.01, 0.01),
                "liquidity": 90000,
                "volume": 25000,
            }
        )

    # Panic selling / Crash
    base_time = base_time + timedelta(minutes=15)
    spike_sequence = [current_price, current_price - 0.1, 0.30, 0.20, 0.10, 0.05]

    for i, price in enumerate(spike_sequence):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": max(0.01, price),
                "liquidity": 100000,
                "volume": 50000,
            }
        )

    return prices


def generate_volume_spike():
    """
    Simulate a 'Smart Money' volume spike.
    Price moves moderately, but volume explodes (5x average).
    """
    base_time = datetime(2025, 7, 10, 10, 0, 0)
    prices = []
    cumulative_volume = 10000

    # Quiet period (Low volume)
    current_price = 0.50
    for i in range(15):
        cumulative_volume += random.randint(100, 500)  # ~300 avg tick volume
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price + random.uniform(-0.002, 0.002),
                "liquidity": 20000,
                "volume": cumulative_volume,
            }
        )

    # VOLUME SPIKE! (Smart Money enters)
    # Volume jumps by 2000 in one tick (vs 300 avg) -> ~6.6x spike
    base_time = base_time + timedelta(minutes=15)
    for i in range(5):
        cumulative_volume += random.randint(2000, 3000)
        current_price += 0.01  # Price starts moving up
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": current_price,
                "liquidity": 50000,  # Liquidity also increases
                "volume": cumulative_volume,
            }
        )

    return prices


def generate_correlation_market_a():
    """
    Market A for correlation test (Group: CORRELATION).
    Price ~0.65 ($325 cost). Spikes early.
    """
    base_time = datetime(2025, 8, 1, 12, 0, 0)
    prices = []

    # Stable
    for i in range(10):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": 0.65 + random.uniform(-0.005, 0.005),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    # Spike
    for i in range(5):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=10 + i)).isoformat(),
                "price": 0.68 + (i * 0.02),
                "liquidity": 60000,
                "volume": 20000,
            }
        )

    # Hold
    for i in range(15):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=15 + i)).isoformat(),
                "price": 0.78,
                "liquidity": 50000,
                "volume": 10000,
            }
        )
    return prices


def generate_correlation_market_b():
    """
    Market B for correlation test (Group: CORRELATION).
    Price ~0.65 ($325 cost). Spikes later.
    Should be blocked if A is held and limit is $600 (Total $650 > $600).
    """
    base_time = datetime(2025, 8, 1, 12, 0, 0)
    prices = []

    # Stable longer
    for i in range(15):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "price": 0.65 + random.uniform(-0.005, 0.005),
                "liquidity": 50000,
                "volume": 10000,
            }
        )

    # Spike
    for i in range(5):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=15 + i)).isoformat(),
                "price": 0.68 + (i * 0.02),
                "liquidity": 60000,
                "volume": 20000,
            }
        )

    # Hold
    for i in range(10):
        prices.append(
            {
                "timestamp": (base_time + timedelta(minutes=20 + i)).isoformat(),
                "price": 0.78,
                "liquidity": 50000,
                "volume": 10000,
            }
        )
    return prices


def main():
    """Generate test dataset with multiple volatile markets"""

    print("=" * 80)
    print("GENERATING SYNTHETIC TEST DATA FOR BACKTESTING")
    print("=" * 80)

    test_data = {
        "PRES2024-TRUMP": generate_election_night_data(),
        "NFL-PLAYOFF-KC": generate_nfl_playoff_spike(),
        "FED-RATE-DEC24": generate_fed_decision_spike(),
        "NBA-FINALS-G5": generate_nba_finals_comeback(),
        "TECH-EARNINGS": generate_earnings_surprise(),
        "MOMENTUM-TEST": generate_sustained_momentum(),
        "MARCH-MADNESS-UPSET": generate_march_madness_upset(),
        "VOLUME-SPIKE-TEST": generate_volume_spike(),
        "CORRELATION-A": generate_correlation_market_a(),
        "CORRELATION-B": generate_correlation_market_b(),
    }

    # Save to file
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "test_volatile_events.json"

    with open(output_file, "w") as f:
        json.dump(test_data, f, indent=2)

    print(f"\n✅ Generated test data: {output_file}")
    print(f"\nDataset Summary:")
    print("-" * 80)

    for market_id, prices in test_data.items():
        first_price = prices[0]["price"]
        max_price = max(p["price"] for p in prices)
        min_price = min(p["price"] for p in prices)

        max_spike = (max_price - first_price) / first_price * 100
        max_drop = (first_price - min_price) / first_price * 100

        print(f"\n{market_id}:")
        print(f"  Data points: {len(prices)}")
        print(f"  Price range: ${min_price:.3f} - ${max_price:.3f}")
        print(f"  Max spike: {max_spike:+.1f}%")
        print(f"  Max drop: {-max_drop:+.1f}%")

        # Check for 4%+ moves
        spikes_4pct = 0
        for i in range(1, len(prices)):
            change = (prices[i]["price"] - prices[i - 1]["price"]) / prices[i - 1][
                "price"
            ]
            if abs(change) >= 0.04:
                spikes_4pct += 1

        print(f"  4%+ moves: {spikes_4pct}")

    print("\n" + "=" * 80)
    print("✅ Test data ready! Run backtest with:")
    print("   python scripts/backtest_test_data.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
