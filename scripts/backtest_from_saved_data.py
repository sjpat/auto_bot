#!/usr/bin/env python3
"""
Run backtest using previously collected price history
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.trading.spike_detector import SpikeDetector
from src.trading.fee_calculator import FeeCalculator
from src.backtesting import (
    BacktestEngine,
    BacktestConfig,
    BacktestReport,
    HistoricalPricePoint
)

async def main():
    # Load saved price history
    data_file = Path("data/price_history.json")
    
    if not data_file.exists():
        print(f"❌ No saved price history found at {data_file}")
        print("\nRun data collection first:")
        print("  python scripts/monitor_and_save.py")
        print("\nLet it run for at least 2-3 hours to collect sufficient data")
        return
    
    print("="*80)
    print("BACKTESTING FROM SAVED PRICE HISTORY")
    print("="*80)
    
    # Load data
    with open(data_file, 'r') as f:
        raw_data = json.load(f)
    
    print(f"\n📊 Loaded data from: {data_file}")
    print(f"   Markets: {len(raw_data)}")
    
    # Convert to HistoricalPricePoint objects
    historical_data = {}
    for market_id, points in raw_data.items():
        if len(points) >= 20:  # Need at least 20 points
            historical_data[market_id] = [
                HistoricalPricePoint(
                    timestamp=datetime.fromisoformat(p['timestamp']),
                    price=p['price'],
                    yes_bid=p['price'] * 0.99,  # Approximate
                    yes_ask=p['price'] * 1.01,
                    volume=0,
                    liquidity=100,
                    market_id=market_id
                )
                for p in points
            ]
    
    if not historical_data:
        print(f"\n❌ No markets with 20+ data points")
        current_max = max(len(points) for points in raw_data.values())
        print(f"   Current maximum: {current_max} points")
        print(f"\n💡 Run monitor_and_save.py longer to collect more data")
        return
    
    print(f"✅ {len(historical_data)} markets ready for backtesting")
    
    # Get date range
    all_timestamps = []
    for history in historical_data.values():
        all_timestamps.extend([p.timestamp for p in history])
    
    start_date = min(all_timestamps)
    end_date = max(all_timestamps)
    duration = end_date - start_date
    
    print(f"\n📅 Data Range:")
    print(f"   Start: {start_date}")
    print(f"   End: {end_date}")
    print(f"   Duration: {duration.total_seconds() / 3600:.1f} hours")
    
    # Backtest configuration
    config = Config(platform="kalshi")
    backtest_config = BacktestConfig(
        starting_balance=10000,
        spike_threshold=0.04,
        position_size_pct=0.02,
        stop_loss_pct=0.20,
        take_profit_pct=0.30,
        max_hold_time=timedelta(hours=24),
        enable_fees=True
    )
    
    print(f"\n💰 Backtest Configuration:")
    print(f"   Starting Balance: ${backtest_config.starting_balance:,.2f}")
    print(f"   Spike Threshold: {backtest_config.spike_threshold:.1%}")
    
    # Run backtest
    spike_detector = SpikeDetector(config)
    fee_calculator = FeeCalculator()
    
    engine = BacktestEngine(
        spike_detector=spike_detector,
        config=backtest_config,
        fee_calculator=fee_calculator
    )
    
    print(f"\n🚀 Running backtest...")
    results = await engine.run_backtest(
        historical_data=historical_data,
        start_date=start_date,
        end_date=end_date
    )
    
    # Generate report
    report = BacktestReport(results)
    report.print_summary()
    
    if results.total_trades > 0:
        report.print_trade_log(limit=20)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report.save_to_json(f"backtest_saved_{timestamp}.json")
    report.generate_html_report(f"backtest_saved_{timestamp}.html")
    
    print("\n✅ Backtest complete!")

if __name__ == "__main__":
    asyncio.run(main())
