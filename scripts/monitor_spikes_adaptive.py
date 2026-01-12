"""
Spike monitoring with adaptive thresholds for low-probability markets.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


def get_adaptive_threshold(price: float, base_threshold: float = 0.04) -> float:
    """
    Calculate adaptive threshold based on market price.
    Low-probability markets (< 0.20) get lower thresholds.
    """
    if price < 0.10:  # Less than 10%
        return 0.02  # 2% threshold
    elif price < 0.20:  # Less than 20%
        return 0.03  # 3% threshold
    else:
        return base_threshold  # 4% threshold


async def main():
    config = Config()
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    print("=" * 60)
    print("ADAPTIVE SPIKE MONITORING - STARTING")
    print(f"Base Threshold: {config.SPIKE_THRESHOLD * 100}%")
    print("Low-prob markets (<10%): 2% threshold")
    print("Mid-prob markets (<20%): 3% threshold")
    print("=" * 60)
    
    try:
        await client.authenticate()
        balance = await client.get_balance()
        print(f"Account Balance: ${balance:.2f}\n")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Check #{iteration}")
            
            # Fetch tradeable markets
            markets = await client.get_markets(
                status="open",
                limit=50,
                min_volume=1
            )
            
            if len(markets) == 0:
                print("⚠️  No tradeable markets found. Waiting...")
                await asyncio.sleep(60)
                continue
            
            print(f"📊 Monitoring {len(markets)} markets")
            
            # Add current prices to history
            for market in markets:
                spike_detector.add_price(
                    market_id=market.market_id,
                    price=market.price,
                    timestamp=datetime.now()
                )
            
            # Check each market with adaptive threshold
            all_spikes = []
            for market in markets:
                # Get adaptive threshold based on price
                threshold = get_adaptive_threshold(market.price)
                
                # Detect spikes for this market
                spikes = spike_detector.detect_spikes(
                    markets=[market],
                    threshold=threshold
                )
                
                if spikes:
                    all_spikes.extend(spikes)
            
            if all_spikes:
                print(f"\n🚨 SPIKES DETECTED: {len(all_spikes)}")
                for spike in all_spikes:
                    threshold_used = get_adaptive_threshold(spike.previous_price)
                    print(f"  Market: {spike.market_id[:30]}...")
                    print(f"  Direction: {spike.direction}")
                    print(f"  Change: {spike.change_pct:.2%} (threshold: {threshold_used:.1%})")
                    print(f"  Current: ${spike.current_price:.4f}")
                    print(f"  Previous: ${spike.previous_price:.4f}")
                    
                    # Check history depth
                    if spike.market_id in spike_detector.price_history:
                        depth = len(spike_detector.price_history[spike.market_id])
                        print(f"  History depth: {depth} points")
                    print()
            else:
                # Show market stats with thresholds
                print(f"  Markets by probability:")
                low_prob = sum(1 for m in markets if m.price < 0.10)
                mid_prob = sum(1 for m in markets if 0.10 <= m.price < 0.20)
                high_prob = sum(1 for m in markets if m.price >= 0.20)
                print(f"    Low (<10%): {low_prob} markets (2% threshold)")
                print(f"    Mid (10-20%): {mid_prob} markets (3% threshold)")
                print(f"    High (>20%): {high_prob} markets (4% threshold)")
                
                # Sample prices
                prices = [m.price for m in markets[:5]]
                print(f"  Sample prices: {[f'${p:.4f}' for p in prices]}")
                
                # Show history depth for first few markets
                markets_with_history = [
                    (m.market_id, len(spike_detector.price_history.get(m.market_id, [])))
                    for m in markets[:3]
                ]
                print(f"  History depth: {[(mid[:20], depth) for mid, depth in markets_with_history]}")
                print(f"  No spikes detected")
            
            # Wait before next check
            print(f"  Waiting 60 seconds...")
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
