#!/usr/bin/env python3
"""
Run backtest on synthetic test data
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
    print("="*80)
    print("BACKTESTING ON SYNTHETIC VOLATILE EVENTS")
    print("="*80)
    
    # Load test data
    test_file = Path("data/test_volatile_events.json")
    
    if not test_file.exists():
        print(f"❌ Test data not found. Generate it first:")
        print(f"   python scripts/generate_test_data.py")
        return
    
    with open(test_file, 'r') as f:
        raw_data = json.load(f)
    
    print(f"\n📊 Loaded {len(raw_data)} test markets")
    
    # Convert to HistoricalPricePoint format
    historical_data = {}
    for market_id, points in raw_data.items():
        historical_data[market_id] = [
            HistoricalPricePoint(
                timestamp=datetime.fromisoformat(p['timestamp']),
                price=p['price'],
                yes_bid=p['price'] * 0.99,
                yes_ask=p['price'] * 1.01,
                volume=10000,  # Assume decent volume
                liquidity=1000,
                market_id=market_id
            )
            for p in points
        ]
    
    # Get date range
    all_timestamps = []
    for history in historical_data.values():
        all_timestamps.extend([p.timestamp for p in history])
    
    start_date = min(all_timestamps)
    end_date = max(all_timestamps)
    
    print(f"\n📅 Date Range:")
    print(f"   {start_date} to {end_date}")
    print(f"   Duration: {(end_date - start_date).total_seconds() / 3600:.1f} hours")
    
    # Backtest configuration
    config = Config(platform="kalshi")
    backtest_config = BacktestConfig(
        starting_balance=10000,
        spike_threshold=0.04,
        position_size_pct=0.01,
        stop_loss_pct=0.05,
        take_profit_pct=0.05,
        max_hold_time=timedelta(minutes=5),
        max_concurrent_positions=10,  # ← Configure here
        enable_fees=True
    )
    
    print(f"\n💰 Backtest Config:")
    print(f"   Starting Balance: ${backtest_config.starting_balance:,.2f}")
    print(f"   Spike Threshold: {backtest_config.spike_threshold:.1%}")
    print(f"   Position Size: {backtest_config.position_size_pct:.1%}")
    print(f"   Stop Loss: {backtest_config.stop_loss_pct:.1%}")
    print(f"   Take Profit: {backtest_config.take_profit_pct:.1%}")
    
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
        report.print_trade_log(limit=50)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report.save_to_json(f"backtest_volatile_{timestamp}.json")
    report.generate_html_report(f"backtest_volatile_{timestamp}.html")
    
    print("\n✅ Backtest complete on synthetic volatile events!")

if __name__ == "__main__":
    asyncio.run(main())
