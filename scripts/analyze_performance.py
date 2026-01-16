"""
Analyze bot performance from logs and history.
"""
import json
import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def analyze_paper_trading_history(history_file='logs/paper_trading_history.json'):
    """Analyze paper trading results."""
    print("="*80)
    print("PAPER TRADING PERFORMANCE ANALYSIS")
    print("="*80)
    
    if not os.path.exists(history_file):
        print(f"\n❌ History file not found: {history_file}")
        return
    
    with open(history_file, 'r') as f:
        history = json.load(f)
    
    orders = history.get('orders', [])
    
    if not orders:
        print("\n⚠️ No orders found in history")
        return
    
    print(f"\n📊 Total Orders: {len(orders)}")
    
    # Categorize orders
    by_side = defaultdict(int)
    by_status = defaultdict(int)
    pnl_by_market = defaultdict(list)
    
    total_pnl = 0
    winning_trades = 0
    losing_trades = 0
    
    for order in orders:
        side = order.get('side', 'unknown')
        status = order.get('status', 'unknown')
        
        by_side[side] += 1
        by_status[status] += 1
        
        # Calculate P&L if filled
        if status == 'filled':
            market_id = order.get('market_id', 'unknown')
            pnl = order.get('pnl', 0)
            
            pnl_by_market[market_id].append(pnl)
            total_pnl += pnl
            
            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1
    
    # Print summary
    print(f"\n📈 Orders by Side:")
    for side, count in by_side.items():
        print(f"   {side.upper()}: {count}")
    
    print(f"\n📋 Orders by Status:")
    for status, count in by_status.items():
        print(f"   {status}: {count}")
    
    print(f"\n💰 P&L Summary:")
    print(f"   Total P&L: ${total_pnl:+.2f}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    
    if winning_trades + losing_trades > 0:
        win_rate = winning_trades / (winning_trades + losing_trades) * 100
        print(f"   Win Rate: {win_rate:.1f}%")
    
    # Top/Bottom markets
    if pnl_by_market:
        print(f"\n🏆 Best Markets:")
        sorted_markets = sorted(
            pnl_by_market.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )
        for market_id, pnls in sorted_markets[:5]:
            total = sum(pnls)
            print(f"   {market_id[:40]}: ${total:+.2f} ({len(pnls)} trades)")
        
        print(f"\n📉 Worst Markets:")
        for market_id, pnls in sorted_markets[-5:]:
            total = sum(pnls)
            print(f"   {market_id[:40]}: ${total:+.2f} ({len(pnls)} trades)")
    
    print("\n" + "="*80)


def analyze_log_file(log_file='logs/trading_bot_demo_optimized.log'):
    """Analyze bot activity from logs."""
    print("\n" + "="*80)
    print("LOG FILE ANALYSIS")
    print("="*80)
    
    if not os.path.exists(log_file):
        print(f"\n❌ Log file not found: {log_file}")
        return
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    print(f"\n📄 Total log lines: {len(lines)}")
    
    # Count key events
    events = {
        'spikes_detected': 0,
        'trades_executed': 0,
        'positions_closed': 0,
        'errors': 0,
        'api_calls': 0
    }
    
    for line in lines:
        if 'spike' in line.lower() and 'detected' in line.lower():
            events['spikes_detected'] += 1
        if 'executing trade' in line.lower():
            events['trades_executed'] += 1
        if 'position closed' in line.lower():
            events['positions_closed'] += 1
        if 'error' in line.lower():
            events['errors'] += 1
        if 'api' in line.lower():
            events['api_calls'] += 1
    
    print(f"\n📊 Event Summary:")
    for event, count in events.items():
        print(f"   {event.replace('_', ' ').title()}: {count}")
    
    print("="*80)


if __name__ == "__main__":
    analyze_paper_trading_history()
    analyze_log_file()
