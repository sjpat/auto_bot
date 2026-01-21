"""
Real-time monitoring dashboard for trading bot.
Shows: positions, opportunities, performance stats.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.market_filter import MarketFilter
from src.strategies.strategy_manager import StrategyManager  # ✅ NEW

class BotMonitor:
    """Monitor bot performance and opportunities."""
    
    def __init__(self):
        self.config = Config()
        self.client = KalshiClient(self.config)
        self.strategy_manager = StrategyManager(self.config)  # ✅ Already correct
        self.market_filter = MarketFilter(self.config)
        
        self.stats = {
            'start_time': datetime.now(),
            'markets_monitored': 0,
            'opportunities_detected': 0,  # ✅ Renamed from spikes_detected
            'last_opportunity_time': None  # ✅ Renamed
        }
    
    async def run_monitoring_cycle(self):
        """Run one monitoring cycle."""
        print("\n" + "="*80)
        print(f"BOT MONITORING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        try:
            # 1. Check authentication
            auth = await self.client.authenticate()
            balance = await self.client.get_balance()
            print(f"\n✅ Connected | Balance: ${balance:.2f}")
            
            # 2. Fetch markets
            print(f"\n📊 Fetching markets...")
            all_markets = await self.client.get_markets(
                status="open",
                limit=200,
                min_volume=0,
                filter_untradeable=False
            )
            
            self.stats['markets_monitored'] = len(all_markets)
            print(f"   Total markets: {len(all_markets)}")
            
            # 3. Apply filtering
            tradeable = self.market_filter.filter_tradeable_markets(all_markets)
            print(f"   Tradeable markets: {len(tradeable)}")
            
            # 4. Update price history for all strategies
            print(f"\n📈 Building price history...")
            for market in tradeable[:20]:  # Top 20
                self.strategy_manager.on_market_update(market)  # ✅ FIXED
            
            # 5. Detect opportunities from ALL strategies
            print(f"\n🔍 Detecting opportunities (All Strategies)...")
            signals = self.strategy_manager.generate_entry_signals(tradeable[:20])
            
            if signals:
                self.stats['opportunities_detected'] += len(signals)
                self.stats['last_opportunity_time'] = datetime.now()
                print(f"   🔔 FOUND {len(signals)} OPPORTUNITY(IES)!")
                
                for i, signal in enumerate(signals, 1):
                    market = next(
                        (m for m in tradeable if m.market_id == signal.market_id),
                        None
                    )
                    strategy_name = signal.metadata.get('strategy', 'unknown')
                    
                    print(f"\n   --- Opportunity #{i} ---")
                    print(f"   Strategy: {strategy_name.upper()}")
                    print(f"   Market: {signal.market_id[:40]}...")
                    print(f"   Direction: {signal.signal_type.value.upper()}")
                    print(f"   Confidence: {signal.confidence:.1%}")
                    
                    if 'edge' in signal.metadata:
                        print(f"   Edge: {signal.metadata['edge']:.1%}")
                    if 'pricing_method' in signal.metadata:
                        print(f"   Method: {signal.metadata['pricing_method']}")
                    
                    if market:
                        print(f"   Price: ${market.price:.4f}")
                        print(f"   Liquidity: ${market.liquidity_usd:.2f}")
                        print(f"   Expires: {market.time_to_expiry_seconds/3600:.1f}h")
            else:
                print(f"   No opportunities detected by any strategy")
            
            # 6. Show stats
            self._print_stats()
            
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
            import traceback
            traceback.print_exc()
    
    async def cleanup(self):
        """Clean up resources when monitoring stops."""
        await self.client.close()
        print("\n🧹 Cleaned up resources")
    
    def _print_stats(self):
        """Print session statistics."""
        print(f"\n📊 Session Stats:")
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        print(f"   Uptime: {uptime/60:.1f} minutes")
        print(f"   Markets monitored: {self.stats['markets_monitored']}")
        print(f"   Opportunities detected: {self.stats['opportunities_detected']}")
        
        if self.stats['last_opportunity_time']:
            time_since = (datetime.now() - self.stats['last_opportunity_time']).total_seconds()
            print(f"   Last opportunity: {time_since/60:.1f} minutes ago")
        else:
            print(f"   Last opportunity: Never")

async def main():
    """Run monitoring in loop."""
    monitor = BotMonitor()
    
    print("🚀 Starting Bot Monitor...")
    print("Press Ctrl+C to stop")
    
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n\n{'='*80}")
            print(f"MONITORING CYCLE #{cycle}")
            print('='*80)
            
            await monitor.run_monitoring_cycle()
            
            # Wait before next cycle
            wait_time = 60  # 1 minute
            print(f"\n⏳ Waiting {wait_time}s until next check...")
            await asyncio.sleep(wait_time)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Monitoring stopped by user")
    finally:
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
