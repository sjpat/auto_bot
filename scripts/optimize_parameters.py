#!/usr/bin/env python3
"""
Grid Search Optimization Script.

Evaluates multiple parameter combinations to find the optimal configuration
for the trading bot using the parity-aligned backtest engine.
"""

import asyncio
import sys
import json
import logging
import itertools
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.strategies.strategy_manager import StrategyManager
from src.trading.risk_manager import RiskManager
from src.trading.fee_calculator import FeeCalculator
from src.trading.market_filter import MarketFilter
from src.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    HistoricalPricePoint,
)

# Suppress detailed logs during optimization to keep output clean
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("Optimizer")
logger.setLevel(logging.INFO)

# Silence component loggers
logging.getLogger("src.backtesting.backtest_engine").setLevel(logging.WARNING)
logging.getLogger("src.strategies.strategy_manager").setLevel(logging.WARNING)
logging.getLogger("src.trading.risk_manager").setLevel(logging.WARNING)


async def load_test_data():
    """Load and prepare synthetic test data (reused from backtest_test_data.py)."""
    test_file = Path("data/test_volatile_events.json")
    if not test_file.exists():
        logger.error("❌ Test data not found. Run scripts/generate_test_data.py first.")
        sys.exit(1)

    with open(test_file, "r") as f:
        raw_data = json.load(f)

    historical_data = {}
    WARMUP_POINTS = 30
    INEFFICIENCY_EDGE = 0.10

    for market_id, points in raw_data.items():
        first_point = points[0]
        start_ts = datetime.fromisoformat(first_point["timestamp"])
        start_price = first_point["price"]

        # Generate warmup data
        full_points = []
        for i in range(WARMUP_POINTS):
            ts = start_ts - timedelta(minutes=WARMUP_POINTS - i)
            full_points.append(
                {
                    "timestamp": ts.isoformat(),
                    "price": start_price,
                    "volume": 10000,
                    "liquidity": 1000.0,
                }
            )
        full_points.extend(points)

        historical_data[market_id] = [
            HistoricalPricePoint(
                timestamp=datetime.fromisoformat(p["timestamp"]),
                yes_price=p["price"],
                no_price=max(0.01, 1.0 - p["price"] - INEFFICIENCY_EDGE),
                liquidity_usd=p.get("liquidity", 1000.0),
                bid=p["price"] * 0.99,
                ask=p["price"] * 1.01,
                volume_24h=p.get("volume", 10000),
                expiry_timestamp=datetime.fromisoformat(p["timestamp"])
                + timedelta(days=7),
            )
            for p in full_points
        ]

    # Calculate date range
    all_timestamps = []
    for history in historical_data.values():
        all_timestamps.extend([p.timestamp for p in history])

    return historical_data, min(all_timestamps), max(all_timestamps)


async def run_optimization():
    print("=" * 80)
    print("🚀 STARTING PARAMETER GRID SEARCH")
    print("=" * 80)

    # Load data
    data, start_date, end_date = await load_test_data()
    print(f"📊 Loaded {len(data)} markets. Range: {start_date} to {end_date}")

    # ========================================================================
    # 1. DEFINE SEARCH GRID
    # ========================================================================
    param_grid = {
        "TRADE_UNIT": [100, 500],
        "SPIKE_THRESHOLD": [0.04, 0.05],
        "TARGET_PROFIT_USD": [30.0, 50.0],
        "TARGET_LOSS_USD": [-5.0, -10.0],
        "MOMENTUM_WINDOW": [3, 6],
        "MOMENTUM_THRESHOLD": [0.03, 0.05],
        "MOMENTUM_REVERSAL_MULTIPLIER": [0.5, 0.8],
        "MIN_EDGE": [0.05, 0.08],
        "VOLUME_SPIKE_THRESHOLD": [3.0, 5.0],
        "TRAILING_STOP_ACTIVATION_USD": [15.0, 25.0],
        "TRAILING_STOP_DISTANCE_USD": [5.0, 10.0],
        "MAX_EVENT_EXPOSURE_USD": [200.0, 600.0],
    }

    keys = list(param_grid.keys())
    combinations = list(itertools.product(*param_grid.values()))

    print(f"Testing {len(combinations)} parameter combinations...")
    print("-" * 90)
    print(
        f"{'ID':<4} | {'Unit':<4} {'Spk':<4} {'TP':<4} {'SL':<4} {'MW':<2} {'MT':<4} {'RM':<3} {'Edg':<4} {'Vol':<3} {'TA':<4} {'TD':<4} {'Exp':<4} | {'Return':<9} {'Win%':<5} {'Trds':<5}"
    )
    print("-" * 90)

    results = []

    # ========================================================================
    # 2. RUN GRID SEARCH
    # ========================================================================
    for i, values in enumerate(combinations):
        params = dict(zip(keys, values))

        # Configure Live Components (Strategy & Risk)
        live_config = Config(platform="kalshi")
        live_config.TARGET_PROFIT_USD = params["TARGET_PROFIT_USD"]
        live_config.TARGET_LOSS_USD = params["TARGET_LOSS_USD"]
        live_config.SPIKE_THRESHOLD = params["SPIKE_THRESHOLD"]
        live_config.MIN_EDGE = params["MIN_EDGE"]
        live_config.MIN_CONFIDENCE_MISPRICING = 0.60

        # Momentum Settings
        live_config.ENABLE_MOMENTUM_STRATEGY = True
        live_config.MOMENTUM_WINDOW = params["MOMENTUM_WINDOW"]
        live_config.MOMENTUM_THRESHOLD = params["MOMENTUM_THRESHOLD"]
        live_config.MIN_CONFIDENCE_MOMENTUM = 0.65
        live_config.MOMENTUM_REVERSAL_MULTIPLIER = params[
            "MOMENTUM_REVERSAL_MULTIPLIER"
        ]

        # Volume Settings
        live_config.ENABLE_VOLUME_STRATEGY = True
        live_config.VOLUME_SPIKE_THRESHOLD = params["VOLUME_SPIKE_THRESHOLD"]
        live_config.MIN_VOLUME_FOR_STRATEGY = 100

        # Mispricing Settings
        live_config.ENABLE_MISPRICING_STRATEGY = True

        # Initialize Components (Fresh for each run)
        strategy_manager = StrategyManager(config=live_config)
        risk_manager = RiskManager(client=None, config=live_config)
        fee_calculator = FeeCalculator()
        market_filter = MarketFilter(config=live_config)

        # Configure Backtest Engine
        backtest_config = BacktestConfig(
            starting_balance=10000.0,
            TRADE_UNIT=params["TRADE_UNIT"],
            MAX_CONCURRENT_TRADES=3,
            SPIKE_THRESHOLD=params["SPIKE_THRESHOLD"],
            TARGET_PROFIT_USD=params["TARGET_PROFIT_USD"],
            TARGET_LOSS_USD=params["TARGET_LOSS_USD"],
            # Dynamic Trailing Stop
            USE_TRAILING_STOP=True,
            TRAILING_STOP_ACTIVATION_USD=params["TRAILING_STOP_ACTIVATION_USD"],
            TRAILING_STOP_DISTANCE_USD=params["TRAILING_STOP_DISTANCE_USD"],
            MAX_SLIPPAGE_TOLERANCE=0.025,  # From input
            MIN_LIQUIDITY_USD=500.0,  # From input
            MAX_SPREAD_PCT=0.30,  # From input
            MAX_DAILY_LOSS_PCT=0.15,  # From input
            MAX_EVENT_EXPOSURE_USD=params["MAX_EVENT_EXPOSURE_USD"],
        )

        engine = BacktestEngine(
            strategy_manager=strategy_manager,
            risk_manager=risk_manager,
            fee_calculator=fee_calculator,
            market_filter=market_filter,
            config=backtest_config,
        )

        # Run Backtest
        res = await engine.run_backtest(data, start_date, end_date)

        # Record Result
        result_entry = {
            "params": params,
            "metrics": {
                "return_usd": res.total_return_usd,
                "return_pct": res.total_return_pct,
                "win_rate": res.win_rate,
                "trades": res.total_trades,
                "drawdown": res.max_drawdown_pct,
            },
        }
        results.append(result_entry)

        # Print Progress row
        print(
            f"{i+1:<4} | {params['TRADE_UNIT']:<4} {params['SPIKE_THRESHOLD']:<4.2f} {params['TARGET_PROFIT_USD']:<4.0f} {params['TARGET_LOSS_USD']:<4.0f} {params['MOMENTUM_WINDOW']:<2} {params['MOMENTUM_THRESHOLD']:<4.2f} {params['MOMENTUM_REVERSAL_MULTIPLIER']:<3.1f} {params['MIN_EDGE']:<4.2f} {params['VOLUME_SPIKE_THRESHOLD']:<3.1f} {params['TRAILING_STOP_ACTIVATION_USD']:<4.0f} {params['TRAILING_STOP_DISTANCE_USD']:<4.0f} {params['MAX_EVENT_EXPOSURE_USD']:<4.0f} | ${res.total_return_usd:<8.2f} {res.win_rate:<5.1f} {res.total_trades:<5}"
        )

    # ========================================================================
    # 3. ANALYZE RESULTS
    # ========================================================================
    # Sort results by Return USD
    results.sort(key=lambda x: x["metrics"]["return_usd"], reverse=True)

    print("=" * 80)
    print("🏆 TOP 3 CONFIGURATIONS")
    print("=" * 80)

    for i, res in enumerate(results[:3]):
        p = res["params"]
        m = res["metrics"]
        print(f"\nRank #{i+1}: Return ${m['return_usd']:.2f} ({m['return_pct']:.2f}%)")
        print(f"  • Trade Unit: {p['TRADE_UNIT']}")
        print(f"  • Spike Threshold: {p['SPIKE_THRESHOLD']:.2f}")
        print(f"  • Targets: +${p['TARGET_PROFIT_USD']} / ${p['TARGET_LOSS_USD']}")
        print(
            f"  • Momentum: Window={p['MOMENTUM_WINDOW']}, Thresh={p['MOMENTUM_THRESHOLD']:.2f}"
        )
        print(f"  • Volume: Thresh={p['VOLUME_SPIKE_THRESHOLD']:.1f}")
        print(f"  • Mispricing: Edge={p['MIN_EDGE']:.2f}")
        print(
            f"  • Trailing Stop: Activate=${p['TRAILING_STOP_ACTIVATION_USD']}, Dist=${p['TRAILING_STOP_DISTANCE_USD']}"
        )
        print(f"  • Risk: Max Exposure=${p['MAX_EVENT_EXPOSURE_USD']}")
        print(
            f"  • Stats: {m['trades']} trades, {m['win_rate']:.1f}% win rate, {m['drawdown']:.2f}% drawdown"
        )

    # Save best config suggestion
    best = results[0]["params"]
    print("\n💾 Recommended .env updates:")
    print("-" * 40)
    print(f"TRADE_UNIT={best['TRADE_UNIT']}")
    print(f"SPIKE_THRESHOLD={best['SPIKE_THRESHOLD']}")
    print(f"TARGET_PROFIT_USD={best['TARGET_PROFIT_USD']}")
    print(f"TARGET_LOSS_USD={best['TARGET_LOSS_USD']}")
    print(f"MOMENTUM_WINDOW={best['MOMENTUM_WINDOW']}")
    print(f"MOMENTUM_THRESHOLD={best['MOMENTUM_THRESHOLD']}")
    print(f"MOMENTUM_REVERSAL_MULTIPLIER={best['MOMENTUM_REVERSAL_MULTIPLIER']}")
    print(f"VOLUME_SPIKE_THRESHOLD={best['VOLUME_SPIKE_THRESHOLD']}")
    print(f"MIN_EDGE={best['MIN_EDGE']}")
    print(f"TRAILING_STOP_ACTIVATION_USD={best['TRAILING_STOP_ACTIVATION_USD']}")
    print(f"TRAILING_STOP_DISTANCE_USD={best['TRAILING_STOP_DISTANCE_USD']}")
    print(f"MAX_EVENT_EXPOSURE_USD={best['MAX_EVENT_EXPOSURE_USD']}")
    print("-" * 40)


if __name__ == "__main__":
    asyncio.run(run_optimization())
