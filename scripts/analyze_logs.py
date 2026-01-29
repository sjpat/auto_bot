"""
Analyze market logs to understand bot behavior.
"""

import sys
from pathlib import Path
from collections import Counter
import re


def analyze_market_log(log_file: str):
    """Analyze a market log file."""

    fetches = []
    spikes = []
    changes = []

    with open(log_file, "r") as f:
        for line in f:
            if "FETCH" in line:
                # Extract tradeable markets count
                match = re.search(r"Tradeable: (\d+)", line)
                if match:
                    fetches.append(int(match.group(1)))

            elif "SPIKE" in line:
                # Extract spike info
                match = re.search(r"Change: ([+-]?\d+\.\d+)%", line)
                if match:
                    spikes.append(float(match.group(1)))

            elif "CHANGE" in line:
                # Extract change info
                match = re.search(r"(UP|DOWN) (\d+\.\d+)%", line)
                if match:
                    changes.append(float(match.group(2)))

    print("=" * 60)
    print(f"LOG ANALYSIS: {log_file}")
    print("=" * 60)

    print(f"\nMarket Fetches: {len(fetches)}")
    if fetches:
        print(f"  Avg tradeable markets: {sum(fetches)/len(fetches):.1f}")
        print(f"  Min/Max: {min(fetches)}/{max(fetches)}")

    print(f"\nSpikes Detected: {len(spikes)}")
    if spikes:
        print(f"  Avg spike size: {sum(abs(s) for s in spikes)/len(spikes):.2f}%")
        print(f"  Largest spike: {max(abs(s) for s in spikes):.2f}%")

    print(f"\nPrice Changes (>2%): {len(changes)}")
    if changes:
        print(f"  Avg change: {sum(changes)/len(changes):.2f}%")


if __name__ == "__main__":
    log_dir = Path("logs/markets")
    if log_dir.exists():
        logs = sorted(log_dir.glob("*.log"))
        if logs:
            analyze_market_log(str(logs[-1]))  # Analyze most recent
        else:
            print("No log files found")
    else:
        print(f"Log directory not found: {log_dir}")
