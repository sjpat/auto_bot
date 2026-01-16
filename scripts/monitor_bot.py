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
from src.trading.spike_detector import SpikeDetector
from src.trading.market_filter import MarketFilter


class BotMonitor:
    """Monitor bot performance and opportunities."""
    
    def __init__(self):
        self.config = Config()
        self.client = KalshiClient(self.config)
        self.spike_detector = SpikeDetector(self.config)
        self.market_filter = MarketFilter(self.config)
        
        self.stats = {
            'start_time': datetime.now(),
            'markets_monitored': 0,
            'spikes_detected': 0,
            'opportunities_found': 0,
            'last_spike_time': None
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
            
            # 4. Build price history for top markets
            print(f"\n📈 Building price history...")
            for market in tradeable[:10]:  # Top 10
                self.spike_detector.add_price(
                    market.market_id,
                    market.price,
                    datetime.now()
                )
            
            # 5. Detect spikes
            print(f"\n🔍 Detecting spikes...")
            spikes = self.spike_detector.detect_spikes(
                markets=tradeable[:10],
                threshold=self.config.SPIKE_THRESHOLD
            )
            
            if spikes:
                self.stats['spikes_detected'] += len(spikes)
                self.stats['last_spike_time'] = datetime.now()
                print(f"   🔔 FOUND {len(spikes)} SPIKE(S)!")
                
                for spike in spikes:
                    market = next(
                        (m for m in tradeable if m.market_id == spike.market_id),
                        None
                    )
                    print(f"\n   📊 Spike Details:")
                    print(f"      Market: {spike.market_id}")
                    print(f"      Change: {spike.change_pct:+.1%}")
                    print(f"      Current: ${spike.current_price:.4f}")
                    print(f"      Direction: {spike.direction}")
                    if market:
                        print(f"      Liquidity: ${market.liquidity_usd:.2f}")
                        print(f"      Expires in: {market.time_to_expiry_seconds/3600:.1f}h")
            else:
                print(f"   No spikes detected")
            
            # 6. Show top opportunities
            print(f"\n🎯 Top Opportunities:")
            ranked = self.market_filter.rank_markets_by_opportunity(
                tradeable[:20],
                self.spike_detector
            )
            
            for i, market in enumerate(ranked[:5], 1):
                history_len = len(
                    self.spike_detector.price_history.get(market.market_id, [])
                )
                print(f"   {i}. {market.market_id[:30]}...")
                print(f"      Price: ${market.price:.4f} | "
                      f"Liquidity: ${market.liquidity_usd:.2f} | "
                      f"History: {history_len} points | "
                      f"Expires: {market.time_to_expiry_seconds/3600:.1f}h")
            
            # 7. Show stats
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
        print(f"   Spikes detected: {self.stats['spikes_detected']}")
        
        if self.stats['last_spike_time']:
            time_since = (datetime.now() - self.stats['last_spike_time']).total_seconds()
            print(f"   Last spike: {time_since/60:.1f} minutes ago")
        else:
            print(f"   Last spike: Never")


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
        # ✅ Close session when monitoring stops completely
        await monitor.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
