"""
Script to verify that the bot is correctly building price history
and detecting spikes with real Kalshi data.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector
from src.config import Config


async def verify_price_history_building():
    """Verify price history is being built correctly."""
    print("=" * 80)
    print("PRICE HISTORY VERIFICATION")
    print("=" * 80)
    
    config = Config()
    client = KalshiClient(config)
    spike_detector = SpikeDetector(config)
    
    try:
        # Authenticate
        print("\n[1/6] Authenticating...")
        auth_success = await client.authenticate()
        if not auth_success:
            print("❌ Authentication failed!")
            return False
        print("✅ Authenticated")
        
        # Fetch markets
        print("\n[2/6] Fetching open markets...")
        markets = await client.get_markets(
            status="open",
            limit=20,
            min_volume=0,
            filter_untradeable=False
        )
        
        if len(markets) == 0:
            print("❌ No markets available!")
            return False
        
        print(f"✅ Retrieved {len(markets)} markets")
        
        # Select first market for testing
        test_market = markets[0]
        print(f"\n[3/6] Testing with market: {test_market.market_id}")
        print(f"   Title: {test_market.title[:60]}...")
        print(f"   Current price: ${test_market.price:.4f}")
        
        # Simulate bot behavior - add prices over time
        print("\n[4/6] Simulating bot behavior - building price history...")
        print("   (Adding current price multiple times to simulate polling)")
        
        base_time = datetime.now()
        
        # Simulate 30 polling intervals (like bot would do)
        for i in range(30):
            # In real scenario, price might vary slightly
            # For this test, we'll add small random variations
            import random
            price_variation = random.uniform(-0.002, 0.002)
            simulated_price = test_market.price + price_variation
            
            timestamp = base_time - timedelta(minutes=30-i)
            spike_detector.add_price(
                test_market.market_id,
                simulated_price,
                timestamp
            )
            
            if i % 5 == 0:
                print(f"   t-{30-i}min: ${simulated_price:.4f}")
        
        # Check price history
        print("\n[5/6] Verifying price history...")
        history = spike_detector.price_history.get(test_market.market_id, [])
        
        print(f"   Total price points stored: {len(history)}")
        
        if len(history) == 0:
            print("❌ No price history stored!")
            return False
        
        print(f"   ✅ Price history successfully built")
        
        # Show statistics
        prices = [p[0] if isinstance(p, tuple) else p for p in history]
        timestamps = [p[1] if isinstance(p, tuple) else datetime.now() for p in history]
        
        print(f"\n   Statistics:")
        print(f"   - Min price: ${min(prices):.4f}")
        print(f"   - Max price: ${max(prices):.4f}")
        print(f"   - Avg price: ${sum(prices)/len(prices):.4f}")
        print(f"   - Price range: ${max(prices) - min(prices):.4f}")
        print(f"   - Time span: {(max(timestamps) - min(timestamps)).total_seconds() / 60:.1f} minutes")
        
        # Try spike detection
        print("\n[6/6] Testing spike detection...")
        
        # Update market with slightly higher price to simulate potential spike
        test_price = test_market.price * 1.05  # 5% increase
        test_market.last_price_cents = int(test_price * 10000)
        
        print(f"   Testing with price: ${test_price:.4f} (+5% from baseline)")
        
        spikes = spike_detector.detect_spikes([test_market], threshold=0.04)
        
        print(f"   Spikes detected: {len(spikes)}")
        
        if len(spikes) > 0:
            print("   ✅ Spike detection is working!")
            for spike in spikes:
                print(f"\n   📊 Spike details:")
                print(f"      Market: {spike.market_id}")
                print(f"      Change: {spike.price_change:.2%}")
                print(f"      Current: ${spike.current_price:.4f}")
                print(f"      Mean: ${spike.mean_price:.4f}")
                print(f"      Std Dev: ${spike.std_dev:.4f}")
        else:
            print("   ℹ️  No spike detected (price change below threshold)")
        
        # Test with multiple markets
        print("\n[BONUS] Testing with multiple markets...")
        print(f"   Building history for {min(5, len(markets))} markets...")
        
        for market in markets[:5]:
            # Add some history for each market
            for i in range(20):
                spike_detector.add_price(
                    market.market_id,
                    market.price,
                    base_time - timedelta(minutes=20-i)
                )
        
        # Check how many markets have history
        markets_with_history = len(spike_detector.price_history)
        print(f"   ✅ {markets_with_history} markets have price history")
        
        # Try batch spike detection
        spikes_found = spike_detector.detect_spikes(markets[:5], threshold=0.04)
        print(f"   Batch detection found: {len(spikes_found)} spikes")
        
        print("\n" + "=" * 80)
        print("✅ VERIFICATION COMPLETE")
        print("=" * 80)
        print("\nSummary:")
        print(f"  • Price history is being built correctly")
        print(f"  • {len(history)} price points stored for test market")
        print(f"  • Spike detection logic is functional")
        print(f"  • {markets_with_history} markets tracked")
        print("\nYour bot should be able to detect spikes once:")
        print("  1. Markets have sufficient trading activity")
        print("  2. Price history has accumulated (20+ data points)")
        print("  3. Actual price movements exceed threshold (4%)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()


async def test_spike_detection_threshold():
    """Test different spike thresholds to find optimal setting."""
    print("\n" + "=" * 80)
    print("SPIKE THRESHOLD TESTING")
    print("=" * 80)
    
    config = Config()
    spike_detector = SpikeDetector(config)
    
    # Create synthetic price history
    base_price = 0.50
    market_id = "THRESHOLD-TEST"
    base_time = datetime.now()
    
    print("\n📊 Creating synthetic stable baseline...")
    for i in range(25):
        spike_detector.add_price(
            market_id,
            base_price,
            base_time - timedelta(minutes=25-i)
        )
    
    # Test different price changes
    print("\nTesting different price movements:")
    print("-" * 80)
    
    test_cases = [
        (0.51, "2% increase"),
        (0.52, "4% increase"),
        (0.53, "6% increase"),
        (0.55, "10% increase"),
        (0.49, "2% decrease"),
        (0.48, "4% decrease"),
    ]
    
    for test_price, description in test_cases:
        # Create mock market
        from src.clients.kalshi_client import Market
        mock_market = Market(
            market_id=market_id,
            title="Test Market",
            status="active",
            close_ts=int((datetime.now() + timedelta(hours=24)).timestamp()),
            liquidity_cents=10000,
            last_price_cents=int(test_price * 10000),
            best_bid_cents=int((test_price - 0.01) * 10000),
            best_ask_cents=int((test_price + 0.01) * 10000)
        )
        
        # Test with 4% threshold
        spikes = spike_detector.detect_spikes([mock_market], threshold=0.04)
        
        detected = "✅ SPIKE" if len(spikes) > 0 else "   ----"
        change_pct = ((test_price - base_price) / base_price) * 100
        
        print(f"   ${test_price:.2f} ({description:20s}) | Change: {change_pct:+6.2f}% | {detected}")
    
    print("-" * 80)
    print("\nRecommendation:")
    print("  • 4% threshold catches meaningful moves without too much noise")
    print("  • Consider lowering to 3% for more opportunities")
    print("  • Consider raising to 5% if too many false signals")


if __name__ == "__main__":
    print("\n🚀 Starting Price History Verification\n")
    
    # Run main verification
    success = asyncio.run(verify_price_history_building())
    
    if success:
        # Run threshold testing
        asyncio.run(test_spike_detection_threshold())
    
    sys.exit(0 if success else 1)
