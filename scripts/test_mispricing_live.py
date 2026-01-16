"""
Test mispricing detector with live Kalshi data.
Run this to see what opportunities exist right now.
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.strategies.mispricing_strategy import MispricingStrategy
from src.trading.market_filter import MarketFilter


async def test_mispricing_live():
    """Run mispricing detector on live markets."""
    print("="*80)
    print("MISPRICING DETECTOR - LIVE TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Initialize
    config = Config()
    client = KalshiClient(config)
    strategy = MispricingStrategy({
        'MIN_EDGE': 0.08,  # 8% minimum edge
        'MIN_CONFIDENCE': 0.6,
        'MAX_HOLDING_TIME': 3600 * 4,
        'HISTORY_SIZE': 50
    })
    market_filter = MarketFilter(config)
    
    try:
        # Authenticate
        await client.authenticate()
        print("✅ Connected to Kalshi\n")
        
        # Fetch markets
        print("📊 Fetching markets...")
        markets = await client.get_markets(
            status="open",
            limit=200,
            filter_untradeable=True
        )
        print(f"   Found {len(markets)} markets\n")
        
        # Filter tradeable
        tradeable = market_filter.filter_tradeable_markets(markets)
        print(f"   {len(tradeable)} tradeable markets\n")
        
        # Build some price history (simulate multiple checks)
        print("📈 Building price history (3 samples)...")
        for i in range(3):
            for market in tradeable[:50]:  # Top 50 markets
                strategy.on_market_update(market)
            if i < 2:
                await asyncio.sleep(2)  # Wait 2 seconds between samples
        print("   Done\n")
        
        # Detect mispricings
        print("🔍 Detecting mispricings...\n")
        signals = strategy.generate_entry_signals(tradeable[:50])
        
        if signals:
            print(f"💰 FOUND {len(signals)} MISPRICING OPPORTUNITIES!\n")
            
            for i, signal in enumerate(signals, 1):
                market = next((m for m in tradeable if m.market_id == signal.market_id), None)
                
                print(f"--- Opportunity #{i} ---")
                print(f"Market: {signal.market_id}")
                if market:
                    print(f"Title: {market.title[:60]}...")
                print(f"Direction: {signal.signal_type.value.upper()}")
                print(f"Edge: {signal.metadata['edge']:.1%}")
                print(f"Fair Value: {signal.metadata['fair_value']:.1%}")
                print(f"Market Price: {signal.metadata['market_price']:.1%}")
                print(f"Confidence: {signal.confidence:.1%}")
                print(f"Method: {signal.metadata['pricing_method']}")
                
                if market:
                    print(f"Liquidity: ${market.liquidity_usd:.2f}")
                    print(f"Expires: {market.time_to_expiry_seconds/3600:.1f}h")
                
                print()
        else:
            print("   No mispricings detected with current thresholds")
            print("   Try lowering MIN_EDGE or MIN_CONFIDENCE")
        
        # Show statistics
        print("\n📊 Strategy Statistics:")
        stats = strategy.get_statistics()
        for key, value in stats.items():
            print(f"   {key}: {value}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_mispricing_live())
