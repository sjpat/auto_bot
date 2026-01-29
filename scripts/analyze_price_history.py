import json
from pathlib import Path


def main():
    file_path = Path("/home/shypat/Documents/auto_bot/data/price_history.json")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    # Handle structure { "spike": { ... } } or flat { ... }
    markets = data.get("spike", data)

    print(f"Analyzing {len(markets)} market histories...")

    significant_moves = []
    recoveries = []

    for market_id, prices in markets.items():
        if not prices or len(prices) < 2:
            continue

        start_price = prices[0]
        end_price = prices[-1]
        min_price = min(prices)

        # Calculate percentage change
        if start_price == 0:
            change_pct = 0
        else:
            change_pct = (end_price - start_price) / start_price

        # Check for significant movement (>10%)
        if abs(change_pct) > 0.10:
            significant_moves.append(
                {
                    "market": market_id,
                    "start": start_price,
                    "end": end_price,
                    "change": change_pct,
                }
            )

        # Check for recovery: Price dropped significantly but ended higher than the low
        # (e.g. 0.5 -> 0.1 -> 0.4)
        if min_price < start_price - 0.10 and end_price > min_price + 0.05:
            recoveries.append(
                {
                    "market": market_id,
                    "start": start_price,
                    "min": min_price,
                    "end": end_price,
                }
            )

    up_moves = [m for m in significant_moves if m["change"] > 0]
    down_moves = [m for m in significant_moves if m["change"] < 0]

    print(f"\n--- Results ---")
    print(f"Significant Downward Moves (Crashes): {len(down_moves)}")
    print(f"Significant Upward Moves (Rallies):   {len(up_moves)}")
    print(f"Recoveries (Dip & Rebound):           {len(recoveries)}")

    if len(up_moves) == 0 and len(recoveries) == 0:
        print("\nVERIFICATION: No missed opportunities detected.")
        print(
            "The bot correctly avoided trading because all significant moves were price crashes."
        )
    else:
        print(
            "\nWARNING: Potential missed opportunities found. Review the lists above."
        )


if __name__ == "__main__":
    main()
