"""
Formatting utilities for display and logging.
"""

from datetime import datetime, timedelta
from typing import Union, Optional


def format_price(price: float, decimals: int = 4) -> str:
    """
    Format price with specified decimals.

    Args:
        price: Price value
        decimals: Number of decimal places

    Returns:
        Formatted price string

    Example:
        >>> format_price(0.6543)
        '$0.6543'
    """
    return f"${price:.{decimals}f}"


def format_quantity(quantity: int, abbreviate: bool = False) -> str:
    """
    Format quantity with optional abbreviation.

    Args:
        quantity: Quantity value
        abbreviate: Use K/M abbreviations for large numbers

    Returns:
        Formatted quantity string

    Example:
        >>> format_quantity(1500, abbreviate=True)
        '1.5K'
    """
    if not abbreviate:
        return f"{quantity:,}"

    if quantity >= 1_000_000:
        return f"{quantity / 1_000_000:.1f}M"
    elif quantity >= 1_000:
        return f"{quantity / 1_000:.1f}K"
    else:
        return str(quantity)


def format_percentage(
    value: float, decimals: int = 2, include_sign: bool = True
) -> str:
    """
    Format percentage value.

    Args:
        value: Percentage value (0.05 = 5%)
        decimals: Number of decimal places
        include_sign: Include + sign for positive values

    Returns:
        Formatted percentage string

    Example:
        >>> format_percentage(0.0543)
        '+5.43%'
        >>> format_percentage(-0.025)
        '-2.50%'
    """
    pct = value * 100
    sign = "+" if include_sign and pct > 0 else ""
    return f"{sign}{pct:.{decimals}f}%"


def format_currency(
    amount: float,
    decimals: int = 2,
    include_sign: bool = True,
    abbreviate: bool = False,
) -> str:
    """
    Format currency amount.

    Args:
        amount: Dollar amount
        decimals: Number of decimal places
        include_sign: Include + sign for positive values
        abbreviate: Use K/M abbreviations

    Returns:
        Formatted currency string

    Example:
        >>> format_currency(1234.56)
        '$1,234.56'
        >>> format_currency(1500000, abbreviate=True)
        '$1.5M'
    """
    sign = "+" if include_sign and amount > 0 else ""

    if abbreviate:
        if abs(amount) >= 1_000_000:
            return f"{sign}${abs(amount) / 1_000_000:.1f}M"
        elif abs(amount) >= 1_000:
            return f"{sign}${abs(amount) / 1_000:.1f}K"

    return (
        f"{sign}${abs(amount):,.{decimals}f}"
        if amount >= 0
        else f"-${abs(amount):,.{decimals}f}"
    )


def format_timestamp(
    timestamp: Union[datetime, float, int], format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format timestamp to string.

    Args:
        timestamp: Datetime object or Unix timestamp
        format_str: strftime format string

    Returns:
        Formatted timestamp string

    Example:
        >>> format_timestamp(datetime.now())
        '2026-01-07 08:00:00'
    """
    if isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp)

    return timestamp.strftime(format_str)


def format_duration(seconds: float, short: bool = False) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds
        short: Use short format (e.g., '1h 30m' vs '1 hour 30 minutes')

    Returns:
        Formatted duration string

    Example:
        >>> format_duration(3665)
        '1h 1m 5s'
        >>> format_duration(3665, short=False)
        '1 hour 1 minute 5 seconds'
    """
    if seconds < 0:
        return "0s" if short else "0 seconds"

    delta = timedelta(seconds=seconds)

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if short:
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)
    else:
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        return " ".join(parts)


def format_change(
    old_value: float, new_value: float, decimals: int = 2, show_percentage: bool = True
) -> str:
    """
    Format change between two values.

    Args:
        old_value: Original value
        new_value: New value
        decimals: Number of decimal places
        show_percentage: Show percentage change

    Returns:
        Formatted change string

    Example:
        >>> format_change(100, 115)
        '+15.00 (+15.00%)'
    """
    change = new_value - old_value
    change_str = format_currency(change, decimals=decimals)

    if show_percentage and old_value != 0:
        pct = change / old_value
        pct_str = format_percentage(pct, decimals=decimals)
        return f"{change_str} ({pct_str})"

    return change_str


def format_table_row(columns: list, widths: list, align: Optional[list] = None) -> str:
    """
    Format a table row with specified column widths.

    Args:
        columns: List of column values
        widths: List of column widths
        align: List of alignments ('left', 'right', 'center')

    Returns:
        Formatted table row string

    Example:
        >>> format_table_row(['Name', 'Price', 'Change'], [15, 10, 10])
        'Name           Price      Change    '
    """
    if align is None:
        align = ["left"] * len(columns)

    parts = []
    for col, width, alignment in zip(columns, widths, align):
        col_str = str(col)
        if alignment == "right":
            parts.append(col_str.rjust(width))
        elif alignment == "center":
            parts.append(col_str.center(width))
        else:
            parts.append(col_str.ljust(width))

    return " ".join(parts)


def format_order_summary(side: str, quantity: int, price: float, market_id: str) -> str:
    """
    Format order summary for logging.

    Args:
        side: Order side
        quantity: Quantity
        price: Price
        market_id: Market ID

    Returns:
        Formatted order summary

    Example:
        >>> format_order_summary('buy', 100, 0.65, 'market_123')
        '📈 BUY 100 @ $0.6500 (market_123...)'
    """
    emoji = "📈" if side.lower() == "buy" else "📉"
    return (
        f"{emoji} {side.upper()} {quantity} @ {format_price(price)} "
        f"({market_id[:12]}...)"
    )


def format_position_summary(
    position_id: str,
    side: str,
    quantity: int,
    entry_price: float,
    current_price: float,
    pnl: float,
    return_pct: float,
) -> str:
    """
    Format position summary for logging.

    Args:
        position_id: Position ID
        side: Position side
        quantity: Quantity
        entry_price: Entry price
        current_price: Current price
        pnl: Profit/loss
        return_pct: Return percentage

    Returns:
        Formatted position summary

    Example:
        >>> format_position_summary('pos_1', 'long', 100, 0.60, 0.68, 6.85, 0.11)
        'pos_1 | LONG 100 | Entry: $0.6000 → Current: $0.6800 | P&L: +$6.85 (+11.00%)'
    """
    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
    return (
        f"{emoji} {position_id} | {side.upper()} {quantity} | "
        f"Entry: {format_price(entry_price)} → Current: {format_price(current_price)} | "
        f"P&L: {format_currency(pnl)} ({format_percentage(return_pct)})"
    )
