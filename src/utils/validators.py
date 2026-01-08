"""
Validation functions for trading parameters.
"""

from typing import Optional, Dict, Any


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_price(price: float, min_price: float = 0.0, max_price: float = 1.0) -> bool:
    """
    Validate price is within acceptable range.
    
    Args:
        price: Price to validate
        min_price: Minimum allowed price
        max_price: Maximum allowed price
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If price is invalid
    """
    if not isinstance(price, (int, float)):
        raise ValidationError(f"Price must be numeric, got {type(price)}")
    
    if price < min_price:
        raise ValidationError(f"Price {price} below minimum {min_price}")
    
    if price > max_price:
        raise ValidationError(f"Price {price} above maximum {max_price}")
    
    return True


def validate_quantity(quantity: int, min_quantity: int = 1, max_quantity: int = 10000) -> bool:
    """
    Validate quantity is within acceptable range.
    
    Args:
        quantity: Quantity to validate
        min_quantity: Minimum allowed quantity
        max_quantity: Maximum allowed quantity
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If quantity is invalid
    """
    if not isinstance(quantity, int):
        raise ValidationError(f"Quantity must be integer, got {type(quantity)}")
    
    if quantity < min_quantity:
        raise ValidationError(f"Quantity {quantity} below minimum {min_quantity}")
    
    if quantity > max_quantity:
        raise ValidationError(f"Quantity {quantity} above maximum {max_quantity}")
    
    return True


def validate_balance(
    balance: float,
    required_amount: float,
    min_reserve: float = 0.0
) -> bool:
    """
    Validate sufficient balance for trade.
    
    Args:
        balance: Current balance
        required_amount: Amount needed for trade
        min_reserve: Minimum reserve to maintain
    
    Returns:
        True if sufficient balance
    
    Raises:
        ValidationError: If insufficient balance
    """
    if balance < required_amount + min_reserve:
        raise ValidationError(
            f"Insufficient balance: have ${balance:.2f}, "
            f"need ${required_amount:.2f} + ${min_reserve:.2f} reserve"
        )
    
    return True


def validate_market_id(market_id: str) -> bool:
    """
    Validate market ID format.
    
    Args:
        market_id: Market identifier
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If market ID is invalid
    """
    if not isinstance(market_id, str):
        raise ValidationError(f"Market ID must be string, got {type(market_id)}")
    
    if not market_id:
        raise ValidationError("Market ID cannot be empty")
    
    if len(market_id) < 3:
        raise ValidationError(f"Market ID too short: {market_id}")
    
    return True


def validate_order_params(
    side: str,
    quantity: int,
    price: Optional[float] = None,
    order_type: str = "limit"
) -> bool:
    """
    Validate order parameters.
    
    Args:
        side: Order side ('buy' or 'sell')
        quantity: Number of contracts
        price: Limit price (required for limit orders)
        order_type: Order type ('limit' or 'market')
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If parameters are invalid
    """
    # Validate side
    if side.lower() not in ['buy', 'sell']:
        raise ValidationError(f"Invalid order side: {side} (must be 'buy' or 'sell')")
    
    # Validate quantity
    validate_quantity(quantity)
    
    # Validate order type
    if order_type.lower() not in ['limit', 'market']:
        raise ValidationError(f"Invalid order type: {order_type} (must be 'limit' or 'market')")
    
    # Validate price for limit orders
    if order_type.lower() == 'limit':
        if price is None:
            raise ValidationError("Price required for limit orders")
        validate_price(price)
    
    return True


def validate_slippage(
    requested_price: float,
    actual_price: float,
    max_slippage_pct: float = 0.025
) -> bool:
    """
    Validate slippage is within tolerance.
    
    Args:
        requested_price: Requested price
        actual_price: Actual fill price
        max_slippage_pct: Maximum allowed slippage (default 2.5%)
    
    Returns:
        True if slippage acceptable
    
    Raises:
        ValidationError: If slippage exceeds tolerance
    """
    if requested_price <= 0:
        raise ValidationError(f"Invalid requested price: {requested_price}")
    
    slippage = abs(actual_price - requested_price) / requested_price
    
    if slippage > max_slippage_pct:
        raise ValidationError(
            f"Slippage {slippage:.2%} exceeds maximum {max_slippage_pct:.2%} "
            f"(requested: ${requested_price:.4f}, actual: ${actual_price:.4f})"
        )
    
    return True


def validate_profit_target(
    entry_cost: float,
    target_profit: float,
    max_return_pct: float = 5.0
) -> bool:
    """
    Validate profit target is reasonable.
    
    Args:
        entry_cost: Entry cost of position
        target_profit: Target profit amount
        max_return_pct: Maximum return percentage (default 500%)
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If target is unreasonable
    """
    if entry_cost <= 0:
        raise ValidationError(f"Invalid entry cost: {entry_cost}")
    
    return_pct = target_profit / entry_cost
    
    if return_pct > max_return_pct:
        raise ValidationError(
            f"Target profit too high: {return_pct:.1%} exceeds maximum {max_return_pct:.1%}"
        )
    
    return True


def validate_position_size(
    position_cost: float,
    account_balance: float,
    max_position_pct: float = 0.10
) -> bool:
    """
    Validate position size relative to account.
    
    Args:
        position_cost: Cost of position
        account_balance: Total account balance
        max_position_pct: Maximum position as % of account (default 10%)
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If position too large
    """
    if account_balance <= 0:
        raise ValidationError(f"Invalid account balance: {account_balance}")
    
    position_pct = position_cost / account_balance
    
    if position_pct > max_position_pct:
        raise ValidationError(
            f"Position size {position_pct:.1%} exceeds maximum {max_position_pct:.1%} "
            f"(cost: ${position_cost:.2f}, balance: ${account_balance:.2f})"
        )
    
    return True


def validate_fee(fee: float, max_fee_pct: float = 0.10) -> bool:
    """
    Validate fee is reasonable.
    
    Args:
        fee: Fee amount
        max_fee_pct: Maximum fee as percentage (default 10%)
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If fee too high
    """
    if fee < 0:
        raise ValidationError(f"Fee cannot be negative: {fee}")
    
    # Note: This is a basic check. Real validation would compare to notional value
    if fee > max_fee_pct:
        raise ValidationError(f"Fee {fee:.2f} seems unreasonably high")
    
    return True


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration dictionary.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If config is invalid
    """
    required_keys = [
        'SPIKE_THRESHOLD',
        'TARGET_PROFIT_USD',
        'TARGET_LOSS_USD',
        'TRADE_UNIT',
        'MAX_DAILY_LOSS_PCT',
        'MAX_SLIPPAGE_TOLERANCE',
        'MIN_ACCOUNT_BALANCE'
    ]
    
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        raise ValidationError(f"Missing required config keys: {missing_keys}")
    
    # Validate individual parameters
    if config['SPIKE_THRESHOLD'] <= 0 or config['SPIKE_THRESHOLD'] > 1:
        raise ValidationError(f"Invalid SPIKE_THRESHOLD: {config['SPIKE_THRESHOLD']}")
    
    if config['TRADE_UNIT'] <= 0:
        raise ValidationError(f"Invalid TRADE_UNIT: {config['TRADE_UNIT']}")
    
    if config['MAX_DAILY_LOSS_PCT'] <= 0 or config['MAX_DAILY_LOSS_PCT'] > 1:
        raise ValidationError(f"Invalid MAX_DAILY_LOSS_PCT: {config['MAX_DAILY_LOSS_PCT']}")
    
    if config['MAX_SLIPPAGE_TOLERANCE'] <= 0 or config['MAX_SLIPPAGE_TOLERANCE'] > 1:
        raise ValidationError(f"Invalid MAX_SLIPPAGE_TOLERANCE: {config['MAX_SLIPPAGE_TOLERANCE']}")
    
    return True
