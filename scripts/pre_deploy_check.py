#!/usr/bin/env python3
"""
Pre-deployment validation checklist.
Ensures all components are ready before going live.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clients.kalshi_client import KalshiClient
from src.trading.fee_calculator import FeeCalculator
from src.trading.risk_manager import RiskManager


class DeploymentValidator:
    """Validates system is ready for deployment."""

    def __init__(self):
        self.checks_passed = []
        self.checks_failed = []

    def check(self, name: str, passed: bool, details: str = ""):
        """Record check result."""
        if passed:
            self.checks_passed.append(name)
            print(f"✅ {name}")
            if details:
                print(f"   {details}")
        else:
            self.checks_failed.append(name)
            print(f"❌ {name}")
            if details:
                print(f"   {details}")

    def check_environment_variables(self):
        """Check required environment variables."""
        print("\n🔐 Checking Environment Variables...")

        required_vars = [
            "KALSHI_API_KEY",
            "KALSHI_PRIVATE_KEY_PATH",
            "SPIKE_THRESHOLD",
            "TARGET_PROFIT_USD",
            "TARGET_LOSS_USD",
        ]

        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        self.check(
            "Environment Variables",
            len(missing) == 0,
            f"Missing: {', '.join(missing)}" if missing else "All present",
        )

    def check_files_exist(self):
        """Check required files exist."""
        print("\n📁 Checking Required Files...")

        required_files = [
            "src/config.py",
            "src/clients/kalshi_client.py",
            "src/trading/fee_calculator.py",
            "src/trading/risk_manager.py",
            "src/trading/spike_detector.py",
            "src/trading/position_manager.py",
            "test.py",
        ]

        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)

        self.check(
            "Required Files",
            len(missing) == 0,
            f"Missing: {', '.join(missing)}" if missing else "All present",
        )

        # Check private key
        key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "keys/private_key.pem")
        key_exists = Path(key_path).exists()

        self.check("Private Key File", key_exists, f"Path: {key_path}")

    async def check_api_connection(self):
        """Check API connectivity."""
        print("\n🔌 Checking API Connection...")

        try:
            config = Config(platform="kalshi")
            async with KalshiClient(config) as client:
                authenticated = await client.authenticate()
                self.check("API Authentication", authenticated)

                if authenticated:
                    balance = await client.get_balance()
                    self.check(
                        "Balance Retrieval", balance >= 0, f"Balance: ${balance:.2f}"
                    )

                    markets = await client.get_markets(limit=5)
                    self.check(
                        "Market Data",
                        len(markets) > 0,
                        f"Retrieved {len(markets)} markets",
                    )

        except Exception as e:
            self.check("API Connection", False, str(e))

    def check_configuration(self):
        """Check configuration values."""
        print("\n⚙️  Checking Configuration...")

        try:
            config = Config(platform="kalshi")

            # Check spike threshold
            self.check(
                "Spike Threshold",
                0.02 <= config.SPIKE_THRESHOLD <= 0.10,
                f"Value: {config.SPIKE_THRESHOLD:.1%}",
            )

            # Check profit target
            self.check(
                "Profit Target",
                config.TARGET_PROFIT_USD > 0,
                f"Value: ${config.TARGET_PROFIT_USD:.2f}",
            )

            # Check stop loss
            self.check(
                "Stop Loss",
                config.TARGET_LOSS_USD < 0,
                f"Value: ${config.TARGET_LOSS_USD:.2f}",
            )

            # Check daily loss limit
            self.check(
                "Daily Loss Limit",
                0.05 <= config.MAX_DAILY_LOSS_PCT <= 0.30,
                f"Value: {config.MAX_DAILY_LOSS_PCT:.1%}",
            )

            # Check trade size
            self.check(
                "Trade Size",
                10 <= config.TRADE_UNIT <= 1000,
                f"Value: {config.TRADE_UNIT} contracts",
            )

        except Exception as e:
            self.check("Configuration", False, str(e))

    def check_risk_calculations(self):
        """Check risk and fee calculations."""
        print("\n🧮 Checking Calculations...")

        try:
            calc = FeeCalculator()

            # Test fee calculation
            fee = calc.kalshi_fee(100, 0.65, "taker")
            self.check(
                "Fee Calculation",
                1.0 <= fee <= 2.0,  # Expect ~$1.60 for this
                f"Fee for 100@$0.65: ${fee:.2f}",
            )

            # Test P&L
            pnl = calc.calculate_pnl(0.60, 0.68, 100)
            self.check(
                "P&L Calculation", pnl.net_profit > 0, f"Net P&L: ${pnl.net_profit:.2f}"
            )

            # Test breakeven
            breakeven = calc.breakeven_exit_price(0.60, 100)
            self.check(
                "Breakeven Calculation",
                breakeven > 0.60,  # Should be above entry
                f"Entry: $0.60, Breakeven: ${breakeven:.4f}",
            )

        except Exception as e:
            self.check("Risk Calculations", False, str(e))

    def check_paper_trading_history(self):
        """Check if paper trading data exists."""
        print("\n📊 Checking Paper Trading History...")

        history_file = Path("logs/paper_trading_history.json")

        if history_file.exists():
            import json

            with open(history_file) as f:
                trades = json.load(f)

            self.check(
                "Paper Trading History",
                len(trades) >= 10,
                f"Found {len(trades)} trades (recommend 20+ before live)",
            )

            if trades:
                total_pnl = sum(t["net_pnl"] for t in trades)
                win_rate = (
                    sum(1 for t in trades if t["net_pnl"] > 0) / len(trades) * 100
                )

                self.check(
                    "Paper Trading P&L",
                    total_pnl > 0,
                    f"Total: ${total_pnl:+.2f}, Win Rate: {win_rate:.1f}%",
                )
        else:
            self.check(
                "Paper Trading History",
                False,
                "No paper trading data found. Run paper trading first!",
            )

    async def run_all_checks(self):
        """Run all validation checks."""
        print("=" * 70)
        print("🚀 PRE-DEPLOYMENT VALIDATION")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Run all checks
        self.check_environment_variables()
        self.check_files_exist()
        await self.check_api_connection()
        self.check_configuration()
        self.check_risk_calculations()
        self.check_paper_trading_history()

        # Summary
        print("\n" + "=" * 70)
        print("📋 VALIDATION SUMMARY")
        print("=" * 70)

        total = len(self.checks_passed) + len(self.checks_failed)
        passed = len(self.checks_passed)

        print(f"Checks Passed: {passed}/{total}")
        print(f"Checks Failed: {len(self.checks_failed)}/{total}")

        if self.checks_failed:
            print("\n❌ Failed Checks:")
            for check in self.checks_failed:
                print(f"  - {check}")

        print("\n" + "=" * 70)

        if len(self.checks_failed) == 0:
            print("✅ READY FOR DEPLOYMENT")
            print("=" * 70)
            return 0
        else:
            print("⚠️  NOT READY - Fix failed checks before deploying")
            print("=" * 70)
            return 1


async def main():
    """Run validation."""
    validator = DeploymentValidator()
    exit_code = await validator.run_all_checks()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
