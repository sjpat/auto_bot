"""
Real-time spike monitoring script with detailed market information.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


async def main():
    config = Config(platform="kalshi")
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    print("=" * 80)
    print("SPIKE MONITORING - STARTING")
    print(f"Threshold: {config.SPIKE_THRESHOLD * 100}%")
    print("Monitoring ALL markets (min_volume=0)")
    print("=" * 80)
    
    try:
        await client.authenticate()
        balance = await client.get_balance()
        print(f"Account Balance: ${balance:.2f}")
        
        if balance == 0:
            print("⚠️  DETECTION-ONLY MODE (No funds for trading)\n")
        else:
            print(f"✅ LIVE TRADING MODE\n")
        
        iteration = 0
        tracked_markets = {}  # Keep track of markets we're monitoring
        
        while True:
            iteration += 1
            print(f"\n{'=' * 80}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{iteration}")
            print("=" * 80)
            
            # Fetch markets
            markets = await client.get_markets(
                status="open",
                limit=50,
                min_volume=0,
                filter_untradeable=True
            )
            
            if len(markets) == 0:
                print("⚠️  No markets available. Waiting...")
                await asyncio.sleep(60)
                continue
            
            # Update tracked markets
            for market in markets:
                if market.market_id not in tracked_markets:
                    tracked_markets[market.market_id] = {
                        'title': market.title,
                        'first_seen': datetime.now(),
                        'checks': 0
                    }
                tracked_markets[market.market_id]['checks'] += 1
                tracked_markets[market.market_id]['last_price'] = market.price
            
            print(f"\n📊 MONITORING {len(markets)} MARKETS")
            print("-" * 80)
            
            # Show detailed market list
            print(f"\n{'#':<3} {'Ticker':<45} {'Price':<10} {'Vol':<8} {'Hist':<6}")
            print("-" * 80)
            
            for i, market in enumerate(markets[:10], 1):  # Show first 10
                history_depth = len(spike_detector.price_history.get(market.market_id, []))
                vol_str = f"${market.liquidity_usd:.2f}" if market.liquidity_usd > 0 else "$0"
                
                # Truncate ticker if too long
                ticker = market.market_id[:43] + "..." if len(market.market_id) > 43 else market.market_id
                
                print(f"{i:<3} {ticker:<45} ${market.price:<9.4f} {vol_str:<8} {history_depth:<6}")
            
            if len(markets) > 10:
                print(f"... and {len(markets) - 10} more markets")
            
            # Statistics
            print(f"\n📈 STATISTICS")
            print("-" * 80)
            markets_with_volume = sum(1 for m in markets if m.liquidity_usd > 0)
            print(f"   Markets with volume: {markets_with_volume}/{len(markets)}")
            
            markets_ready = sum(
                1 for mid in spike_detector.price_history 
                if len(spike_detector.price_history[mid]) >= 20
            )
            total_tracked = len(spike_detector.price_history)
            print(f"   Markets ready for spike detection: {markets_ready}/{total_tracked}")
            print(f"   Total unique markets seen: {len(tracked_markets)}")
            
            # Add current prices to history
            for market in markets:
                spike_detector.add_price(
                    market_id=market.market_id,
                    price=market.price,
                    timestamp=datetime.now()
                )
            
            # Detect spikes
            spikes = spike_detector.detect_spikes(
                markets=markets,
                threshold=config.SPIKE_THRESHOLD
            )
            
            if spikes:
                print(f"\n🚨 SPIKES DETECTED: {len(spikes)}")
                print("=" * 80)
                for i, spike in enumerate(spikes, 1):
                    # Find the market details
                    market = next((m for m in markets if m.market_id == spike.market_id), None)
                    
                    print(f"\nSPIKE #{i}:")
                    print(f"  Ticker: {spike.market_id}")
                    if market:
                        print(f"  Title: {market.title[:70]}")
                        print(f"  Volume: ${market.liquidity_usd:.2f}")
                    print(f"  Direction: {spike.direction.upper()}")
                    print(f"  Change: {spike.change_pct:.2%} (threshold: {config.SPIKE_THRESHOLD:.1%})")
                    print(f"  Previous price: ${spike.previous_price:.4f}")
                    print(f"  Current price: ${spike.current_price:.4f}")
                    
                    # Show history depth
                    history_depth = len(spike_detector.price_history.get(spike.market_id, []))
                    print(f"  History depth: {history_depth} data points")
                    
                    # Show if this is a tracked market
                    if spike.market_id in tracked_markets:
                        checks = tracked_markets[spike.market_id]['checks']
                        print(f"  Monitoring duration: {checks} checks")
            else:
                print(f"\n✓ No spikes detected")
            
            # Show price changes for markets with sufficient history
            markets_with_history = [
                m for m in markets 
                if len(spike_detector.price_history.get(m.market_id, [])) >= 20
            ]
            
            if markets_with_history and not spikes:
                print(f"\n📊 PRICE CHANGES (markets with 20+ history):")
                print("-" * 80)
                print(f"{'Ticker':<45} {'Change':<10} {'Current':<10}")
                print("-" * 80)
                
                for market in markets_with_history[:5]:
                    history = spike_detector.price_history[market.market_id]
                    prices = [p[0] if isinstance(p, tuple) else p for p in history]
                    avg_price = sum(prices) / len(prices)
                    change = (market.price - avg_price) / avg_price if avg_price > 0 else 0
                    
                    ticker = market.market_id[:43] + "..." if len(market.market_id) > 43 else market.market_id
                    print(f"{ticker:<45} {change:>8.2%}  ${market.price:.4f}")
            
            # Wait before next check
            print(f"\n⏳ Waiting 60 seconds before next check...")
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
        
        # Show summary
        if tracked_markets:
            print("\n" + "=" * 80)
            print("SESSION SUMMARY")
            print("=" * 80)
            print(f"Total markets monitored: {len(tracked_markets)}")
            print(f"Markets with 20+ history: {markets_ready}")
            print(f"Total checks performed: {iteration}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
