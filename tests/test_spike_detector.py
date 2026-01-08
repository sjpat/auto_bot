"""
Tests for spike detection logic.
"""

import pytest
from datetime import datetime
from collections import deque
from src.trading.spike_detector import SpikeDetector


class TestSpikeDetector:
    """Test spike detection functionality."""
    
    def test_initialization(self, config):
        """Test spike detector initialization."""
        detector = SpikeDetector(config)
        assert detector is not None
        assert config.SPIKE_THRESHOLD == 0.04
    
    def test_add_price(self, config, sample_market):
        """Test adding price to history."""
        detector = SpikeDetector(config)
        
        detector.add_price(
            market_id=sample_market.market_id,
            price=0.65,
            timestamp=datetime.now()
        )
        
        assert sample_market.market_id in detector.price_history
        assert len(detector.price_history[sample_market.market_id]) == 1
    
    def test_spike_detection_insufficient_history(self, config, sample_market):
        """Test no spike with insufficient history."""
        detector = SpikeDetector(config)
        threshold = config.SPIKE_THRESHOLD
        # Add only 5 prices (need at least 20)
        for i in range(5):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.65,
                timestamp=datetime.now()
            )
        
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) == 0
    
    def test_spike_detection_no_spike(self, config, sample_market):
        """Test no spike when prices are stable."""
        detector = SpikeDetector(config)
        threshold = config.SPIKE_THRESHOLD
        # Add 25 stable prices
        for i in range(25):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.65,
                timestamp=datetime.now()
            )
        
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) == 0
    
    def test_spike_detection_upward(self, config, sample_market):
        """Test upward spike detection."""
        detector = SpikeDetector(config)
        threshold = config.SPIKE_THRESHOLD
        # Add baseline prices
        for i in range(20):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.60,
                timestamp=datetime.now()
            )
        
        # Add a few prices at higher level
        for i in range(3):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.63,
                timestamp=datetime.now()
            )
        
        # Current price is spike
        sample_market.last_price_cents = 6500  # 0.65 (8.3% above baseline)
        
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) >= 1
        assert spikes[0].change_pct > 0.04  # Above threshold
    
    def test_spike_detection_downward(self, config, sample_market):
        """Test downward spike detection."""
        detector = SpikeDetector(config)
        threshold = config.SPIKE_THRESHOLD
        # Add baseline prices
        for i in range(20):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.70,
                timestamp=datetime.now()
            )
        
        # Current price drops
        sample_market.last_price_cents = 6500  # 0.65 (7.1% below baseline)
        
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) >= 1
        assert abs(spikes[0].change_pct) > 0.04
    
    def test_spike_threshold(self, config, sample_market):
        """Test spike threshold filtering."""
        detector = SpikeDetector(config)
        threshold = config.SPIKE_THRESHOLD
        # Add baseline at 0.60
        for i in range(20):
            detector.add_price(
                market_id=sample_market.market_id,
                price=0.60,
                timestamp=datetime.now()
            )
        
        # Test 3% move (below 4% threshold)
        sample_market.last_price_cents = 6180  # 0.618 (3% move)
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) == 0
        
        # Test 5% move (above 4% threshold)
        sample_market.last_price_cents = 6300  # 0.63 (5% move)
        spikes = detector.detect_spikes(threshold)
        assert len(spikes) >= 1
