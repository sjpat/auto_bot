"""
Monitor markets that have enough time to build history.
Only track markets closing in 2+ hours.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


async def main():
    config = Config()
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    stable_markets: Set[str] = set()
    market_details = {}
    
    print("=" * 80)
    print("LONG-LIVED MARKET MONITORING")
    print("Only tracking markets that close in 2+ hours")
    print("=" * 80)
    
    try:
        await client.authenticate()
        balance = await client.get_balance()
        print(f"Account Balance: ${balance:.2f}\n")
        
        # Find markets with long time horizons
        print("🔍 Finding long-lived markets...")
        all_markets = await client.get_markets(
            status="open",
            limit=200,
            min_volume=100,
            filter_untradeable=False
        )
        
        now = datetime.now().timestamp()
        
        # Filter for markets closing in 2+ hours
        long_lived_markets = [
            m for m in all_markets
            if (m.close_ts - now) > 7200  # 2 hours = 7200 seconds
        ]
        
        print(f"   Total markets: {len(all_markets)}")
        print(f"   Long-lived (2+ hours): {len(long_lived_markets)}")
        
        if len(long_lived_markets) == 0:
            print("\n❌ No long-lived markets found!")
            print("   All markets close within 2 hours.")
            print("\n   RECOMMENDATION:")
            print("   1. Try lowering threshold to 1 hour (3600 seconds)")
            print("   2. Or use a different time of day when more markets are available")
            print("   3. Or check if you need to use production API instead of demo")
            return
        
        # Sort by combination of: time until close + volume
        long_lived_markets.sort(
            key=lambda m: (m.close_ts - now) + (m.liquidity_usd * 100),
            reverse=True
        )
        
        # Select top 15 markets
        selected_count = min(15, len(long_lived_markets))
        
        for market in long_lived_markets[:selected_count]:
            stable_markets.add(market.market_id)
            hours_until_close = (market.close_ts - now) / 3600
            market_details[market.market_id] = {
                'title': market.title,
                'initial_price': market.price,
                'close_ts': market.close_ts,
                'hours_until_close': hours_until_close,
                'volume': market.liquidity_usd
            }
        
        print(f"\n✅ Locked onto {len(stable_markets)} markets\n")
        print("TRACKED MARKETS:")
        print("-" * 80)
        print(f"{'#':<3} {'Time to Close':<14} {'Volume':<10} {'Price':<10}")
        print("-" * 80)
        
        for i, market_id in enumerate(list(stable_markets)[:10], 1):
            details = market_details[market_id]
            hours = details['hours_until_close']
            vol = details['volume']
            price = details['initial_price']
            
            time_str = f"{hours:.1f}h" if hours < 24 else f"{hours/24:.1f}d"
            vol_str = f"${vol:.2f}" if vol > 0 else "$0"
            
            print(f"{i:<3} {time_str:<14} {vol_str:<10} ${price:.4f}")
            print(f"    {market_id[:70]}")
        
        if len(stable_markets) > 10:
            print(f"... and {len(stable_markets) - 10} more")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'=' * 80}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{iteration}")
            print("=" * 80)
            
            # Fetch ALL markets
            all_markets = await client.get_markets(
                status="open",
                limit=300,
                min_volume=0,
                filter_untradeable=False
            )
            
            # Filter to only our stable markets
            current_markets = {
                m.market_id: m 
                for m in all_markets 
                if m.market_id in stable_markets
            }
            
            print(f"\n📊 MONITORING STATUS")
            print("-" * 80)
            print(f"   Stable markets tracked: {len(stable_markets)}")
            print(f"   Markets currently available: {len(current_markets)}/{len(stable_markets)}")
            
            # Check which markets are missing
            missing = stable_markets - set(current_markets.keys())
            if missing:
                print(f"   ⚠️  Markets not found: {len(missing)}")
                
                # Check if they closed
                now = datetime.now().timestamp()
                for mid in list(missing)[:3]:
                    if mid in market_details:
                        close_ts = market_details[mid]['close_ts']
                        if close_ts < now:
                            print(f"      - {mid[:50]}... (CLOSED)")
                        else:
                            hours_left = (close_ts - now) / 3600
                            print(f"      - {mid[:50]}... ({hours_left:.1f}h remaining)")
            
            # Add prices for available markets
            added_count = 0
            for market_id, market in current_markets.items():
                spike_detector.add_price(
                    market_id=market_id,
                    price=market.price,
                    timestamp=datetime.now()
                )
                added_count += 1
            
            print(f"   ✅ Prices added: {added_count}")
            
            # Show history depth
            print(f"\n📈 PRICE HISTORY")
            print("-" * 80)
            
            markets_ready = 0
            markets_building = 0
            
            for market_id in stable_markets:
                history_depth = len(spike_detector.price_history.get(market_id, []))
                
                if history_depth >= 20:
                    markets_ready += 1
                elif history_depth > 0:
                    markets_building += 1
            
            print(f"   Ready (20+ points): {markets_ready}")
            print(f"   Building (1-19 points): {markets_building}")
            print(f"   Not started: {len(stable_markets) - markets_ready - markets_building}")
            
            # Show detailed status
            print(f"\n   Detailed Status (first 5 markets):")
            for i, market_id in enumerate(list(stable_markets)[:5], 1):
                history_depth = len(spike_detector.price_history.get(market_id, []))
                status = "✅" if history_depth >= 20 else f"⏳{history_depth}"
                
                if market_id in current_markets:
                    price = current_markets[market_id].price
                    print(f"   {i}. {market_id[:40]}... [{status:>4}] ${price:.4f}")
                else:
                    print(f"   {i}. {market_id[:40]}... [{status:>4}] ❌ UNAVAILABLE")
            
            # Detect spikes
            markets_for_detection = [
                m for m in current_markets.values()
                if len(spike_detector.price_history.get(m.market_id, [])) >= 20
            ]
            
            if markets_for_detection:
                spikes = spike_detector.detect_spikes(
                    markets=markets_for_detection,
                    threshold=config.SPIKE_THRESHOLD
                )
                
                if spikes:
                    print(f"\n🚨 SPIKES DETECTED: {len(spikes)}")
                    for spike in spikes:
                        print(f"  {spike.market_id[:50]}")
                        print(f"  {spike.change_pct:.2%}: ${spike.previous_price:.4f} -> ${spike.current_price:.4f}")
                else:
                    print(f"\n✓ No spikes (monitoring {len(markets_for_detection)} ready markets)")
            else:
                print(f"\n⏳ Building history... ({markets_building} markets in progress)")
                if markets_ready == 0 and iteration > 20:
                    print(f"   ⚠️  No markets ready after {iteration} checks - markets may be expiring")
            
            print(f"\n⏳ Waiting 60 seconds...")
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
