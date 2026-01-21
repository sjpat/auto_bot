"""
Real API integration tests to verify market data is being pulled correctly.
These tests make REAL API calls (not mocked) to validate data quality.
"""
import pytest
import asyncio
from datetime import datetime
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector


@pytest.mark.integration
def test_real_market_data_retrieval(config):
    """
    Test that we can retrieve real market data from Kalshi API.
    This is NOT mocked - it makes a real API call.
    """
    async def _test():
        client = KalshiClient(config)
        
        try:
            # Authenticate
            auth_success = await client.authenticate()
            assert auth_success, "Failed to authenticate with Kalshi API"
            
            # Get real markets with low volume filter
            markets = await client.get_markets(status="open", limit=50, min_volume=1)
            
            # Basic validation
            assert len(markets) > 0, "No markets returned from API"
            print(f"\n✅ Retrieved {len(markets)} open markets")
            
            # Validate data structure
            for market in markets[:5]:  # Check first 5
                assert market.market_id is not None
                assert market.title is not None
                assert market.last_price_cents > 0, f"Market {market.market_id} has invalid price: {market.last_price_cents}"
                assert 0 <= market.last_price_cents <= 10000, f"Market {market.market_id} price out of range: {market.last_price_cents}"
                
                print(f"  Market: {market.market_id}")
                print(f"    Price: ${market.price:.4f} ({market.last_price_cents} cents)")
                print(f"    Liquidity: ${market.liquidity_usd:.2f}")
                print(f"    Status: {market.status}")
                
        finally:
            await client.close()
    
    asyncio.run(_test())


@pytest.mark.integration
def test_market_data_freshness(config):
    """
    Verify that market data contains recent timestamps and is not stale.
    """
    async def _test():
        client = KalshiClient(config)
        
        try:
            await client.authenticate()
            markets = await client.get_markets(status="open", limit=20, min_volume=1)
            
            # Skip test if no markets available
            if len(markets) == 0:
                pytest.skip("No markets available for testing")
            
            now = datetime.now().timestamp()
            stale_count = 0
            
            for market in markets:
                # Check if market close time is in the future (market is actually active)
                if market.close_ts < now:
                    stale_count += 1
                    print(f"⚠️  Market {market.market_id} has expired (close_ts: {market.close_ts})")
                else:
                    time_to_close = (market.close_ts - now) / 3600  # hours
                    print(f"✅ Market {market.market_id} closes in {time_to_close:.1f} hours")
            
            # At least 50% of markets should be active
            active_percent = (len(markets) - stale_count) / len(markets) * 100
            assert active_percent >= 50, f"Too many stale markets: only {active_percent:.0f}% are active"
            
        finally:
            await client.close()
    
    asyncio.run(_test())


@pytest.mark.integration
def test_price_data_for_spike_detection(config):
    """
    Test that the data structure works with spike detector.
    This validates the integration between API data and spike detection logic.
    """
    async def _test():
        client = KalshiClient(config)
        spike_detector = SpikeDetector(config)
        
        try:
            await client.authenticate()
            markets = await client.get_markets(status="open", limit=10, min_volume=1)
            
            # Skip if no markets
            if len(markets) == 0:
                pytest.skip("No markets available for testing")
            
            # Add some price history for first market
            test_market = markets[0]  # Fixed: was missing [0]
            
            print(f"\n📊 Testing spike detection with market: {test_market.market_id}")
            print(f"   Current price: ${test_market.price:.4f}")
            
            # Simulate price history by adding current price multiple times
            for i in range(25):
                spike_detector.add_price(
                    market_id=test_market.market_id,
                    price=test_market.price,
                    timestamp=datetime.now()
                )
            
            # Verify price was added
            assert test_market.market_id in spike_detector.price_history
            assert len(spike_detector.price_history[test_market.market_id]) == 25
            
            # Try to detect spikes (should be none since prices are stable)
            spikes = spike_detector.detect_spikes(markets=[test_market], threshold=0.04)
            
            print(f"   Spikes detected: {len(spikes)}")
            
            # Verify the detection ran without errors
            assert spikes is not None
            
        finally:
            await client.close()
    
    asyncio.run(_test())


@pytest.mark.integration
def test_price_variation_across_markets(config):
    """
    Verify that different markets have different prices (not all returning same default).
    """
    async def _test():
        client = KalshiClient(config)
        
        try:
            await client.authenticate()
            markets = await client.get_markets(status="open", limit=20, min_volume=1)
            
            # Skip if no markets
            if len(markets) == 0:
                pytest.skip("No markets available for testing")
            
            prices = [m.last_price_cents for m in markets]
            unique_prices = len(set(prices))
            
            print(f"\n💰 Price diversity check:")
            print(f"   Total markets: {len(markets)}")
            print(f"   Unique prices: {unique_prices}")
            print(f"   Sample prices: {prices[:10]}")
            
            # At least 30% of prices should be unique (not all the same)
            diversity_ratio = unique_prices / len(markets)
            assert diversity_ratio >= 0.3, f"Prices lack diversity ({diversity_ratio*100:.0f}% unique). Possible stale data."
            
            # Check that not all prices are at 0.50 (5000 cents)
            default_price_count = sum(1 for p in prices if p == 5000)
            default_ratio = default_price_count / len(markets)
            
            print(f"   Markets at default price (5000 cents): {default_price_count} ({default_ratio*100:.0f}%)")
            
            assert default_ratio < 0.5, f"Too many markets at default price ({default_ratio*100:.0f}%)"
            
        finally:
            await client.close()
    
    asyncio.run(_test())

@pytest.mark.integration
def test_close_timestamp_parsing(config):
    """Test that close timestamps are parsed correctly from various formats."""
    async def _test():
        client = KalshiClient(config)
        
        try:
            await client.authenticate()
            markets = await client.get_markets(status="open", limit=30, min_volume=1)
            
            if len(markets) == 0:
                pytest.skip("No markets available for testing")
            
            now = datetime.now().timestamp()
            valid_timestamps = 0
            invalid_timestamps = 0
            
            print(f"\n⏰ Timestamp validation:")
            
            for market in markets:
                assert isinstance(market.close_ts, int), \
                    f"Market {market.market_id} has non-integer timestamp: {type(market.close_ts)}"
                
                one_year = 365 * 24 * 3600
                if now - one_year < market.close_ts < now + (5 * one_year):
                    valid_timestamps += 1
                else:
                    invalid_timestamps += 1
                    print(f"   ⚠️  {market.market_id}: timestamp out of range")
            
            print(f"   Valid: {valid_timestamps}/{len(markets)}")
            
            validity_ratio = valid_timestamps / len(markets)
            assert validity_ratio >= 0.9, \
                f"Too many invalid timestamps: {validity_ratio * 100:.0f}% valid"
            
        finally:
            await client.close()
    
    asyncio.run(_test())


@pytest.mark.integration
def test_no_markets_skipped_due_to_parsing_errors(config):
    """Verify that the fixed parsing logic doesn't skip markets unnecessarily."""
    async def _test():
        client = KalshiClient(config)
        
        try:
            await client.authenticate()
            
            markets = await client.get_markets(
                status="open",
                limit=50,
                min_volume=0,
                filter_untradeable=False
            )
            
            print(f"\n📈 Market retrieval efficiency:")
            print(f"   Requested: 50")
            print(f"   Received: {len(markets)}")
            
            assert len(markets) >= 20, \
                f"Too few markets returned: {len(markets)}/50. Possible parsing issues."
            
            for market in markets:
                assert market.market_id
                assert market.title
                assert market.close_ts > 0
                assert 0 <= market.last_price_cents <= 10000
            
            print(f"   ✅ All {len(markets)} markets have valid data")
            
        finally:
            await client.close()
    
    asyncio.run(_test())

@pytest.mark.integration
def test_price_conversion_accuracy(config):
    """Verify that prices are converted correctly from Kalshi's format."""
    async def _test():
        client = KalshiClient(config)
        
        try:
            await client.authenticate()
            markets = await client.get_markets(status="open", limit=20, min_volume=1)
            
            if len(markets) == 0:
                pytest.skip("No markets available for testing")
            
            print(f"\n💵 Price conversion check:")
            
            for market in markets[:5]:
                # Verify price is in basis points (0-10000)
                assert 0 <= market.last_price_cents <= 10000, \
                    f"Price out of range: {market.last_price_cents}"
                
                # Verify price property converts correctly to 0.00-1.00 range
                price_float = market.price
                assert 0.0 <= price_float <= 1.0, \
                    f"Float price out of range: {price_float}"
                
                # Verify conversion is correct (within 0.0001 tolerance)
                expected_float = market.last_price_cents / 10000.0
                assert abs(price_float - expected_float) < 0.0001, \
                    f"Price conversion error: {price_float} != {expected_float}"
                
                print(f"   ✅ {market.market_id}: {market.last_price_cents} → ${price_float:.4f}")
            
            print(f"   All {min(5, len(markets))} sample prices converted correctly")
            
        finally:
            await client.close()
    
    asyncio.run(_test())
