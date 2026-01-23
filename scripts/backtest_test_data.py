#!/usr/bin/env python3

"""
Run backtest on synthetic test data using the parity-aligned engine.

Updated: 2026-01-20
Now integrates with live bot components for accurate parity testing.
"""

import asyncio
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

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

logger = logging.getLogger(__name__)


async def main():
    print("=" * 80)
    print("BACKTESTING WITH PARITY-ALIGNED ENGINE")
    print("=" * 80)
    
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
    # ✅ Now uses YES/NO prices matching Kalshi format
    historical_data = {}
    
    # NEW: Warmup and Inefficiency settings
    WARMUP_POINTS = 30
    INEFFICIENCY_EDGE = 0.10  # 10% edge to trigger MispricingStrategy (min 8%)

    for market_id, points in raw_data.items():
        # Generate warmup data (flat price before start)
        first_point = points[0]
        start_ts = datetime.fromisoformat(first_point['timestamp'])
        start_price = first_point['price']
        
        full_points = []
        for i in range(WARMUP_POINTS):
            ts = start_ts - timedelta(minutes=WARMUP_POINTS - i)
            full_points.append({
                'timestamp': ts.isoformat(),
                'price': start_price,
                'volume': 10000,
                'liquidity': 1000.0
            })
        full_points.extend(points)

        historical_data[market_id] = [
            HistoricalPricePoint(
                timestamp=datetime.fromisoformat(p['timestamp']),
                yes_price=p['price'],  # YES price
                # Simulate inefficiency: NO price = 1 - YES - EDGE
                # This creates an arbitrage opportunity (Sum < 1.0)
                no_price=max(0.01, 1.0 - p['price'] - INEFFICIENCY_EDGE),
                liquidity_usd=p.get('liquidity', 1000.0),
                bid=p['price'] * 0.99,
                ask=p['price'] * 1.01,
                volume_24h=p.get('volume', 10000),
                expiry_timestamp=datetime.fromisoformat(p['timestamp']) + timedelta(days=7),
            )
            for p in full_points
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
    
    # Initialize live bot components (PARITY: Reuse from live bot)
    print(f"\n🔗 Initializing live bot components...")
    live_config = Config(platform="kalshi")
    # Manually set targets for StrategyManager to pick up
    live_config.TARGET_PROFIT_USD = 30.0
    live_config.TARGET_LOSS_USD = -15.0
    
    # Enable Momentum Strategy for backtest
    live_config.ENABLE_MOMENTUM_STRATEGY = True
    live_config.MOMENTUM_WINDOW = 6
    live_config.MOMENTUM_THRESHOLD = 0.03
    
    # Enable Volume Strategy for backtest
    live_config.ENABLE_VOLUME_STRATEGY = True
    live_config.VOLUME_SPIKE_THRESHOLD = 3.0
    live_config.MIN_VOLUME_FOR_STRATEGY = 100
    
    strategy_manager = StrategyManager(config=live_config)
    risk_manager = RiskManager(client=None, config=live_config)
    fee_calculator = FeeCalculator()
    market_filter = MarketFilter(config=live_config)
    
    print(f"   ✅ StrategyManager initialized")
    print(f"   ✅ RiskManager initialized")
    print(f"   ✅ FeeCalculator initialized")
    print(f"   ✅ MarketFilter initialized")
    
    # ✅ NEW: Backtest configuration aligned with live bot
    # Key differences from old config:
    # - TRADE_UNIT (fixed): 100 contracts instead of percentage-based
    # - TARGET_PROFIT_USD / TARGET_LOSS_USD (USD): instead of percentage
    # - Market filtering parameters: spread, expiry, liquidity, depth
    # - Risk management parameters: daily loss limit
    backtest_config = BacktestConfig(
        # Account
        starting_balance=10000.0,
        
        # Position sizing (FIXED, not percentage)
        TRADE_UNIT=500,  # Increased to 500 to overcome fees and hit targets easier
        MAX_CONCURRENT_TRADES=3,  # From live bot
        
        # Spike detection (Increased to filter noise)
        SPIKE_THRESHOLD=0.05,  # Lowered slightly to catch more valid moves
        
        # Exit targets (Wider stops, higher targets)
        TARGET_PROFIT_USD=40.00,  # Scaled up for larger position size
        TARGET_LOSS_USD=-5.00,   # Wider stop to prevent noise outs
        
        # Trailing Stop
        USE_TRAILING_STOP=True,
        TRAILING_STOP_ACTIVATION_USD=10.00,  # Lock in once we have $10 profit
        TRAILING_STOP_DISTANCE_USD=5.00,     # Give it $5.00 wiggle room
        
        # Slippage tolerance
        MAX_SLIPPAGE_TOLERANCE=0.025,
        
        # Market filtering (comprehensive quality checks)
        MIN_LIQUIDITY_USD=500.0,        # Minimum liquidity
        MAX_SPREAD_PCT=0.30,            # Maximum 30% spread
        MIN_PRICE_HISTORY=20,           # Minimum 20 data points
        MAX_SUSPICIOUS_SPIKE_PCT=0.30,  # Reject spikes > 30%
        MIN_TIME_TO_EXPIRY_HOURS=0.5,   # Exit if < 30 min to expiry
        
        # Risk management
        MAX_DAILY_LOSS_PCT=0.15,  # 15% daily loss limit ($1,500 on $10k)
        MAX_EVENT_EXPOSURE_USD=600.0, # Limit exposure (allows 1 trade of 500@0.65, blocks 2nd)
    )
    
    print(f"\n💰 Backtest Config (Parity-Aligned):")
    print(f"   Starting Balance: ${backtest_config.starting_balance:,.2f}")
    print(f"   Trade Unit: {backtest_config.TRADE_UNIT} contracts (FIXED)")
    print(f"   Max Concurrent: {backtest_config.MAX_CONCURRENT_TRADES} positions")
    print(f"   Spike Threshold: {backtest_config.SPIKE_THRESHOLD:.1%}")
    print(f"   Target Profit: ${backtest_config.TARGET_PROFIT_USD:.2f} (USD)")
    print(f"   Target Loss: ${backtest_config.TARGET_LOSS_USD:.2f} (USD)")
    print(f"   Min Liquidity: ${backtest_config.MIN_LIQUIDITY_USD:,.0f}")
    print(f"   Trailing Stop: {backtest_config.USE_TRAILING_STOP} (Activate: ${backtest_config.TRAILING_STOP_ACTIVATION_USD}, Dist: ${backtest_config.TRAILING_STOP_DISTANCE_USD})")
    print(f"   Max Spread: {backtest_config.MAX_SPREAD_PCT:.1%}")
    print(f"   Daily Loss Limit: {backtest_config.MAX_DAILY_LOSS_PCT:.1%}")
    
    # ✅ Create engine with live bot components
    engine = BacktestEngine(
        strategy_manager=strategy_manager,
        risk_manager=risk_manager,
        fee_calculator=fee_calculator,
        market_filter=market_filter,
        config=backtest_config,
    )
    
    print(f"\n🚀 Running backtest (parity-aligned)...")
    results = await engine.run_backtest(
        historical_data=historical_data,
        start_date=start_date,
        end_date=end_date,
    )
    
    # Print detailed results
    print(f"\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    
    print(f"\n📊 Performance Metrics:")
    print(f"   Final Balance: ${results.final_balance:,.2f}")
    print(f"   Total Return: ${results.total_return_usd:+,.2f} ({results.total_return_pct:+.2f}%)")
    print(f"   Total P&L: ${results.total_pnl:+,.2f}")
    print(f"   Total Fees: ${results.total_fees_paid:,.2f}")
    
    print(f"\n📈 Trade Statistics:")
    print(f"   Total Trades: {results.total_trades}")
    print(f"   Winning Trades: {results.winning_trades}")
    print(f"   Losing Trades: {results.losing_trades}")
    print(f"   Win Rate: {results.win_rate:.1f}%")
    print(f"   Max Drawdown: ${results.max_drawdown:,.2f} ({results.max_drawdown_pct:.2f}%)")
    
    print(f"\n🎯 Signal Statistics:")
    print(f"   Signals Evaluated: {results.signals_evaluated}")
    print(f"   Signals Accepted: {results.signals_accepted}")
    print(f"   Signals Rejected: {results.signals_rejected}")
    
    if results.signals_evaluated > 0:
        acceptance_rate = (results.signals_accepted / results.signals_evaluated) * 100
        print(f"   Acceptance Rate: {acceptance_rate:.1f}%")
    
    # Print rejection reasons
    if results.rejection_reasons:
        print(f"\n❌ Rejection Reasons (Top 5):")
        sorted_reasons = sorted(
            results.rejection_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for reason, count in sorted_reasons[:5]:
            pct = (count / results.signals_rejected) * 100 if results.signals_rejected > 0 else 0
            print(f"   {reason}: {count} ({pct:.1f}%)")
    
    # Daily P&L breakdown
    if results.daily_pnl:
        print(f"\n📅 Daily P&L:")
        for date, pnl in sorted(results.daily_pnl.items()):
            print(f"   {date}: ${pnl:+,.2f}")
    
    # Trade log (top trades)
    if results.trades:
        print(f"\n📋 Trade Log (First 10 trades):")
        print(f"   {'Market':<20} {'Side':<6} {'Entry':<8} {'Exit':<8} {'P&L':<10} {'Strategy':<15} {'Reason':<20}")
        print(f"   {'-'*95}")
        
        for i, trade in enumerate(results.trades[:10]):
            side = trade.side.value if hasattr(trade.side, 'value') else str(trade.side)
            entry = f"${trade.entry_price:.4f}"
            exit_price = f"${trade.exit_price:.4f}" if trade.exit_price else "—"
            pnl = f"${trade.pnl:+.2f}"
            strategy = trade.metadata.get('strategy', 'unknown')[:15]
            reason = trade.exit_reason or "open"
            
            print(f"   {trade.market_id:<20} {side:<6} {entry:<8} {exit_price:<8} {pnl:<10} {strategy:<15} {reason:<20}")
        
        if len(results.trades) > 10:
            print(f"   ... and {len(results.trades) - 10} more trades")
    
    # Save results to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"backtest_results_{timestamp}.json"
    
    # Convert results to serializable format
    results_dict = {
        "timestamp": timestamp,
        "final_balance": results.final_balance,
        "starting_balance": results.starting_balance,
        "total_return_usd": results.total_return_usd,
        "total_return_pct": results.total_return_pct,
        "total_pnl": results.total_pnl,
        "total_fees_paid": results.total_fees_paid,
        "total_trades": results.total_trades,
        "winning_trades": results.winning_trades,
        "losing_trades": results.losing_trades,
        "win_rate": results.win_rate,
        "max_drawdown": results.max_drawdown,
        "max_drawdown_pct": results.max_drawdown_pct,
        "signals_evaluated": results.signals_evaluated,
        "signals_accepted": results.signals_accepted,
        "signals_rejected": results.signals_rejected,
        "rejection_reasons": results.rejection_reasons,
        "daily_pnl": results.daily_pnl,
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_dict, f, indent=2)
    
    print(f"\n✅ Results saved to: {results_file}")
    print(f"\n✅ Backtest complete using parity-aligned engine!")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())