#!/usr/bin/env python3
"""
Run backtesting on historical Kalshi market data
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector
from src.trading.fee_calculator import FeeCalculator
from src.backtesting import (
    HistoricalDataFetcher,
    BacktestEngine,
    BacktestConfig,
    BacktestReport
)

async def main():
    """Main backtest execution"""
    
    print("="*80)
    print("BACKTESTING - SPIKE TRADING STRATEGY")
    print("="*80)
    
    # Configuration
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    
    # Backtest parameters
    backtest_config = BacktestConfig(
        starting_balance=10000,
        spike_threshold=0.04,  # 10% spike threshold
        max_position_size=100,
        position_size_pct=0.02,  # 2% per trade
        stop_loss_pct=0.20,  # 20% stop loss
        take_profit_pct=0.30,  # 30% take profit
        max_hold_time=timedelta(hours=24),
        min_liquidity=100,
        enable_fees=True,
        fee_rate=0.07
    )
    
    # Date range for backtest
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # Last 30 days
    
    print(f"\n📅 Backtest Period: {start_date.date()} to {end_date.date()}")
    print(f"💰 Starting Balance: ${backtest_config.starting_balance:,.2f}")
    print(f"🎯 Spike Threshold: {backtest_config.spike_threshold:.1%}")
    print(f"📊 Position Size: {backtest_config.position_size_pct:.1%} of balance")
    
    try:
        # Authenticate
        print("\n🔐 Authenticating with Kalshi...")
        await client.authenticate()
        
        # Initialize components
        fetcher = HistoricalDataFetcher(client)
        spike_detector = SpikeDetector(config)
        fee_calculator = FeeCalculator()
        
        # Fetch historical data
        print("\n📊 Fetching historical market data...")
        historical_data = await fetcher.build_backtest_dataset(
            start_date=start_date,
            end_date=end_date,
            min_volume=1000,
            max_markets=20  # Start with 20 markets for testing
        )
        
        if not historical_data:
            print("❌ No historical data found for the specified period")
            return
        
        print(f"✅ Loaded {len(historical_data)} markets with historical data")
        
        # Initialize backtest engine
        engine = BacktestEngine(
            spike_detector=spike_detector,
            config=backtest_config,
            fee_calculator=fee_calculator
        )
        
        # Run backtest
        print("\n🚀 Running backtest...")
        results = await engine.run_backtest(
            historical_data=historical_data,
            start_date=start_date,
            end_date=end_date
        )
        
        # Generate reports
        print("\n📊 Generating reports...")
        report = BacktestReport(results)
        
        # Print summary to console
        report.print_summary()
        
        # Print recent trades
        report.print_trade_log(limit=20)
        
        # Save JSON results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report.save_to_json(f"backtest_{timestamp}.json")
        
        # Generate HTML report
        report.generate_html_report(f"backtest_{timestamp}.html")
        
        print("\n✅ Backtest complete!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Backtest interrupted by user")
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
