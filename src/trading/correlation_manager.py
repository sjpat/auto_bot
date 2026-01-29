import logging
from typing import List, Dict, Tuple
from src.models.position import Position

logger = logging.getLogger(__name__)


class CorrelationManager:
    """
    Manages correlation risk by limiting exposure to specific event groups.

    Example:
    - Markets: "FED-DEC-RATE-4.5", "FED-DEC-RATE-4.75"
    - Group: "FED"
    - If exposure to "FED" > limit, reject new trades in that group.
    """

    def __init__(self, config, position_manager):
        self.config = config
        self.position_manager = position_manager
        self.max_exposure = config.MAX_EVENT_EXPOSURE_USD
        self.logger = logging.getLogger(__name__)

    def get_event_group(self, market_id: str) -> str:
        """
        Extract event group from market ID.
        Heuristic: Take the first part of the ticker before the hyphen.
        """
        if not market_id:
            return "UNKNOWN"

        # Common patterns: "KX-INFL-...", "NBA-...", "FED-..."
        parts = market_id.split("-")
        if len(parts) > 1:
            # Special case for Kalshi "KX-" prefix
            if parts[0] == "KX" and len(parts) > 2:
                return f"{parts[0]}-{parts[1]}"
            return parts[0]
        return market_id

    def check_exposure(self, market_id: str, potential_cost: float) -> Tuple[bool, str]:
        """
        Check if adding this trade would exceed the event exposure limit.

        Args:
            market_id: The market we want to trade
            potential_cost: The cost of the new trade (USD)

        Returns:
            (passed: bool, reason: str)
        """
        target_group = self.get_event_group(market_id)
        current_exposure = 0.0

        # Calculate current exposure for this group
        positions = self.position_manager.get_active_positions()
        for position in positions:
            # Handle both object and dict access for compatibility
            pos_market_id = getattr(position, "market_id", None) or position.get(
                "market_id"
            )

            if self.get_event_group(pos_market_id) == target_group:
                # Use entry cost as exposure metric
                cost = getattr(position, "entry_cost", 0.0)
                if cost == 0.0:
                    # Fallback calculation
                    qty = getattr(position, "quantity", 0) or position.get(
                        "quantity", 0
                    )
                    price = getattr(position, "entry_price", 0) or position.get(
                        "entry_price", 0
                    )
                    cost = qty * price

                current_exposure += cost

        # Check limit
        if current_exposure + potential_cost > self.max_exposure:
            msg = (
                f"Correlation limit hit for '{target_group}'. "
                f"Current: ${current_exposure:.2f} + New: ${potential_cost:.2f} > Limit: ${self.max_exposure:.2f}"
            )
            return False, msg

        return True, "OK"
