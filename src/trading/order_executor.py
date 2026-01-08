import asyncio
import logging

logger = logging.getLogger(__name__)

class OrderExecutor:
    def __init__(self, client, config, risk_manager=None):
        self.client = client
        self.config = config
        self.risk_manager = risk_manager
    
    async def execute_order_with_slippage_check(
        self,
        market_id: str,
        side: str,
        quantity: int,
        requested_price: float
    ):
        """
        Execute order and validate fill for slippage.
        
        Returns: fill_info or None if rejected
        """
        
        # Submit order
        order = await self.client.create_order(
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=requested_price
        )
        
        logger.info(f"Order submitted: {order['order_id']} @ ${requested_price:.4f}")
        
        # Wait for fill
        fill_info = await self.track_fill(order['order_id'])
        actual_fill_price = fill_info['filled_price']
        
        # Check slippage
        if self.risk_manager:
            risk_check = await self.risk_manager.validate_fill(
                requested_price=requested_price,
                actual_fill_price=actual_fill_price,
                side=side,
                quantity=quantity,
                market_id=market_id
            )
            
            if not risk_check.passed:
                logger.warning(
                    f"Fill rejected due to slippage: {risk_check.reason}\n"
                    f"Requested: ${requested_price:.4f}, "
                    f"Actual: ${actual_fill_price:.4f}"
                )
                
                # Cancel order to avoid partial position
                try:
                    await self.client.cancel_order(order['order_id'])
                except:
                    pass
                
                return None
        
        logger.info(
            f"Fill accepted: {quantity} @ ${actual_fill_price:.4f} "
            f"(vs requested ${requested_price:.4f})"
        )
        
        return fill_info
    
    async def track_fill(self, order_id: str) -> dict:
        """Track order fill status."""
        max_wait_seconds = 10
        poll_interval_seconds = 0.5
        elapsed = 0
        
        while elapsed < max_wait_seconds:
            order = await self.client.get_order(order_id)
            
            if order['status'] in ['filled', 'partially_filled']:
                return {
                    'filled_price': order['avg_fill_price'],
                    'filled_quantity': order['filled_quantity'],
                    'status': order['status']
                }
            
            await asyncio.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
        
        raise TimeoutError(f"Order {order_id} did not fill within {max_wait_seconds}s")
    
    async def submit_order(
        self, 
        market_id: str, 
        side: str, 
        size: int, 
        price: float, 
        order_type: str = "limit"
    ) -> dict:
        """
        Submit an order with automatic retry logic.
        
        Returns: Dictionary with success status and order details or error
        """
        max_retries = 2
        retry_delay = 1.0
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Attempt to create order
                order = await self.client.create_order(
                    market_id=market_id,
                    side=side,
                    quantity=size,
                    price=price,
                    order_type=order_type
                )
                
                logger.info(f"Order submitted successfully: {order.get('order_id')}")
                return {
                    'success': True,
                    'order': order,
                    'order_id': order.get('order_id')
                }
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Order submission attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                
                # Wait before retrying (exponential backoff)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
        
        # All retries exhausted - return error dict instead of raising
        logger.error(
            f"Order submission failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )
        
        return {
            'success': False,
            'error': f"API Error: {str(last_error)}",
            'attempts': max_retries
        }
