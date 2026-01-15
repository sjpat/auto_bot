"""
Report generation for backtesting results
"""
from datetime import datetime
from typing import Optional
import json
from pathlib import Path

from .performance_metrics import BacktestResults

class BacktestReport:
    """Generate human-readable reports from backtest results"""
    
    def __init__(self, results: BacktestResults):
        self.results = results
    
    def print_summary(self):
        """Print formatted summary to console"""
        r = self.results
        
        print("\n" + "="*80)
        print("BACKTEST RESULTS SUMMARY")
        print("="*80)
        
        # Period
        print(f"\n📅 BACKTEST PERIOD")
        print(f"   Start: {r.start_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"   End:   {r.end_date.strftime('%Y-%m-%d %H:%M')}")
        duration = r.end_date - r.start_date
        print(f"   Duration: {duration.days} days, {duration.seconds // 3600} hours")
        
        # Account performance
        print(f"\n💰 ACCOUNT PERFORMANCE")
        print(f"   Starting Balance: ${r.starting_balance:,.2f}")
        print(f"   Final Balance:    ${r.final_balance:,.2f}")
        print(f"   Total P&L:        ${r.total_pnl:+,.2f}")
        return_pct = (r.final_balance - r.starting_balance) / r.starting_balance * 100
        print(f"   Return:           {return_pct:+.2f}%")
        print(f"   Total Fees Paid:  ${r.total_fees_paid:,.2f}")
        
        # Trading statistics
        print(f"\n📊 TRADING STATISTICS")
        print(f"   Total Trades:     {r.total_trades}")
        print(f"   Winning Trades:   {r.winning_trades} ({r.win_rate:.1%})")
        print(f"   Losing Trades:    {r.losing_trades}")
        print(f"   Profit Factor:    {r.profit_factor:.2f}")
        
        # P&L breakdown
        print(f"\n💵 P&L BREAKDOWN")
        print(f"   Gross Profit:     ${r.gross_profit:,.2f}")
        print(f"   Gross Loss:       ${r.gross_loss:,.2f}")
        print(f"   Average Win:      ${r.avg_win:,.2f}")
        print(f"   Average Loss:     ${r.avg_loss:,.2f}")
        print(f"   Largest Win:      ${r.largest_win:,.2f}")
        print(f"   Largest Loss:     ${r.largest_loss:,.2f}")
        
        # Risk metrics
        print(f"\n⚠️  RISK METRICS")
        print(f"   Max Drawdown:     ${r.max_drawdown:,.2f} ({r.max_drawdown_pct:.1%})")
        print(f"   Sharpe Ratio:     {r.sharpe_ratio:.2f}")
        print(f"   Max Consecutive Losses: {r.max_consecutive_losses}")
        
        # Spike detection
        print(f"\n🚨 SPIKE DETECTION")
        print(f"   Spikes Detected:  {r.spikes_detected}")
        print(f"   Spikes Traded:    {r.spikes_traded}")
        print(f"   Spikes Rejected:  {r.spikes_rejected}")
        print(f"   Spike Threshold:  {r.spike_threshold:.1%}")
        
        if r.rejection_reasons:
            print(f"\n   Rejection Reasons:")
            for reason, count in sorted(r.rejection_reasons.items(), key=lambda x: x[1], reverse=True):
                print(f"      {reason}: {count}")
        
        # Hold time
        if r.avg_hold_time is not None:
            hours = r.avg_hold_time.total_seconds() / 3600
            print(f"\n⏱️  TIMING")
            print(f"   Average Hold Time: {hours:.1f} hours")
        else:
            print(f"\n⏱️  TIMING")
            print(f"   Average Hold Time: N/A (no completed trades)")
        
        print("\n" + "="*80)
    
    def print_trade_log(self, limit: int = 20):
        """Print detailed trade log"""
        print(f"\n📋 TRADE LOG (showing last {limit} trades)")
        print("-"*100)
        print(f"{'#':<4} {'Market':<20} {'Entry':<12} {'Exit':<12} {'P&L':<12} {'Return':<10} {'Reason':<15}")
        print("-"*100)
        
        trades_to_show = self.results.trades[-limit:]
        
        for trade in trades_to_show:
            market_short = trade.market_id[:18] + "..." if len(trade.market_id) > 20 else trade.market_id
            entry_str = trade.entry_time.strftime('%m/%d %H:%M')
            exit_str = trade.exit_time.strftime('%m/%d %H:%M') if trade.exit_time else "Open"
            pnl_str = f"${trade.net_pnl:+.2f}" if trade.net_pnl else "-"
            return_str = f"{trade.return_pct:+.1%}" if trade.return_pct else "-"
            
            print(f"{trade.trade_id:<4} {market_short:<20} {entry_str:<12} {exit_str:<12} "
                  f"{pnl_str:<12} {return_str:<10} {trade.exit_reason or '-':<15}")
        
        print("-"*100)
    
    def save_to_json(self, filename: str):
        """Save results to JSON file"""
        output_dir = Path("data/backtest_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / filename
        
        # Convert results to dict
        data = {
            'summary': {
                'start_date': self.results.start_date.isoformat(),
                'end_date': self.results.end_date.isoformat(),
                'starting_balance': self.results.starting_balance,
                'final_balance': self.results.final_balance,
                'total_pnl': self.results.total_pnl,
                'win_rate': self.results.win_rate,
                'total_trades': self.results.total_trades,
                'profit_factor': self.results.profit_factor,
                'max_drawdown_pct': self.results.max_drawdown_pct,
                'sharpe_ratio': self.results.sharpe_ratio,
            },
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'market_id': t.market_id,
                    'entry_time': t.entry_time.isoformat(),
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'contracts': t.contracts,
                    'net_pnl': t.net_pnl,
                    'return_pct': t.return_pct,
                    'exit_reason': t.exit_reason,
                }
                for t in self.results.trades
            ],
            'equity_curve': [
                {
                    'timestamp': ts.isoformat(),
                    'balance': balance
                }
                for ts, balance in self.results.equity_curve
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Results saved to: {filepath}")
    
    def generate_html_report(self, filename: str = "backtest_report.html"):
        """Generate interactive HTML report with charts"""
        output_dir = Path("data/backtest_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / filename
        
        html = self._generate_html()
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        print(f"\n✅ HTML report saved to: {filepath}")
    
    def _generate_html(self) -> str:
        """Generate HTML content for report"""
        r = self.results
        
        # Prepare equity curve data for chart
        equity_data = [
            f"['{ts.strftime('%Y-%m-%d %H:%M')}', {balance}]"
            for ts, balance in r.equity_curve
        ]
        
        return_pct = (r.final_balance - r.starting_balance) / r.starting_balance * 100
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report - {r.start_date.date()} to {r.end_date.date()}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }}
        .metric-label {{
            color: #666;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }}
        .positive {{ color: #4CAF50; }}
        .negative {{ color: #f44336; }}
        .chart-container {{
            margin: 30px 0;
            position: relative;
            height: 400px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Backtest Results Report</h1>
        <p><strong>Period:</strong> {r.start_date.strftime('%Y-%m-%d')} to {r.end_date.strftime('%Y-%m-%d')}</p>
        <p><strong>Strategy:</strong> Spike Trading (Threshold: {r.spike_threshold:.1%})</p>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Total Return</div>
                <div class="metric-value {'positive' if return_pct > 0 else 'negative'}">{return_pct:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Final Balance</div>
                <div class="metric-value">${r.final_balance:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">{r.win_rate:.1%}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{r.total_trades}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{r.profit_factor:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">{r.max_drawdown_pct:.1%}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">{r.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Hold Time</div>
                <div class="metric-value">{r.avg_hold_time.total_seconds() / 3600 if r.avg_hold_time else 0:.1f}h</div>
            </div>
        </div>
        
        <h2>📈 Equity Curve</h2>
        <div class="chart-container">
            anvas id="equityChart"></canvas>
        </div>
        
        <h2>📋 Recent Trades</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Market</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>P&L</th>
                    <th>Return</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Add last 50 trades to table
        for trade in r.trades[-50:]:
            pnl_class = 'positive' if trade.net_pnl and trade.net_pnl > 0 else 'negative'
            html += f"""
                <tr>
                    <td>{trade.trade_id}</td>
                    <td>{trade.market_id[:30]}...</td>
                    <td>{trade.entry_time.strftime('%m/%d %H:%M')}</td>
                    <td>{trade.exit_time.strftime('%m/%d %H:%M') if trade.exit_time else 'Open'}</td>
                    <td class="{pnl_class}">${trade.net_pnl:+.2f}</td>
                    <td class="{pnl_class}">{trade.return_pct:+.1%}</td>
                    <td>{trade.exit_reason or '-'}</td>
                </tr>
"""
        
        html += f"""
            </tbody>
        </table>
    </div>
    
    <script>
        // Equity Curve Chart
        const ctx = document.getElementById('equityChart').getContext('2d');
        const equityChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: [{','.join([f"'{ts.strftime('%m/%d %H:%M')}'" for ts, _ in r.equity_curve])}],
                datasets: [{{
                    label: 'Account Balance',
                    data: [{','.join([str(balance) for _, balance in r.equity_curve])}],
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    borderWidth: 2,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: false,
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toLocaleString();
                            }}
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return '$' + context.parsed.y.toLocaleString();
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        return html
