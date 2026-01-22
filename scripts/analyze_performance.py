#!/usr/bin/env python3
"""
Analyze Paper Trading Performance
Reads the JSON history file and outputs key metrics.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def main():
    # Path to history file (default from config)
    history_file = Path("logs/paper_trading_history.json")
    
    if not history_file.exists():
        print(f"❌ History file not found: {history_file}")
        return

    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
    except json.JSONDecodeError:
        print("❌ Error reading history file (might be empty or corrupt)")
        return

    trades = history.get('trades', [])
    if not trades:
        print("ℹ️  No closed trades found yet.")
        return

    # Calculate Metrics
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]
    
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0.0
    
    # Best/Worst
    best_trade = max(trades, key=lambda x: x['pnl'])
    worst_trade = min(trades, key=lambda x: x['pnl'])
    
    # Average PnL
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0

    print("=" * 60)
    print(f"📊 PAPER TRADING PERFORMANCE REPORT")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    print(f"\n💰 P&L Summary:")
    print(f"   Total PnL:      ${total_pnl:+.2f}")
    print(f"   Total Trades:   {total_trades}")
    print(f"   Win Rate:       {win_rate:.1f}%")
    
    print(f"\n📈 Trade Stats:")
    print(f"   Avg Win:        ${avg_win:+.2f}")
    print(f"   Avg Loss:       ${avg_loss:+.2f}")
    print(f"   Profit Factor:  {abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else 'Inf':.2f}")
    
    print(f"\n🏆 Extremes:")
    print(f"   Best Trade:     ${best_trade['pnl']:+.2f} ({best_trade['market_id']})")
    print(f"   Worst Trade:    ${worst_trade['pnl']:+.2f} ({worst_trade['market_id']})")
    
    print(f"\n📋 Recent Trades (Last 5):")
    print(f"   {'Time':<20} {'Market':<25} {'Side':<5} {'PnL':<10}")
    print("-" * 65)
    
    for t in trades[-5:]:
        ts = t.get('exit_time', 'N/A')[:19]
        market = t.get('market_id', 'Unknown')[:23]
        side = t.get('side', 'UNK').upper()
        pnl = t.get('pnl', 0.0)
        print(f"   {ts:<20} {market:<25} {side:<5} ${pnl:<+8.2f}")
    print("-" * 65)

if __name__ == "__main__":
    main()

'''

### How to Enable the Service
Run these commands in your terminal to start the background service:

```bash
# 1. Copy service file to systemd directory
sudo cp auto_bot.service /etc/systemd/system/

# 2. Reload systemd to recognize the new service
sudo systemctl daemon-reload

# 3. Enable the service to start on boot
sudo systemctl enable auto_bot

# 4. Start the bot immediately
sudo systemctl start auto_bot

# 5. Check status
sudo systemctl status auto_bot
'''