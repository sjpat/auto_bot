#!/usr/bin/env python3
"""
Generate synthetic historical data for backtesting
Based on real-world volatile events
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
import random

def generate_election_night_data():
    """
    Simulate 2024 Presidential Election market
    Real event: Trump odds went from 55% → 95% on election night
    """
    base_time = datetime(2024, 11, 5, 20, 0, 0)  # 8 PM Election Night
    prices = []
    
    # Pre-results: Stable around 55%
    for i in range(10):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*5)).isoformat(),
            'price': 0.55 + random.uniform(-0.02, 0.02)
        })
    
    # Results start coming in: Sharp spike
    base_time = base_time + timedelta(minutes=50)
    spike_prices = [0.57, 0.62, 0.68, 0.75, 0.82, 0.88, 0.92, 0.95]  # ~72% spike!
    
    for i, price in enumerate(spike_prices):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*3)).isoformat(),
            'price': price + random.uniform(-0.005, 0.005)
        })
    
    # Stabilization
    for i in range(20):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=24 + i*5)).isoformat(),
            'price': 0.95 + random.uniform(-0.01, 0.01)
        })
    
    return prices

def generate_nfl_playoff_spike():
    """
    Simulate NFL playoff game market
    Example: Team winning probability spikes when they score
    """
    base_time = datetime(2025, 1, 12, 19, 0, 0)  # Playoff game
    prices = []
    
    # Game start: Even odds
    for i in range(15):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*2)).isoformat(),
            'price': 0.50 + random.uniform(-0.03, 0.03)
        })
    
    # Big touchdown: 15% spike
    base_time = base_time + timedelta(minutes=30)
    spike_sequence = [0.52, 0.57, 0.62, 0.65, 0.64, 0.63]
    
    for i, price in enumerate(spike_sequence):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i)).isoformat(),
            'price': price
        })
    
    # Game continues
    for i in range(30):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=6 + i*2)).isoformat(),
            'price': 0.63 + random.uniform(-0.04, 0.04)
        })
    
    return prices

def generate_fed_decision_spike():
    """
    Simulate Fed rate decision market
    Sharp moves when decision announced
    """
    base_time = datetime(2024, 12, 18, 14, 0, 0)  # Fed decision day 2 PM
    prices = []
    
    # Pre-announcement: Stable
    for i in range(25):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*2)).isoformat(),
            'price': 0.72 + random.uniform(-0.02, 0.02)
        })
    
    # Decision announced: 20% spike
    base_time = base_time + timedelta(minutes=50)
    spike_sequence = [0.73, 0.80, 0.85, 0.88, 0.87]
    
    for i, price in enumerate(spike_sequence):
        prices.append({
            'timestamp': (base_time + timedelta(seconds=i*30)).isoformat(),
            'price': price
        })
    
    # Post-announcement
    for i in range(20):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=2.5 + i*3)).isoformat(),
            'price': 0.86 + random.uniform(-0.02, 0.02)
        })
    
    return prices

def generate_nba_finals_comeback():
    """
    Simulate NBA Finals game with dramatic comeback
    """
    base_time = datetime(2025, 6, 12, 20, 0, 0)
    prices = []
    
    # Team A leading: High probability
    for i in range(20):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*2)).isoformat(),
            'price': 0.75 + random.uniform(-0.03, 0.03)
        })
    
    # Team B makes comeback: Sharp decline (inverse spike)
    base_time = base_time + timedelta(minutes=40)
    spike_sequence = [0.74, 0.68, 0.61, 0.54, 0.48, 0.42, 0.38]  # ~50% drop!
    
    for i, price in enumerate(spike_sequence):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*1.5)).isoformat(),
            'price': price
        })
    
    # Final minutes
    for i in range(15):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=10.5 + i*2)).isoformat(),
            'price': 0.38 + random.uniform(-0.03, 0.03)
        })
    
    return prices

def generate_earnings_surprise():
    """
    Simulate market reaction to major earnings surprise
    """
    base_time = datetime(2025, 1, 25, 16, 0, 0)  # After market close
    prices = []
    
    # Pre-earnings: Stable
    for i in range(15):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i*3)).isoformat(),
            'price': 0.45 + random.uniform(-0.02, 0.02)
        })
    
    # Earnings released: Massive beat → 35% spike
    base_time = base_time + timedelta(minutes=45)
    spike_sequence = [0.46, 0.52, 0.58, 0.64, 0.68, 0.70]
    
    for i, price in enumerate(spike_sequence):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=i)).isoformat(),
            'price': price
        })
    
    # Settlement
    for i in range(10):
        prices.append({
            'timestamp': (base_time + timedelta(minutes=6 + i*5)).isoformat(),
            'price': 0.69 + random.uniform(-0.01, 0.02)
        })
    
    return prices

def main():
    """Generate test dataset with multiple volatile markets"""
    
    print("="*80)
    print("GENERATING SYNTHETIC TEST DATA FOR BACKTESTING")
    print("="*80)
    
    test_data = {
        'PRES2024-TRUMP': generate_election_night_data(),
        'NFL-PLAYOFF-KC': generate_nfl_playoff_spike(),
        'FED-RATE-DEC24': generate_fed_decision_spike(),
        'NBA-FINALS-G5': generate_nba_finals_comeback(),
        'TECH-EARNINGS': generate_earnings_surprise(),
    }
    
    # Save to file
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "test_volatile_events.json"
    
    with open(output_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print(f"\n✅ Generated test data: {output_file}")
    print(f"\nDataset Summary:")
    print("-" * 80)
    
    for market_id, prices in test_data.items():
        first_price = prices[0]['price']
        max_price = max(p['price'] for p in prices)
        min_price = min(p['price'] for p in prices)
        
        max_spike = (max_price - first_price) / first_price * 100
        max_drop = (first_price - min_price) / first_price * 100
        
        print(f"\n{market_id}:")
        print(f"  Data points: {len(prices)}")
        print(f"  Price range: ${min_price:.3f} - ${max_price:.3f}")
        print(f"  Max spike: {max_spike:+.1f}%")
        print(f"  Max drop: {-max_drop:+.1f}%")
        
        # Check for 4%+ moves
        spikes_4pct = 0
        for i in range(1, len(prices)):
            change = (prices[i]['price'] - prices[i-1]['price']) / prices[i-1]['price']
            if abs(change) >= 0.04:
                spikes_4pct += 1
        
        print(f"  4%+ moves: {spikes_4pct}")
    
    print("\n" + "="*80)
    print("✅ Test data ready! Run backtest with:")
    print("   python scripts/backtest_test_data.py")
    print("="*80)

if __name__ == "__main__":
    main()
