"""
Real-time spike monitoring script.
Continuously monitors tradeable markets and alerts on spikes.
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
    
    print("=" * 60)
    print("SPIKE MONITORING - STARTING")
    print(f"Threshold: {config.SPIKE_THRESHOLD * 100}%")
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
                min_volume=100
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
            
            # Detect spikes
            spikes = spike_detector.detect_spikes(
                markets=markets,
                threshold=config.SPIKE_THRESHOLD
            )
            
            if spikes:
                print(f"\n🚨 SPIKES DETECTED: {len(spikes)}")
                for spike in spikes:
                    print(f"  Market: {spike.market_id}")
                    print(f"  Direction: {spike.direction}")
                    print(f"  Change: {spike.change_pct:.2%}")
                    print(f"  Current: ${spike.current_price:.4f}")
                    print(f"  Previous: ${spike.previous_price:.4f}")
                    print()
            else:
                # Show some market stats
                prices = [m.price for m in markets[:5]]
                print(f"  Sample prices: {[f'${p:.4f}' for p in prices]}")
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
