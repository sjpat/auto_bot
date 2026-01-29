"""
Analyze why opportunities are being missed by the bot.
Checks: Liquidity, Spread, Volatility Speed, and Data Efficiency.
"""

import json
import sys
from pathlib import Path
import numpy as np


def analyze_market_data(file_path):
    print(f"Loading data from {file_path}...")
    with open(file_path, "r") as f:
        data = json.load(f)

    # Handle different json structures
    markets = data.get("spike", data)

    print(f"Analyzing {len(markets)} markets for tradeability...\n")

    stats = {
        "total_markets": len(markets),
        "insufficient_history": 0,
        "low_liquidity": 0,
        "wide_spread": 0,
        "perfect_efficiency": 0,  # No Arb opportunity
        "slow_trends": 0,  # Moves that are too slow for spike detection
        "tradeable_candidates": 0,
    }

    # Config thresholds (matching your BacktestConfig)
    MIN_LIQUIDITY = 500.0
    MAX_SPREAD = 0.30
    SPIKE_THRESHOLD = 0.04  # 4% per step required for SpikeStrategy
    MIN_HISTORY = 20

    for market_id, points in markets.items():
        # Convert simple list to dicts if necessary
        if isinstance(points[0], (int, float)):
            # Simple price list - can't check liquidity/spread
            prices = points
            liquidity = 10000  # Assume good
            spread = 0.01  # Assume good
        else:
            # Full object list
            prices = [p["price"] for p in points]
            liquidity = np.mean([p.get("liquidity", 10000) for p in points])
            # Estimate spread from bid/ask if available, else assume from price
            spreads = []
            for p in points:
                if "yes_ask" in p and "yes_bid" in p:
                    mid = (p["yes_ask"] + p["yes_bid"]) / 2
                    if mid > 0:
                        spreads.append((p["yes_ask"] - p["yes_bid"]) / mid)
                else:
                    spreads.append(0.02)  # Default 2%
            spread = np.mean(spreads)

            # Check Efficiency (Arb opportunity)
            # If data was generated with Yes = Price, No = 1-Price, edge is 0
            if all(
                abs((p.get("price", 0) + (1.0 - p.get("price", 0))) - 1.0) < 0.001
                for p in points
            ):
                stats["perfect_efficiency"] += 1

        # 1. Check History
        if len(prices) < MIN_HISTORY:
            stats["insufficient_history"] += 1
            continue

        # 2. Check Liquidity
        if liquidity < MIN_LIQUIDITY:
            stats["low_liquidity"] += 1
            continue

        # 3. Check Spread
        if spread > MAX_SPREAD:
            stats["wide_spread"] += 1
            continue

        # 4. Check for Spikes (Speed of move)
        # Calculate max single-step percentage change
        price_changes = np.diff(prices)
        pct_changes = np.abs(price_changes / prices[:-1])
        max_spike = np.max(pct_changes) if len(pct_changes) > 0 else 0

        total_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0

        if max_spike < SPIKE_THRESHOLD:
            # Significant move but too slow?
            if abs(total_change) > 0.10:
                stats["slow_trends"] += 1
            continue

        stats["tradeable_candidates"] += 1

    print("--- DIAGNOSTIC RESULTS ---")
    print(f"Total Markets:        {stats['total_markets']}")
    print(
        f"Rejected (History):   {stats['insufficient_history']} (Too few data points)"
    )
    print(
        f"Rejected (Liquidity): {stats['low_liquidity']} (Liquidity < ${MIN_LIQUIDITY})"
    )
    print(f"Rejected (Spread):    {stats['wide_spread']} (Spread > {MAX_SPREAD:.0%})")
    print(
        f"Rejected (Too Slow):  {stats['slow_trends']} (Big moves, but < {SPIKE_THRESHOLD:.0%} per step)"
    )
    print(
        f"Perfect Efficiency:   {stats['perfect_efficiency']} (Markets with 0 Arbitrage edge)"
    )
    print("-" * 30)
    print(f"Tradeable Candidates: {stats['tradeable_candidates']}")

    if stats["tradeable_candidates"] == 0:
        print(
            "\nCONCLUSION: The bot is correct. Your data contains trends, but they are"
        )
        print(
            "either too slow (gradual) for the Spike Strategy, or perfectly efficient"
        )
        print("(no arbitrage) for the Mispricing Strategy.")


if __name__ == "__main__":
    # Default to the test data file used by backtest
    default_file = "/home/shypat/Documents/auto_bot/data/test_volatile_events.json"
    analyze_market_data(default_file)
