import unittest
import sys
import os
from pathlib import Path

# Add project root to path to ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.strategies.volume_strategy import VolumeStrategy
from src.strategies.base_strategy import SignalType

# --- Mocks ---

class MockConfig:
    def __init__(self):
        self.ENABLE_VOLUME_STRATEGY = True
        self.VOLUME_SPIKE_THRESHOLD = 3.0
        self.MIN_VOLUME_FOR_STRATEGY = 100

class MockMarket:
    def __init__(self, market_id, yes_price, volume):
        self.market_id = market_id
        self.yes_price = yes_price
        self.volume = volume
        self.volume_24h = volume # For compatibility with different adapters

# --- Tests ---

class TestVolumeStrategy(unittest.TestCase):
    def setUp(self):
        self.config = MockConfig()
        self.strategy = VolumeStrategy(self.config)

    def test_initialization(self):
        """Test that strategy initializes with correct config values."""
        self.assertTrue(self.strategy.enabled)
        self.assertEqual(self.strategy.spike_threshold, 3.0)
        self.assertEqual(self.strategy.min_volume, 100)
        self.assertEqual(self.strategy.history_size, 20)

    def test_insufficient_history(self):
        """Test that no signal is generated with insufficient history."""
        market = MockMarket("m1", 0.50, 1000)
        self.strategy.on_market_update(market)
        
        # Only 1 data point (need at least 5)
        signals = self.strategy.generate_entry_signals([market])
        self.assertEqual(len(signals), 0)

    def test_volume_spike_buy_signal(self):
        """Test detection of a bullish volume spike."""
        # 1. Build baseline history (steady volume)
        base_vol = 10000
        price = 0.50
        
        # Add initial point
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        # Add 10 ticks with +100 volume each (Average tick volume = 100)
        for _ in range(10):
            base_vol += 100
            self.strategy.on_market_update(MockMarket("m1", price, base_vol))
            
        # 2. Trigger Spike
        # Volume +500 (5x average), Price +0.05 (Up)
        base_vol += 500
        price = 0.55
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        # 3. Check Signal
        signals = self.strategy.generate_entry_signals([MockMarket("m1", price, base_vol)])
        
        self.assertEqual(len(signals), 1)
        signal = signals[0]
        self.assertEqual(signal.signal_type, SignalType.BUY)
        self.assertEqual(signal.market_id, "m1")
        self.assertEqual(signal.metadata['strategy'], 'volume_spike')
        self.assertEqual(signal.metadata['vol_ratio'], 5.0)
        self.assertEqual(signal.metadata['current_vol'], 500)
        self.assertEqual(signal.metadata['avg_vol'], 100.0)

    def test_volume_spike_sell_signal(self):
        """Test detection of a bearish volume spike."""
        base_vol = 10000
        price = 0.50
        
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        # Build history
        for _ in range(10):
            base_vol += 100
            self.strategy.on_market_update(MockMarket("m1", price, base_vol))
            
        # Spike: Volume +400 (4x avg), Price -0.05 (Down)
        base_vol += 400
        price = 0.45
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        signals = self.strategy.generate_entry_signals([MockMarket("m1", price, base_vol)])
        
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, SignalType.SELL)
        self.assertEqual(signals[0].metadata['vol_ratio'], 4.0)

    def test_no_price_movement_ignored(self):
        """Test that volume spikes without price movement are ignored."""
        base_vol = 10000
        price = 0.50
        
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        for _ in range(10):
            base_vol += 100
            self.strategy.on_market_update(MockMarket("m1", price, base_vol))
            
        # Spike: Volume +500, Price Unchanged
        base_vol += 500
        # Price stays 0.50
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        signals = self.strategy.generate_entry_signals([MockMarket("m1", price, base_vol)])
        self.assertEqual(len(signals), 0)

    def test_small_price_movement_ignored(self):
        """Test that insignificant price movements are ignored."""
        base_vol = 10000
        price = 0.50
        
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        for _ in range(10):
            base_vol += 100
            self.strategy.on_market_update(MockMarket("m1", price, base_vol))
            
        # Spike: Volume +500, Price +0.001 (Below 0.005 threshold)
        base_vol += 500
        price = 0.501
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        signals = self.strategy.generate_entry_signals([MockMarket("m1", price, base_vol)])
        self.assertEqual(len(signals), 0)

    def test_min_volume_filter(self):
        """Test that spikes with low absolute volume are ignored."""
        # Set min volume to 1000
        self.strategy.min_volume = 1000
        
        base_vol = 10000
        price = 0.50
        
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        # Avg volume = 10
        for _ in range(10):
            base_vol += 10
            self.strategy.on_market_update(MockMarket("m1", price, base_vol))
            
        # Spike: +100 volume (10x avg), but 100 < 1000 min_volume
        base_vol += 100
        price = 0.55
        self.strategy.on_market_update(MockMarket("m1", price, base_vol))
        
        signals = self.strategy.generate_entry_signals([MockMarket("m1", price, base_vol)])
        self.assertEqual(len(signals), 0)

    def test_history_management(self):
        """Test that history size is maintained."""
        self.strategy.history_size = 5
        
        # Add 10 updates
        for i in range(10):
            self.strategy.on_market_update(MockMarket("m1", 0.50, i*100))
            
        history = self.strategy.history["m1"]
        
        # Should only keep last 5
        self.assertEqual(len(history), 5)
        # Should have the latest data (volume 900)
        self.assertEqual(history[-1]['volume'], 900)

    def test_get_statistics(self):
        """Test statistics reporting."""
        market = MockMarket("m1", 0.50, 1000)
        self.strategy.on_market_update(market)
        
        stats = self.strategy.get_statistics()
        self.assertTrue(stats['enabled'])
        self.assertEqual(stats['tracked_markets'], 1)

if __name__ == '__main__':
    unittest.main()
