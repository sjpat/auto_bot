"""
Enhanced market filtering for demo mode optimization.
"""

from datetime import datetime
from typing import List
import logging

logger = logging.getLogger(__name__)


class MarketFilter:
    """Filter and rank markets for trading opportunities."""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def filter_tradeable_markets(self, markets: List) -> List:
        """
        Apply comprehensive filtering for demo mode.

        Returns markets suitable for trading given demo constraints.
        """
        tradeable = []
        filter_stats = {
            "total": len(markets),
            "keyword": 0,
            "no_price": 0,
            "expired": 0,
            "too_far": 0,
            "extreme_price": 0,
            "wide_spread": 0,
            "passed": 0,
        }

        for market in markets:
            # Filter 0: Keyword filter
            if self.config.TARGET_EVENT_KEYWORDS:
                search_text = (market.title + " " + (market.category or "")).lower()
                if not any(
                    keyword.lower() in search_text
                    for keyword in self.config.TARGET_EVENT_KEYWORDS
                ):
                    filter_stats["keyword"] += 1
                    continue

            # Filter 1: Must have a price
            if market.last_price_cents == 0:
                filter_stats["no_price"] += 1
                continue

            # Filter 2: Time to expiry (30min to 7 days)
            hours_to_close = market.time_to_expiry_seconds / 3600
            if hours_to_close < 0.5:  # < 30 minutes
                filter_stats["expired"] += 1
                continue
            if hours_to_close > 168:  # > 7 days
                filter_stats["too_far"] += 1
                continue

            # Filter 3: Price not at extremes (0.10 to 0.90)
            price = market.price
            if not (0.10 < price < 0.90):
                filter_stats["extreme_price"] += 1
                continue

            # Filter 4: Reasonable bid-ask spread (< 50%)
            if market.best_ask_cents > 0 and market.best_bid_cents > 0:
                mid_price_cents = (market.best_ask_cents + market.best_bid_cents) / 2
                if mid_price_cents > 0:
                    spread_pct = (
                        market.best_ask_cents - market.best_bid_cents
                    ) / mid_price_cents
                    if spread_pct > 0.50:  # 50% spread
                        filter_stats["wide_spread"] += 1
                        continue

            # Passed all filters
            filter_stats["passed"] += 1
            tradeable.append(market)

        # Log filtering results
        self.logger.info(
            f"Market Filtering: {filter_stats['passed']}/{filter_stats['total']} passed | "
            f"Rejected: {filter_stats['keyword']} keyword, "
            f"{filter_stats['no_price']} no-price, "
            f"{filter_stats['expired']} expired, "
            f"{filter_stats['too_far']} too-far, "
            f"{filter_stats['extreme_price']} extreme-price, "
            f"{filter_stats['wide_spread']} wide-spread"
        )

        return tradeable

    def rank_markets_by_opportunity(self, markets: List, spike_detector) -> List:
        """
        Rank markets by trading opportunity quality.

        Considers: price history depth, volatility, time to expiry.
        """
        ranked = []

        for market in markets:
            score = self._calculate_opportunity_score(market, spike_detector)
            ranked.append((market, score))

        # Sort by score (highest first)
        ranked.sort(key=lambda x: x[1], reverse=True)

        # Log top opportunities
        if ranked:
            self.logger.debug(f"Top 3 opportunities:")
            for market, score in ranked[:3]:
                self.logger.debug(
                    f"  {market.market_id}: score={score:.2f}, "
                    f"price=${market.price:.4f}, "
                    f"expires_in={market.time_to_expiry_seconds/3600:.1f}h"
                )

        return [m for m, score in ranked]

    def _calculate_opportunity_score(self, market, spike_detector) -> float:
        """Calculate opportunity score (0-100)."""
        score = 0.0

        # Factor 1: Price history depth (0-30 points)
        history = spike_detector.price_history.get(market.market_id, [])
        history_score = min(30, len(history) / 100 * 30)
        score += history_score

        # Factor 2: Recent volatility (0-30 points)
        if len(history) >= 10:
            recent_prices = [p[0] for p in history[-10:]]
            volatility = max(recent_prices) - min(recent_prices)
            volatility_score = min(30, volatility / market.price * 100)
            score += volatility_score

        # Factor 3: Time to expiry (0-20 points)
        # Prefer markets 2-48 hours from close
        hours_to_close = market.time_to_expiry_seconds / 3600
        if 2 < hours_to_close < 48:
            time_score = 20
        elif hours_to_close < 2:
            time_score = 10  # Too close
        else:
            time_score = 5  # Too far
        score += time_score

        # Factor 4: Liquidity (0-20 points)
        liquidity_score = min(20, market.liquidity_usd / 10.0 * 20)
        score += liquidity_score

        return score
