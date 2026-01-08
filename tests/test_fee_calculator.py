# tests/test_fee_calculator.py

"""
Unit tests for FeeCalculator.

Tests the complete fee calculation and P&L logic for Kalshi.

Run: pytest tests/test_fee_calculator.py -v
"""

import pytest
from src.trading.fee_calculator import FeeCalculator, PnLInfo


class TestFeeCalculations:
    """Test basic fee calculations."""
    
    def test_taker_fee_formula(self):
        """Test taker fee formula: 0.07 × C × P × (1-P)."""
        calc = FeeCalculator()
        
        # 100 contracts @ $0.65
        # Fee = 0.07 × 100 × 0.65 × 0.35 = $1.5925 → $1.60
        fee = calc.kalshi_fee(100, 0.65, "taker")
        
        assert 1.59 <= fee <= 1.61, f"Expected ~$1.60, got ${fee:.2f}"
    
    def test_maker_fee_formula(self):
        """Test maker fee formula: 0.0175 × C × P × (1-P)."""
        calc = FeeCalculator()
        
        # 100 contracts @ $0.65
        # Fee = 0.0175 × 100 × 0.65 × 0.35 = $0.3981 → $0.40
        fee = calc.kalshi_fee(100, 0.65, "maker")
        
        assert 0.39 <= fee <= 0.41, f"Expected ~$0.40, got ${fee:.2f}"
    
    def test_fee_peak_at_50_percent(self):
        """Test that fees peak at $0.50 price."""
        calc = FeeCalculator()
        
        # 100 contracts at various prices
        fee_30 = calc.kalshi_fee(100, 0.30, "taker")
        fee_50 = calc.kalshi_fee(100, 0.50, "taker")
        fee_70 = calc.kalshi_fee(100, 0.70, "taker")
        
        # Fee should peak at $0.50
        assert fee_50 > fee_30
        assert fee_50 > fee_70
    
    def test_fee_symmetry(self):
        """Test that fees are symmetric around $0.50."""
        calc = FeeCalculator()
        
        # Fees should be equal for symmetric prices
        fee_30 = calc.kalshi_fee(100, 0.30, "taker")
        fee_70 = calc.kalshi_fee(100, 0.70, "taker")
        
        assert abs(round(fee_30 - fee_70,2)) < 0.01
        
        fee_20 = calc.kalshi_fee(100, 0.20, "taker")
        fee_80 = calc.kalshi_fee(100, 0.80, "taker")
        
        assert abs(round(fee_20 - fee_80,2)) < 0.01
    
    def test_fee_scales_with_quantity(self):
        """Test that fees scale with number of contracts."""
        calc = FeeCalculator()
        
        fee_100 = calc.kalshi_fee(100, 0.65, "taker")
        fee_200 = calc.kalshi_fee(200, 0.65, "taker")
        fee_50 = calc.kalshi_fee(50, 0.65, "taker")
        
        # Fees should be roughly proportional to quantity
        assert abs(round(fee_200 - fee_100 * 2,2)) < 0.01
        assert abs(round(fee_50 - fee_100 / 2, 2)) < 0.01
    
    def test_zero_fee_at_extremes(self):
        """Test that fees are zero at 0.00 and 1.00."""
        calc = FeeCalculator()
        
        fee_0 = calc.kalshi_fee(100, 0.00, "taker")
        fee_1 = calc.kalshi_fee(100, 1.00, "taker")
        
        assert fee_0 == 0.0
        assert fee_1 == 0.0


class TestEntryCost:
    """Test entry cost calculations."""
    
    def test_entry_cost_basic(self):
        """Test basic entry cost calculation."""
        calc = FeeCalculator()
        
        result = calc.entry_cost(100, 0.65, "taker")
        
        assert result['notional'] == 65.0
        assert 1.59 <= result['fee'] <= 1.61
        assert 66.59 <= result['total_cost'] <= 66.61
    
    def test_entry_cost_no_fee(self):
        """Test entry cost at extreme prices (no fee)."""
        calc = FeeCalculator()
        
        result = calc.entry_cost(100, 0.00, "taker")
        
        assert result['notional'] == 0.0
        assert result['fee'] == 0.0
        assert result['total_cost'] == 0.0
    
    def test_entry_cost_components(self):
        """Test entry cost component breakdown."""
        calc = FeeCalculator()
        
        result = calc.entry_cost(50, 0.50, "taker")
        
        # At $0.50, fee is maximized
        # Fee = 0.07 × 50 × 0.50 × 0.50 = $0.875
        assert result['notional'] == 25.0
        assert 0.87 <= result['fee'] <= 0.88
        assert abs(result['total_cost'] - (result['notional'] + result['fee'])) < 0.01


class TestExitRevenue:
    """Test exit revenue calculations."""
    
    def test_exit_revenue_basic(self):
        """Test basic exit revenue calculation."""
        calc = FeeCalculator()
        
        result = calc.exit_revenue(100, 0.70, "taker")
        
        assert result['notional'] == 70.0
        assert result['fee'] > 0
        assert result['net_revenue'] == result['notional'] - result['fee']
    
    def test_exit_revenue_less_than_notional(self):
        """Test that exit revenue is less than notional (fee deducted)."""
        calc = FeeCalculator()
        
        result = calc.exit_revenue(100, 0.70, "taker")
        
        assert result['net_revenue'] < result['notional']
        assert result['net_revenue'] == pytest.approx(68.53, abs=0.02)


class TestPnL:
    """Test complete P&L calculations."""
    
    def test_pnl_profitable_trade(self):
        """Test P&L for profitable trade."""
        calc = FeeCalculator()
        
        # Buy 100 @ $0.60, sell @ $0.70
        pnl = calc.calculate_pnl(0.60, 0.70, 100)
        
        # Entry: $60 + $1.68 = $61.68
        # Exit: $70 - $1.47 = $68.53
        # Net: $6.85
        assert pnl.entry_cost == pytest.approx(61.68, abs=0.01)
        assert pnl.exit_revenue == pytest.approx(68.53, abs=0.01)
        assert pnl.net_profit == pytest.approx(6.85, abs=0.01)
        assert pnl.return_pct > 0
    
    def test_pnl_unprofitable_trade(self):
        """Test P&L for unprofitable trade."""
        calc = FeeCalculator()
        
        # Buy 100 @ $0.70, sell @ $0.60
        pnl = calc.calculate_pnl(0.70, 0.60, 100)
        
        assert pnl.gross_profit < 0
        assert pnl.net_profit < pnl.gross_profit  # Fees make it worse
        assert pnl.return_pct < 0
    
    def test_pnl_small_move_negative(self):
        """Test that small moves result in losses due to fees."""
        calc = FeeCalculator()
        
        # Buy @ $0.50, sell @ $0.54 (4% move - should profit)
        pnl_54 = calc.calculate_pnl(0.50, 0.54, 100)
        
        # Actually, let's test 2% move which should be loss
        # Buy @ $0.50, sell @ $0.51 (2% move - insufficient for fees)
        pnl_2pct = calc.calculate_pnl(0.50, 0.51, 100)
        
        assert pnl_2pct.gross_profit > 0  # Gross is positive
        assert pnl_2pct.net_profit < 0    # But net is negative due to fees!
    
    def test_pnl_includes_both_fees(self):
        """Test that P&L includes both entry AND exit fees."""
        calc = FeeCalculator()
        
        pnl = calc.calculate_pnl(0.60, 0.70, 100)
        
        # Total fees should be entry + exit
        assert pnl.total_fees == pytest.approx(pnl.entry_fee + pnl.exit_fee, abs=0.01)
        
        # Entry fee should be ~$1.68
        assert pnl.entry_fee == pytest.approx(1.68, abs=0.01)
        
        # Exit fee should be ~$1.47
        assert pnl.exit_fee == pytest.approx(1.47, abs=0.01)


class TestBreakeven:
    """Test breakeven calculations."""
    
    def test_breakeven_exit_price(self):
        """Test breakeven exit price calculation."""
        calc = FeeCalculator()
        
        # Entry @ $0.60
        breakeven = calc.breakeven_exit_price(0.60, 100)
        
        # Should be above entry price (need to cover fees)
        assert breakeven > 0.60
        
        # Verify it actually breaks even
        pnl = calc.calculate_pnl(0.60, breakeven, 100)
        assert abs(pnl.net_profit) < 0.10  # Within $0.10
    
    def test_breakeven_price_move_percent(self):
        """Test minimum price move to break even."""
        calc = FeeCalculator()
        
        move_pct = calc.breakeven_price_move_percent(0.60, 100)
        
        # Should be positive (need upward move to break even)
        assert move_pct > 0
        
        # At $0.60, with fees, need about 5.6% move
        assert 0.04 < move_pct < 0.08
    
    def test_breakeven_varies_by_price(self):
        """Test that breakeven move varies by entry price."""
        calc = FeeCalculator()
        
        # Fees are lowest at extremes, highest at $0.50
        # So breakeven move should be different at different prices
        
        move_50 = calc.breakeven_price_move_percent(0.50, 100)
        move_65 = calc.breakeven_price_move_percent(0.65, 100)
        move_70 = calc.breakeven_price_move_percent(0.70, 100)
        
        # These should be different (not all equal)
        assert not (abs(move_50 - move_65) < 0.0001)


class TestTargetProfit:
    """Test target profit solver."""
    
    def test_required_exit_for_target_profit(self):
        """Test calculation of exit price for target profit."""
        calc = FeeCalculator()
        
        exit_price = calc.required_exit_price_for_target_profit(
            entry_price=0.65,
            target_profit_usd=2.50,
            contracts=100
        )
        
        # Should be above entry (need upward move)
        assert exit_price > 0.65
        
        # Verify it achieves target profit
        pnl = calc.calculate_pnl(0.65, exit_price, 100)
        assert abs(pnl.net_profit - 2.50) < 0.10  # Within $0.10
    
    def test_required_exit_for_zero_profit(self):
        """Test that zero profit requirement gives breakeven price."""
        calc = FeeCalculator()
        
        exit_zero = calc.required_exit_price_for_target_profit(
            entry_price=0.60,
            target_profit_usd=0.0,
            contracts=100
        )
        
        breakeven = calc.breakeven_exit_price(0.60, 100)
        
        assert abs(exit_zero - breakeven) < 0.001


class TestAnalysis:
    """Test analysis methods."""
    
    def test_fee_impact_analysis(self):
        """Test comprehensive fee impact analysis."""
        calc = FeeCalculator()
        
        analysis = calc.fee_impact_analysis(0.60, 0.70, 100)
        
        assert 'gross_profit' in analysis
        assert 'total_fees' in analysis
        assert 'net_profit' in analysis
        assert analysis['gross_profit'] > 0
        assert analysis['total_fees'] > 0
        assert analysis['net_profit'] < analysis['gross_profit']
    
    def test_sweet_price_range(self):
        """Test sweet price range identification."""
        calc = FeeCalculator()
        
        sweet = calc.sweet_price_range(100)
        
        assert 'sweet_range_start' in sweet
        assert 'sweet_range_end' in sweet
        assert sweet['sweet_range_start'] < sweet['sweet_range_end']
        
        # Sweet range should be somewhere in the middle (not extremes)
        assert 0.30 < sweet['sweet_range_start']
        assert sweet['sweet_range_end'] < 0.80


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_contracts(self):
        """Test fee calculation with zero contracts."""
        calc = FeeCalculator()
        
        fee = calc.kalshi_fee(0, 0.65, "taker")
        assert fee == 0.0
    
    def test_extreme_prices(self):
        """Test calculations at extreme prices."""
        calc = FeeCalculator()
        
        # At $0.00 (always lose)
        pnl_0 = calc.calculate_pnl(0.00, 0.05, 100)
        # Entry fee is 0, exit fee is small
        
        # At $1.00 (always win, but no fee)
        pnl_100 = calc.calculate_pnl(0.95, 1.00, 100)
        assert pnl_100.gross_profit > 0


class TestIntegration:
    """Integration tests combining multiple methods."""
    
    def test_realistic_trade_scenario(self):
        """Test realistic spike trading scenario."""
        calc = FeeCalculator()
        
        # Scenario: Market spikes from $0.60 to $0.68
        # Trader enters at $0.65 (catches spike partway through)
        # Sells at $0.73 (takes profit on continued momentum)
        
        entry_price = 0.65
        exit_price = 0.73
        contracts = 100
        
        # Calculate full P&L
        pnl = calc.calculate_pnl(entry_price, exit_price, contracts)
        
        assert pnl.gross_profit == pytest.approx(8.0, abs=0.01)
        assert pnl.net_profit == pytest.approx(6.85, abs=0.1)  # After ~$1.15 in fees
        assert pnl.return_pct == pytest.approx(0.10, abs=0.01)  # ~10% return
    
    def test_minimum_profitable_move(self):
        """Test what minimum price move is profitable."""
        calc = FeeCalculator()
        
        entry = 0.65
        
        # Try small moves until we find profitability
        for move_pct in [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]:
            exit_price = entry * (1 + move_pct)
            pnl = calc.calculate_pnl(entry, exit_price, 100)
            
            if pnl.net_profit > 0:
                print(f"At entry $0.65, minimum profitable move: {move_pct:.1%}")
                assert pnl.net_profit > 0
                break
        else:
            pytest.fail("No profitable move found up to 6%")


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def fee_calculator():
    """Provide FeeCalculator for tests."""
    return FeeCalculator()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
