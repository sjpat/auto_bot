# src/trading/fee_calculator.py

"""
Fee Calculator for Kalshi Trading

Implements Kalshi fee formulas:
- Taker: 0.07 × C × P × (1-P)
- Maker: 0.0175 × C × P × (1-P)

Where:
  C = number of contracts
  P = contract price (0.00-1.00)
  (1-P) = complementary probability

Key Methods:
- kalshi_fee(): Calculate fee for given price/quantity
- entry_cost(): Calculate total cost including entry fee
- exit_revenue(): Calculate net revenue after exit fee
- calculate_pnl(): Calculate profit/loss including both fees
- required_exit_price_for_target_profit(): Solve for exit price
- breakeven_exit_price(): Calculate minimum exit to break even
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP


@dataclass
class FeeInfo:
    """Fee calculation result."""
    fee: float
    multiplier: float
    contracts: int
    price: float
    
    def __str__(self) -> str:
        return f"Fee: ${self.fee:.2f} ({self.multiplier:.2%} on {self.contracts}@${self.price:.2f})"


@dataclass
class PnLInfo:
    """Profit/Loss calculation result."""
    entry_price: float
    exit_price: float
    contracts: int
    entry_cost: float
    entry_fee: float
    exit_revenue: float
    exit_fee: float
    gross_profit: float
    total_fees: float
    net_profit: float
    return_pct: float
    
    def __str__(self) -> str:
        return (
            f"Entry: ${self.entry_price:.4f} × {self.contracts} = ${self.entry_cost:.2f} "
            f"(+${self.entry_fee:.2f} fee) | "
            f"Exit: ${self.exit_price:.4f} × {self.contracts} = ${self.exit_revenue:.2f} "
            f"(-${self.exit_fee:.2f} fee) | "
            f"Net: ${self.net_profit:.2f} ({self.return_pct:.2%})"
        )


class FeeCalculator:
    """
    Calculate Kalshi trading fees and P&L.
    
    Implements Kalshi's fee formula:
    Fee = round_up(multiplier × contracts × price × (1-price))
    """
    
    TAKER_MULTIPLIER = 0.07      # 7% for market orders (immediate execution)
    MAKER_MULTIPLIER = 0.0175    # 1.75% for limit orders (passive)
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # BASIC FEE CALCULATIONS
    # ========================================================================
    
    def kalshi_fee(
        self,
        contracts: int,
        price: float,
        fee_type: str = "taker"
    ) -> float:
        """
        Calculate Kalshi fee for given price and quantity.
        
        Formula: Fee = round_up(multiplier × C × P × (1-P))
        
        Args:
            contracts: Number of contracts
            price: Contract price (0.00-1.00)
            fee_type: "taker" or "maker"
        
        Returns:
            Fee in USD
        
        Example:
            100 contracts at $0.65 (taker):
            Fee = 0.07 × 100 × 0.65 × 0.35 = $1.5925 → rounds to $1.60
        """
        if fee_type.lower() == "maker":
            multiplier = self.MAKER_MULTIPLIER
        else:  # taker (default)
            multiplier = self.TAKER_MULTIPLIER
        
        # Calculate fee using Decimal for precision
        fee_decimal = (
            Decimal(str(multiplier)) *
            Decimal(str(contracts)) *
            Decimal(str(price)) *
            Decimal(str(1 - price))
        )
        
        # Round up to nearest cent
        fee_cents = fee_decimal * 100
        fee_cents_rounded = fee_cents.quantize(Decimal('1'), rounding=ROUND_UP)
        fee_usd = float(fee_cents_rounded / 100)
        
        return round(fee_usd,2)
    
    # ========================================================================
    # ENTRY/EXIT CALCULATIONS
    # ========================================================================
    
    def entry_cost(
        self,
        contracts: int,
        entry_price: float,
        fee_type: str = "taker"
    ) -> Dict[str, float]:
        """
        Calculate total cost to enter position (price + fee).
        
        Args:
            contracts: Number of contracts
            entry_price: Entry price
            fee_type: "taker" or "maker"
        
        Returns:
            Dictionary with:
            - notional: Entry price × contracts
            - fee: Entry fee
            - total_cost: notional + fee
        
        Example:
            100 contracts at $0.65:
            - Notional: $65.00
            - Fee: $1.60
            - Total: $66.60
        """
        notional = entry_price * contracts
        fee = self.kalshi_fee(contracts, entry_price, fee_type)
        
        return {
            'notional': notional,
            'fee': fee,
            'total_cost': notional + fee,
            'price': entry_price,
            'contracts': contracts
        }
    
    def exit_revenue(
        self,
        contracts: int,
        exit_price: float,
        fee_type: str = "taker"
    ) -> Dict[str, float]:
        """
        Calculate net revenue from exit (price - fee).
        
        Args:
            contracts: Number of contracts
            exit_price: Exit price
            fee_type: "taker" or "maker"
        
        Returns:
            Dictionary with:
            - notional: Exit price × contracts
            - fee: Exit fee
            - net_revenue: notional - fee
        
        Example:
            100 contracts at $0.70:
            - Notional: $70.00
            - Fee: $1.47
            - Net: $68.53
        """
        notional = exit_price * contracts
        fee = self.kalshi_fee(contracts, exit_price, fee_type)
        
        return {
            'notional': notional,
            'fee': fee,
            'net_revenue': notional - fee,
            'price': exit_price,
            'contracts': contracts
        }
    
    # ========================================================================
    # PROFIT/LOSS CALCULATIONS
    # ========================================================================
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        contracts: int,
        entry_fee_type: str = "taker",
        exit_fee_type: str = "taker"
    ) -> PnLInfo:
        """
        Calculate complete profit/loss including both entry and exit fees.
        
        CRITICAL: Both entry AND exit fees must be included!
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            contracts: Number of contracts
            entry_fee_type: Entry fee type ("taker" or "maker")
            exit_fee_type: Exit fee type ("taker" or "maker")
        
        Returns:
            PnLInfo with detailed breakdown
        
        Example:
            Buy 100 @ $0.60, Sell @ $0.70
            
            Entry: $60.00 + $1.68 = $61.68
            Exit: $70.00 - $1.47 = $68.53
            Profit: $68.53 - $61.68 = $6.85
            Return: 11.1% (not 16.7% gross)
        """
        # Entry costs
        entry_notional = entry_price * contracts
        entry_fee = self.kalshi_fee(contracts, entry_price, entry_fee_type)
        entry_total = entry_notional + entry_fee
        
        # Exit proceeds
        exit_notional = exit_price * contracts
        exit_fee = self.kalshi_fee(contracts, exit_price, exit_fee_type)
        exit_total = exit_notional - exit_fee
        
        # Profit/Loss
        gross_profit = exit_notional - entry_notional
        total_fees = entry_fee + exit_fee
        net_profit = exit_total - entry_total
        # return_pct = net_profit / entry_total if entry_total > 0 else 0
        return_pct = net_profit / entry_notional if entry_notional > 0 else 0
        
        return PnLInfo(
            entry_price=entry_price,
            exit_price=exit_price,
            contracts=contracts,
            entry_cost=entry_total,
            entry_fee=entry_fee,
            exit_revenue=exit_total,
            exit_fee=exit_fee,
            gross_profit=gross_profit,
            total_fees=total_fees,
            net_profit=net_profit,
            return_pct=return_pct
        )
    
    # ========================================================================
    # SOLVER METHODS
    # ========================================================================
    
    def required_exit_price_for_target_profit(
        self,
        entry_price: float,
        target_profit_usd: float,
        contracts: int,
        entry_fee_type: str = "taker",
        exit_fee_type: str = "taker"
    ) -> Optional[float]:
        """
        Calculate exit price needed to achieve target profit.
        
        Solves for: exit_price such that net_profit = target_profit_usd
        
        Args:
            entry_price: Entry price
            target_profit_usd: Target profit in dollars
            contracts: Number of contracts
            entry_fee_type: Entry fee type
            exit_fee_type: Exit fee type
        
        Returns:
            Exit price needed (or None if impossible)
        
        Example:
            Entry @ $0.65, want $2.50 profit, 100 contracts:
            - Entry cost: $66.60 (including fee)
            - Need exit revenue: $69.10
            - Required exit price: $0.691
        """
        # Calculate entry cost
        entry_fee = self.kalshi_fee(contracts, entry_price, entry_fee_type)
        entry_total = (entry_price * contracts) + entry_fee
        
        # Required exit revenue
        required_exit_revenue = entry_total + target_profit_usd
        
        # Iterative search for exit price (binary search)
        # Fee formula makes it non-linear, so we solve numerically
        
        low_price = 0.00
        high_price = 1.00
        precision = 0.0001  # $0.0001 precision
        
        for _ in range(100):  # Max iterations
            mid_price = (low_price + high_price) / 2
            
            exit_fee = self.kalshi_fee(contracts, mid_price, exit_fee_type)
            exit_total = (mid_price * contracts) - exit_fee
            
            if abs(exit_total - required_exit_revenue) < precision:
                return round(mid_price, 4)
            
            if exit_total < required_exit_revenue:
                low_price = mid_price
            else:
                high_price = mid_price
        
        self.logger.warning(
            f"Could not solve for exit price: "
            f"entry=${entry_price:.4f}, target=${target_profit_usd:.2f}"
        )
        return None
    
    def breakeven_exit_price(
        self,
        entry_price: float,
        contracts: int,
        entry_fee_type: str = "taker",
        exit_fee_type: str = "taker"
    ) -> float:
        """
        Calculate minimum exit price to break even.
        
        Accounts for both entry AND exit fees.
        
        Args:
            entry_price: Entry price
            contracts: Number of contracts
            entry_fee_type: Entry fee type
            exit_fee_type: Exit fee type
        
        Returns:
            Breakeven exit price
        
        Example:
            Entry @ $0.60, 100 contracts:
            - Entry cost: $61.68 (with fee)
            - Exit fee @ breakeven price: $1.68
            - Total to recover: $63.36
            - Breakeven exit: $0.6336 (not $0.60!)
        """
        # Calculate entry cost
        entry_fee = self.kalshi_fee(contracts, entry_price, entry_fee_type)
        entry_total = (entry_price * contracts) + entry_fee
        
        # Need to recover entry_total after exit fees
        # This is a bit circular since exit fee depends on exit price
        # So we solve iteratively
        
        low_price = entry_price * 0.99
        high_price = 1.00
        precision = 0.00001
        
        for _ in range(100):
            mid_price = (low_price + high_price) / 2
            
            exit_fee = self.kalshi_fee(contracts, mid_price, exit_fee_type)
            exit_total = (mid_price * contracts) - exit_fee
            
            if abs(exit_total - entry_total) < precision:
                return round(mid_price, 4)
            
            if exit_total < entry_total:
                low_price = mid_price
            else:
                high_price = mid_price
        
        return round(low_price, 4)
    
    def breakeven_price_move_percent(
        self,
        entry_price: float,
        contracts: int,
        entry_fee_type: str = "taker",
        exit_fee_type: str = "taker"
    ) -> float:
        """
        Calculate minimum price move percentage to break even.
        
        Args:
            entry_price: Entry price
            contracts: Number of contracts
            entry_fee_type: Entry fee type
            exit_fee_type: Exit fee type
        
        Returns:
            Minimum price move percentage
        
        Example:
            Entry @ $0.60:
            - Breakeven exit: $0.6336
            - Move needed: ($0.6336 - $0.60) / $0.60 = 5.6%
        """
        breakeven_price = self.breakeven_exit_price(
            entry_price, contracts, entry_fee_type, exit_fee_type
        )
        
        move_pct = (breakeven_price - entry_price) / entry_price if entry_price > 0 else 0
        return move_pct
    
    # ========================================================================
    # ANALYSIS METHODS
    # ========================================================================
    
    def fee_impact_analysis(
        self,
        entry_price: float,
        exit_price: float,
        contracts: int
    ) -> Dict[str, Any]:
        """
        Comprehensive fee impact analysis.
        
        Returns:
            Dictionary with complete analysis
        """
        pnl = self.calculate_pnl(entry_price, exit_price, contracts)
        
        entry_fee = pnl.entry_fee
        exit_fee = pnl.exit_fee
        total_fees = pnl.total_fees
        
        entry_fee_pct = (entry_fee / (entry_price * contracts)) * 100 if entry_price > 0 else 0
        exit_fee_pct = (exit_fee / (exit_price * contracts)) * 100 if exit_price > 0 else 0
        
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'contracts': contracts,
            'gross_profit': pnl.gross_profit,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'total_fees': total_fees,
            'entry_fee_pct_of_notional': entry_fee_pct,
            'exit_fee_pct_of_notional': exit_fee_pct,
            'net_profit': pnl.net_profit,
            'fee_impact_pct': (total_fees / pnl.gross_profit * 100) if pnl.gross_profit > 0 else 0,
            'profitability_pct': pnl.return_pct * 100,
            'message': str(pnl)
        }
    
    def sweet_price_range(self, contracts: int = 100) -> Dict[str, float]:
        """
        Identify price range with lowest fees (for trading).
        
        Kalshi fees follow bell curve peaking at $0.50.
        Best trading opportunities are $0.55-$0.75 (lower fees, better liquidity).
        
        Returns:
            Dictionary with price ranges and fee info
        """
        prices = [i / 100 for i in range(5, 96)]  # $0.05 to $0.95
        
        results = []
        for price in prices:
            fee = self.kalshi_fee(contracts, price, "taker")
            results.append({'price': price, 'fee': fee})
        
        # Find minimum fee
        min_fee = min(r['fee'] for r in results)
        max_fee = max(r['fee'] for r in results)
        
        # Identify sweet range (within 50% of min)
        sweet_threshold = min_fee * 1.5
        sweet_range = [r for r in results if r['fee'] <= sweet_threshold]
        
        return {
            'min_fee_price': min(results, key=lambda x: x['fee'])['price'],
            'min_fee': min_fee,
            'max_fee': max_fee,
            'sweet_range_start': sweet_range[0]['price'] if sweet_range else 0.50,
            'sweet_range_end': sweet_range[-1]['price'] if sweet_range else 0.50,
            'message': (
                f"Fees peak at $0.50 (${max_fee:.2f}). "
                f"Best range: ${sweet_range[0]['price']:.2f}-${sweet_range[-1]['price']:.2f} "
                f"(${sweet_range[0]['fee']:.2f}-${sweet_range[-1]['fee']:.2f})"
            )
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    calc = FeeCalculator()
    
    # Example 1: Calculate fee
    fee = calc.kalshi_fee(100, 0.65, "taker")
    print(f"\n100 contracts @ $0.65: ${fee:.2f} fee")
    
    # Example 2: Complete PnL
    pnl = calc.calculate_pnl(0.60, 0.70, 100)
    print(f"\n{pnl}")
    
    # Example 3: Required exit for target profit
    exit_price = calc.required_exit_price_for_target_profit(0.65, 2.50, 100)
    print(f"\nFor $2.50 profit from $0.65 entry: ${exit_price:.4f} exit needed")
    
    # Example 4: Breakeven
    breakeven = calc.breakeven_exit_price(0.60, 100)
    move_pct = calc.breakeven_price_move_percent(0.60, 100)
    print(f"\nBreakeven @ $0.60: ${breakeven:.4f} ({move_pct:.2%} move needed)")
    
    # Example 5: Sweet price range
    sweet = calc.sweet_price_range(100)
    print(f"\n{sweet['message']}")
