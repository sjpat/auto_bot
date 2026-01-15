#!/usr/bin/env python3
"""
Debug version of backtest to see exact entry/exit details
"""
import json
from pathlib import Path
from datetime import datetime

# Load test data
test_file = Path("data/test_volatile_events.json")
with open(test_file, 'r') as f:
    raw_data = json.load(f)

# Analyze the Fed decision market specifically
market_id = "FED-RATE-DEC24"
prices = raw_data[market_id]

print("="*80)
print(f"DEBUGGING: {market_id}")
print("="*80)

print("\nPrice movements:")
for i, point in enumerate(prices):
    timestamp = datetime.fromisoformat(point['timestamp'])
    price = point['price']
    
    if i > 0:
        prev_price = prices[i-1]['price']
        change = (price - prev_price) / prev_price * 100
        
        # Check if this is a 4%+ spike
        is_spike = abs(change) >= 4.0
        spike_marker = " ← SPIKE!" if is_spike else ""
        
        print(f"{i:3d}. {timestamp.strftime('%H:%M:%S')} - ${price:.3f} ({change:+.2f}%){spike_marker}")
    else:
        print(f"{i:3d}. {timestamp.strftime('%H:%M:%S')} - ${price:.3f} (baseline)")

# Now simulate ONE trade manually
print("\n" + "="*80)
print("MANUAL TRADE SIMULATION")
print("="*80)

# Find first spike
for i in range(1, len(prices)):
    change = (prices[i]['price'] - prices[i-1]['price']) / prices[i-1]['price']
    
    if abs(change) >= 0.04:
        entry_idx = i
        entry_price = prices[i]['price']
        prev_price = prices[i-1]['price']
        
        print(f"\n🚨 SPIKE DETECTED at index {i}")
        print(f"   Previous: ${prev_price:.3f}")
        print(f"   Current:  ${entry_price:.3f}")
        print(f"   Change:   {change:+.2%}")
        
        # Determine entry
        if change > 0:
            print(f"\n📈 Upward spike detected")
            print(f"   Strategy: Buy NO (fade the spike)")
            entry_side = 'no'
        else:
            print(f"\n📉 Downward spike detected")
            print(f"   Strategy: Buy YES (fade the spike)")
            entry_side = 'yes'
        
        # Calculate costs
        contracts = 100
        
        if entry_side == 'no':
            entry_cost = contracts * (1.0 - entry_price)
            print(f"   NO cost: {contracts} × (1.0 - ${entry_price:.3f}) = ${entry_cost:.2f}")
        else:
            entry_cost = contracts * entry_price
            print(f"   YES cost: {contracts} × ${entry_price:.3f} = ${entry_cost:.2f}")
        
        # Simulate holding for 5 minutes
        exit_idx = min(i + 2, len(prices) - 1)  # ~2 ticks later
        exit_price = prices[exit_idx]['price']
        
        print(f"\n⏱️  EXIT after {exit_idx - entry_idx} ticks")
        print(f"   Exit YES price: ${exit_price:.3f}")
        
        # Calculate exit value
        if entry_side == 'no':
            exit_value = contracts * (1.0 - exit_price)
            print(f"   NO exit value: {contracts} × (1.0 - ${exit_price:.3f}) = ${exit_value:.2f}")
        else:
            exit_value = contracts * exit_price
            print(f"   YES exit value: {contracts} × ${exit_price:.3f} = ${exit_value:.2f}")
        
        # Calculate P&L
        gross_pnl = exit_value - entry_cost
        fees = (entry_cost + exit_value) * 0.07
        net_pnl = gross_pnl - fees
        return_pct = net_pnl / entry_cost * 100
        
        print(f"\n💰 P&L CALCULATION")
        print(f"   Entry cost:  ${entry_cost:.2f}")
        print(f"   Exit value:  ${exit_value:.2f}")
        print(f"   Gross P&L:   ${gross_pnl:+.2f}")
        print(f"   Fees:        ${fees:.2f}")
        print(f"   Net P&L:     ${net_pnl:+.2f}")
        print(f"   Return:      {return_pct:+.1f}%")
        
        if net_pnl > 0:
            print("\n   ✅ PROFITABLE TRADE")
        else:
            print("\n   ❌ LOSING TRADE")
        
        # Check next few price movements
        print(f"\n📊 Next 5 price movements:")
        for j in range(i+1, min(i+6, len(prices))):
            p = prices[j]['price']
            chg = (p - entry_price) / entry_price * 100
            print(f"   Tick {j-i}: ${p:.3f} ({chg:+.2f}% from entry)")
        
        break

print("\n" + "="*80)
