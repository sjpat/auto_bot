# src/trading/position_manager.py (modified)
from datetime import datetime
import logging
from src.trading.fee_calculator import FeeCalculator
from typing import List

logger = logging.getLogger(__name__)


class PositionManager:
    def __init__(self, platform: str, config, risk_manager=None):
        self.platform = platform
        self.config = config
        self.positions = {}  # position_id -> position_data
        self.risk_manager = risk_manager
        # Initialize fee calculator if Kalshi
        self.fee_calc = FeeCalculator() if platform == "kalshi" else None

    def add_position(self, order_id, market_id, entry_price, quantity, side):
        """Track a new position with fee accounting"""

        if self.platform == "kalshi":
            # Calculate entry fee
            entry_fee = self.fee_calc.kalshi_fee(quantity, entry_price)
            total_entry_cost = quantity * entry_price + entry_fee
        else:
            # Polymarket
            entry_fee = 0  # No platform fee
            total_entry_cost = quantity * entry_price

        self.positions[order_id] = {
            "id": order_id,
            "market_id": market_id,
            "entry_price": entry_price,
            "quantity": quantity,
            "side": side,
            "entry_fee": entry_fee,
            "total_entry_cost": total_entry_cost,
            "entry_time": datetime.now(),
            "current_price": entry_price,
            "status": "open",
        }

    def get_active_positions(self) -> List[dict]:
        """
        Get all active (open) positions.

        Returns:
            List of open position dictionaries
        """
        return [pos for pos in self.positions.values() if pos.get("status") == "open"]

    def evaluate_position_for_exit(
        self, position_id: str, current_price: float
    ) -> dict:
        """
        Determine if position should exit based on fees-adjusted targets

        For Kalshi: considers actual fees in profit calculation
        For Polymarket: uses percentage-based targets (legacy)
        """
        if position_id not in self.positions:
            return {"should_exit": False, "reason": "position_not_found"}

        pos = self.positions[position_id]
        pos["current_price"] = current_price

        if self.platform == "kalshi":
            return self._evaluate_kalshi_position(pos)
        else:
            return self._evaluate_polymarket_position(pos)

    def _evaluate_kalshi_position(self, pos: dict) -> dict:
        """Kalshi-specific exit logic (fee-aware)"""

        # Calculate P&L with fees
        pnl = self.fee_calc.calculate_pnl(
            entry_price=pos["entry_price"],
            exit_price=pos["current_price"],
            contracts=pos["quantity"],
        )

        # Check profit target
        if pnl.net_profit >= self.config.TARGET_PROFIT_USD:
            return {
                "should_exit": True,
                "reason": "profit_target_met",
                "net_pnl": pnl.net_profit,
                "gross_pnl": pnl.gross_profit,
                "fees": pnl.total_fees,
            }

        # Check stop loss
        if pnl.net_profit <= self.config.TARGET_LOSS_USD:
            return {
                "should_exit": True,
                "reason": "stop_loss_hit",
                "net_pnl": pnl.net_profit,
                "gross_pnl": pnl.gross_profit,
                "fees": pnl.total_fees,
            }

        # Check holding time limit
        holding_time = (datetime.now() - pos["entry_time"]).total_seconds()
        if holding_time > self.config.HOLDING_TIME_LIMIT:
            return {
                "should_exit": True,
                "reason": "holding_time_limit_reached",
                "net_pnl": pnl.net_profit,
                "gross_pnl": pnl.gross_profit,
                "fees": pnl.total_fees,
                "holding_seconds": holding_time,
            }

        return {"should_exit": False}

    def _evaluate_polymarket_position(self, pos: dict) -> dict:
        """Polymarket-specific exit logic (percentage-based)"""

        return_pct = (pos["current_price"] - pos["entry_price"]) / pos["entry_price"]

        # Check profit target
        if return_pct >= self.config.PCT_PROFIT:
            return {
                "should_exit": True,
                "reason": "profit_target_met",
                "return_pct": return_pct,
            }

        # Check stop loss
        if return_pct <= self.config.PCT_LOSS:
            return {
                "should_exit": True,
                "reason": "stop_loss_hit",
                "return_pct": return_pct,
            }

        # Check holding time
        holding_time = (datetime.now() - pos["entry_time"]).total_seconds()
        if holding_time > self.config.HOLDING_TIME_LIMIT:
            return {
                "should_exit": True,
                "reason": "holding_time_limit_reached",
                "return_pct": return_pct,
                "holding_seconds": holding_time,
            }

        return {"should_exit": False}

    def get_position_details(self, position_id: str) -> dict:
        """Get complete position details with current P&L"""
        if position_id not in self.positions:
            return None

        pos = self.positions[position_id]

        if self.platform == "kalshi":
            pnl = self.fee_calc.calculate_pnl(
                pos["entry_price"], pos["current_price"], pos["quantity"]
            )
            return {
                "id": pos["id"],
                "market_id": pos["market_id"],
                "entry_price": pos["entry_price"],
                "current_price": pos["current_price"],
                "quantity": pos["quantity"],
                "entry_fee": pos["entry_fee"],
                "gross_pnl": pnl.gross_profit,
                "total_fees": pnl.total_fees,
                "net_pnl": pnl.net_profit,
                "net_return_pct": pnl.net_return_pct,
                "holding_seconds": (datetime.now() - pos["entry_time"]).total_seconds(),
            }
        else:
            # Polymarket
            gross_pnl = (pos["current_price"] - pos["entry_price"]) * pos["quantity"]
            return {
                "id": pos["id"],
                "market_id": pos["market_id"],
                "entry_price": pos["entry_price"],
                "current_price": pos["current_price"],
                "quantity": pos["quantity"],
                "gross_pnl": gross_pnl,
                "return_pct": (pos["current_price"] - pos["entry_price"])
                / pos["entry_price"],
            }

    async def exit_position(self, position_id: str, exit_price: float):
        """Exit position and track settlement."""

        position = self.positions[position_id]
        exit_amount = exit_price * position["quantity"]

        # Exit the position
        logger.info(
            f"Exiting position {position_id}: "
            f"{position['quantity']} @ ${exit_price:.4f} = ${exit_amount:.2f}"
        )

        # Track settlement (funds settle in 1-2 business days)
        if self.risk_manager:
            await self.risk_manager.track_exit(
                position_id=position_id, exit_amount=exit_amount
            )

        # Remove from open positions
        del self.positions[position_id]

    def get_statistics(self) -> dict:
        """
        Get position manager statistics.

        Returns:
            Dictionary with statistics
        """
        active = self.get_active_positions()

        total_value = sum(pos["total_entry_cost"] for pos in active)

        return {
            "active_positions": len(active),
            "total_positions_tracked": len(self.positions),
            "total_value": total_value,
            "platform": self.platform,
        }

    def close_position(self, position_id: str, exit_price: float) -> dict:
        """
        Close a position and return final P&L.

        Args:
            position_id: Position identifier
            exit_price: Exit price

        Returns:
            Dictionary with position summary
        """
        if position_id not in self.positions:
            return {"success": False, "error": "position_not_found"}

        pos = self.positions[position_id]
        pos["status"] = "closed"
        pos["exit_price"] = exit_price
        pos["exit_time"] = datetime.now()

        # Calculate final P&L
        if self.platform == "kalshi":
            pnl = self.fee_calc.calculate_pnl(
                pos["entry_price"], exit_price, pos["quantity"]
            )

            result = {
                "success": True,
                "position_id": position_id,
                "market_id": pos["market_id"],
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "quantity": pos["quantity"],
                "gross_pnl": pnl.gross_profit,
                "total_fees": pnl.total_fees,
                "net_pnl": pnl.net_profit,
                "return_pct": pnl.return_pct,
                "holding_seconds": (
                    pos["exit_time"] - pos["entry_time"]
                ).total_seconds(),
            }
        else:
            pnl = self.calculate_pnl(pos, exit_price)
            result = {
                "success": True,
                "position_id": position_id,
                "market_id": pos["market_id"],
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "quantity": pos["quantity"],
                "pnl": pnl,
                "return_pct": (exit_price - pos["entry_price"]) / pos["entry_price"],
            }

        logger.info(
            f"📊 Position closed: {position_id} | "
            f"P&L: ${result.get('net_pnl', result.get('pnl', 0)):+.2f}"
        )

        # Remove from active positions
        self.remove_position(position_id)

        return result

    def calculate_pnl(self, position: dict, exit_price: float) -> float:
        """
        Calculate P&L for a position at given exit price.

        Args:
            position: Position dictionary
            exit_price: Exit price

        Returns:
            Net P&L in dollars
        """
        if self.platform == "kalshi":
            pnl = self.fee_calc.calculate_pnl(
                entry_price=position["entry_price"],
                exit_price=exit_price,
                contracts=position["quantity"],
            )
            return pnl.net_profit
        else:
            # Polymarket - simple calculation
            return (exit_price - position["entry_price"]) * position["quantity"]

    def update_position_price(self, position_id: str, current_price: float):
        """
        Update current price for a position.

        Args:
            position_id: Position identifier
            current_price: Current market price
        """
        if position_id in self.positions:
            self.positions[position_id]["current_price"] = current_price

    def remove_position(self, position_id: str):
        """
        Remove a position from tracking
        """

        if position_id in self.positions:
            logger.info(f"Removing position {position_id} from tracking.")
            del self.positions[position_id]
