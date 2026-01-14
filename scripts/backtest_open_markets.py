#!/usr/bin/env python3
"""
Backtest using currently open markets with their recent price history
This is faster for testing since we don't need to wait for markets to settle
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
    """Backtest using open markets with price history"""
    
    print("="*80)
    print("BACKTESTING - OPEN MARKETS WITH PRICE HISTORY")
    print("="*80)
    
    # Configuration
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    
    # Backtest parameters
    backtest_config = BacktestConfig(
        starting_balance=10000,
        spike_threshold=0.10,
        max_position_size=100,
        position_size_pct=0.02,
        stop_loss_pct=0.20,
        take_profit_pct=0.30,
        max_hold_time=timedelta(hours=24),
        min_liquidity=100,
        enable_fees=True,
        fee_rate=0.07
    )
    
    print(f"\n💰 Starting Balance: ${backtest_config.starting_balance:,.2f}")
    print(f"🎯 Spike Threshold: {backtest_config.spike_threshold:.1%}")
    
    try:
        # Authenticate
        print("\n🔐 Authenticating with Kalshi...")
        await client.authenticate()
        
        # Get currently open markets with decent volume
        print("\n📊 Fetching open markets with volume...")
        open_markets = await client.get_markets(
            status="open",
            limit=100,
            min_volume=50  # Lower threshold to get more markets
        )
        
        if not open_markets:
            print("❌ No open markets found")
            return
        
        print(f"✅ Found {len(open_markets)} open markets")
        
        # Filter for markets with good volume
        filtered_markets = [m for m in open_markets if m.volume >= 5000]  # $50+ in volume
        
        if not filtered_markets:
            print("❌ No markets with sufficient volume")
            print(f"   Try lowering min_volume threshold")
            return
        
        print(f"✅ {len(filtered_markets)} markets with good volume")
        
        # Fetch historical data for each market
        print("\n📊 Fetching historical price data...")
        fetcher = HistoricalDataFetcher(client)
        historical_data = {}
        
        for i, market in enumerate(filtered_markets[:10], 1):  # Start with 10 markets
            print(f"   [{i}/10] Fetching history for {market.market_id}...")
            
            try:
                history = await fetcher.fetch_market_history(
                    market_id=market.market_id,
                    use_cache=True
                )
                
                if history and len(history) >= 20:  # Need at least 20 data points
                    historical_data[market.market_id] = history
                    print(f"      ✓ {len(history)} data points")
                else:
                    print(f"      ✗ Insufficient history ({len(history) if history else 0} points)")
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"      ✗ Error: {e}")
                continue
        
        if not historical_data:
            print("\n❌ No markets with sufficient historical data")
            print("   Try these alternatives:")
            print("   1. Run your monitor script for a few hours to build price history")
            print("   2. Look for markets with longer trading history")
            print("   3. Use closed/settled markets from the past")
            return
        
        print(f"\n✅ Ready to backtest with {len(historical_data)} markets")
        
        # Determine date range from actual data
        all_timestamps = []
        for history in historical_data.values():
            all_timestamps.extend([p.timestamp for p in history])
        
        start_date = min(all_timestamps)
        end_date = max(all_timestamps)
        
        print(f"📅 Date range: {start_date} to {end_date}")
        print(f"   Duration: {(end_date - start_date).total_seconds() / 3600:.1f} hours")
        
        # Initialize components
        spike_detector = SpikeDetector(config)
        fee_calculator = FeeCalculator()
        
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
        
        # Print summary
        report.print_summary()
        
        # Print trades
        if results.total_trades > 0:
            report.print_trade_log(limit=20)
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report.save_to_json(f"backtest_open_{timestamp}.json")
        report.generate_html_report(f"backtest_open_{timestamp}.html")
        
        print("\n✅ Backtest complete!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Backtest interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
