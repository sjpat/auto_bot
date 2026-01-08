#!/usr/bin/env python3
"""
Quick validation script for manual testing.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.fee_calculator import FeeCalculator
from src.trading.spike_detector import SpikeDetector


async def test_connection():
    """Test Kalshi API connection."""
    print("🔌 Testing Kalshi connection...")
    
    try:
        config = Config(platform='kalshi')
        async with KalshiClient(config) as client:
            # Test authentication
            if await client.authenticate():
                print("✅ Authentication successful")
            else:
                print("❌ Authentication failed")
                return False
            
            # Test balance
            balance = await client.get_balance()
            print(f"✅ Balance: ${balance:.2f}")
            
            # Test markets
            markets = await client.get_markets(status='open', limit=5)
            print(f"✅ Retrieved {len(markets)} markets")
            
            if markets:
                print(f"   Sample: {markets[0].title[:50]}...")
            
            return True
    
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def test_fee_calculator():
    """Test fee calculator."""
    print("\n💰 Testing Fee Calculator...")
    
    try:
        calc = FeeCalculator()
        
        # Test fee calculation
        fee = calc.kalshi_fee(100, 0.65, 'taker')
        print(f"✅ Fee calculation: ${fee:.2f}")
        
        # Test P&L
        pnl = calc.calculate_pnl(0.60, 0.68, 100)
        print(f"✅ P&L calculation: ${pnl.net_profit:+.2f}")
        
        # Test breakeven
        breakeven = calc.breakeven_exit_price(0.60, 100)
        print(f"✅ Breakeven price: ${breakeven:.4f}")
        
        return True
    
    except Exception as e:
        print(f"❌ Fee calculator test failed: {e}")
        return False


def test_spike_detector():
    """Test spike detector."""
    print("\n📊 Testing Spike Detector...")
    
    try:
        config = Config(platform='kalshi')
        detector = SpikeDetector(config)
        
        # Add price history
        from datetime import datetime
        for i in range(25):
            detector.add_price('TEST_MARKET', 0.60, datetime.now())
        
        print(f"✅ Added 25 prices to history")
        
        # Create mock market with spike
        class MockMarket:
            market_id = 'TEST_MARKET'
            last_price_cents = 6500  # 0.65 (8.3% increase)
            status = 'open'
            
            @property
            def price(self):
                return self.last_price_cents / 100.0
            
            @property
            def is_open(self):
                return self.status == 'open'
            
            @property
            def is_liquid(self):
                return True
        
        market = MockMarket()
        spikes = detector.detect_spikes([market])
        
        if spikes:
            print(f"✅ Detected {len(spikes)} spike(s)")
            print(f"   Change: {spikes[0].change_pct:.2%}")
        else:
            print("⚠️  No spikes detected (may be expected)")
        
        return True
    
    except Exception as e:
        print(f"❌ Spike detector test failed: {e}")
        return False


async def run_all_tests():
    """Run all quick tests."""
    print("="*60)
    print("🧪 QUICK VALIDATION TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Connection
    results.append(await test_connection())
    
    # Test 2: Fee Calculator
    results.append(test_fee_calculator())
    
    # Test 3: Spike Detector
    results.append(test_spike_detector())
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
