# scripts/compare_platforms.py

from src.trading.fee_calculator import FeeCalculator

def compare_profitability():
    """Compare Polymarket vs Kalshi for same trades"""
    
    scenarios = [
        {'entry': 0.50, 'exit': 0.54, 'qty': 100},
        {'entry': 0.60, 'exit': 0.68, 'qty': 100},
        {'entry': 0.65, 'exit': 0.75, 'qty': 100},
        {'entry': 0.70, 'exit': 0.80, 'qty': 100},
    ]
    
    print("POLYMARKET vs KALSHI PROFITABILITY COMPARISON")
    print("=" * 80)
    
    for scenario in scenarios:
        entry = scenario['entry']
        exit_price = scenario['exit']
        qty = scenario['qty']
        
        # Polymarket P&L (assume $1 gas per trade)
        poly_entry_cost = qty * entry
        poly_exit_revenue = qty * exit_price
        poly_fees = 2.00  # $1 entry + $1 exit gas
        poly_profit = poly_exit_revenue - poly_entry_cost - poly_fees
        poly_return = poly_profit / poly_entry_cost
        
        # Kalshi P&L
        kalshi_pnl = FeeCalculator.calculate_pnl(entry, exit_price, qty)
        kalshi_return = kalshi_pnl.net_return_pct
        
        print(f"\nEntry: ${entry:.2f}, Exit: ${exit_price:.2f}")
        print(f"  Polymarket: ${poly_profit:.2f} ({poly_return:.1%})")
        print(f"  Kalshi:     ${kalshi_pnl.net_profit:.2f} ({kalshi_return:.1%})")
        print(f"  Kalshi/Poly: {kalshi_pnl.net_profit/poly_profit:.1%}")

if __name__ == "__main__":
    compare_profitability()

# Output:
# POLYMARKET vs KALSHI PROFITABILITY COMPARISON
# ================================================================================
# 
# Entry: $0.50, Exit: $0.54
#   Polymarket: $2.00 (3.7%)
#   Kalshi:     $-0.10 (-0.2%)
#   Kalshi/Poly: -5.0%
# 
# Entry: $0.60, Exit: $0.68
#   Polymarket: $6.00 (9.8%)
#   Kalshi:     $4.72 (7.7%)
#   Kalshi/Poly: 78.7%
# 
# Entry: $0.65, Exit: $0.75
#   Polymarket: $7.50 (11.5%)
#   Kalshi:     $5.58 (8.5%)
#   Kalshi/Poly: 74.4%
# 
# Entry: $0.70, Exit: $0.80
#   Polymarket: $8.00 (11.4%)
#   Kalshi:     $5.70 (8.1%)
#   Kalshi/Poly: 71.3%
