# test.py - Main execution file

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional
import os

from src.config import Config
from src.logger import setup_logger
# from src.clients.polymarket_client import PolymarketClient
from src.clients.kalshi_client import KalshiClient
from src.trading.spike_detector import SpikeDetector
from src.trading.order_executor import OrderExecutor
from src.trading.position_manager import PositionManager
from src.trading.risk_manager import RiskManager
from src.clients.kalshi_client import KalshiClient
from src.trading.fee_calculator import FeeCalculator
from src.trading.market_filter import MarketFilter


class TradingBot:
    """Main orchestration class for spike trading bot"""
    
    def __init__(self, platform: str = "kalshi"):
        """
        Initialize bot for specific platform
        
        Args:
            platform: "polymarket" or "kalshi"
        """
        self.platform = platform
        self.config = Config(platform=platform)
        self.logger = setup_logger(
            name="TradingBot",
            log_file=self.config.LOG_FILE,
            level=self.config.LOG_LEVEL
        )
        self.market_filter = MarketFilter(config=self.config)

        # Initialize clients based on platform
        if platform == "polymarket":
            # self.client = PolymarketClient(config=self.config)
            raise ValueError("Polymarket client not implemented yet")
        elif platform == "kalshi":
            self.client = KalshiClient(config=self.config)
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        if self.config.PAPER_TRADING:
            from src.trading.paper_trading import PaperTradingClient
            
            self.client = PaperTradingClient(
                kalshi_client=self.client,
                starting_balance=self.config.PAPER_STARTING_BALANCE,
                simulate_slippage=self.config.PAPER_SIMULATE_SLIPPAGE,
                max_slippage_pct=self.config.PAPER_MAX_SLIPPAGE_PCT,
                save_history=self.config.PAPER_SAVE_HISTORY,
                history_file=self.config.PAPER_HISTORY_FILE
            )
            
            self.logger.info("📄 PAPER TRADING MODE: Orders will be simulated")
        else:
            self.logger.warning("💰 LIVE TRADING MODE: Orders will use REAL MONEY")


        # Initialize fee calculator
        if platform == "kalshi":
            self.fee_calculator = FeeCalculator()
        else:
            self.fee_calculator = None  # Placeholder for other platforms

        # Initialize trading components (platform-agnostic)
        self.spike_detector = SpikeDetector(config=self.config)
        self.order_executor = OrderExecutor(
            client=self.client,
            config=self.config
        )
        self.position_manager = PositionManager(
            platform=platform,
            config=self.config,
        )
        self.risk_manager = RiskManager(
            client=self.client,
            config=self.config,
            fee_calculator=self.fee_calculator
        )

        self.loop_count = 0
        self.running = False
    
    async def initialize(self):
        try:
            self.logger.info(f"Initializing {self.platform} bot...")
            
            # Verify API connection
            await self.client.verify_connection()
            self.logger.info("✅ API connection verified")
            
            # Check balance
            balance = await self.client.get_balance()
            self.logger.info(f"Account balance: ${balance:.2f}")
            
            if balance < self.config.MIN_ACCOUNT_BALANCE:
                raise ValueError(f"Insufficient balance: ${balance:.2f}")
            
            # ✅ Initialize daily risk limits
            await self.risk_manager.initialize_daily(balance)
            self.logger.info("✅ Daily risk limits initialized")
            
            # Fetch initial market data
            markets = await self.client.get_markets(status="open", filter_untradeable=False)
            self.logger.info(f"Loaded {len(markets)} markets")
            
            self.running = True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            raise

    
    async def price_update_loop(self):
        """Continuously fetch and process price updates"""
        while self.running:
            try:
                # Get tradeable markets (filtered by platform)
                if self.platform == "kalshi":
                    markets = await self.get_tradeable_markets(
                        status="open",
                        filter_untradeable=False
                    )
                else:
                    markets = await self.client.get_markets()
                
                # Update price history
                for market in markets:
                    market_id = market.market_id if hasattr(market, 'market_id') else market.id
                    price = market.price if hasattr(market, 'price') else market.current_price
                    
                    self.spike_detector.add_price(
                        market_id=market_id,
                        price=price,
                        timestamp=datetime.now()
                    )
                
                self.logger.debug(f"Updated {len(markets)} markets")
                await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Price update error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def get_tradeable_markets(self, status, filter_untradeable: bool = True):
        """Get all open markets from Kalshi."""
        try:
            markets = await self.client.get_markets(status=status, filter_untradeable=filter_untradeable)
            
            self.logger.info(f"Found {len(markets)} open markets")
            return markets  # Return ALL markets, filter for trading later
            
        except Exception as e:
            self.logger.error(f"Failed to get markets: {e}")
            return []

    async def spike_detection_loop(self):
        """Enhanced spike detection with filtering and ranking."""
        while self.running:
            try:
                # Fetch all markets
                all_markets = await self.client.get_markets(
                    status="open",
                    limit=200,
                    min_volume=0,
                    filter_untradeable=False
                )
                
                if not all_markets:
                    self.logger.warning("No markets available")
                    await asyncio.sleep(self.config.SPIKE_CHECK_INTERVAL)
                    continue
                
                # Apply comprehensive filtering
                tradeable_markets = self.market_filter.filter_tradeable_markets(all_markets)
                
                if not tradeable_markets:
                    self.logger.debug("No tradeable markets after filtering")
                    await asyncio.sleep(self.config.SPIKE_CHECK_INTERVAL)
                    continue
                
                # Rank by opportunity
                ranked_markets = self.market_filter.rank_markets_by_opportunity(
                    tradeable_markets,
                    self.spike_detector
                )
                
                # Detect spikes on top markets (limit to top 20 to save processing)
                top_markets = ranked_markets[:20]
                spikes = self.spike_detector.detect_spikes(
                    markets=top_markets,
                    threshold=self.config.SPIKE_THRESHOLD
                )
                
                if spikes:
                    self.logger.info(f"🔔 Detected {len(spikes)} spike(s)!")
                    
                    for spike in spikes:
                        # Get full market object
                        market = next(
                            (m for m in top_markets if m.market_id == spike.market_id),
                            None
                        )
                        
                        if not market:
                            continue
                        
                        # Enhanced pre-trade validation
                        if await self.should_trade_spike(market, spike):
                            await self.execute_spike_trade(spike, market)
                else:
                    self.logger.debug(
                        f"No spikes detected in {len(top_markets)} top markets "
                        f"({len(tradeable_markets)} tradeable, {len(all_markets)} total)"
                    )
                
                await asyncio.sleep(self.config.SPIKE_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Spike detection error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def position_management_loop(self):
        """Monitor open positions and execute exits"""
        while self.running:
            try:
                # Check all open positions
                positions = self.position_manager.get_active_positions()
                
                for position in positions:
                    # Evaluate exit conditions
                    exit_decision = self.position_manager.evaluate_position(
                        position_id=position.id,
                        current_price=position.current_price
                    )
                    
                    if exit_decision.should_exit:
                        await self._execute_exit(
                            position=position,
                            reason=exit_decision.reason
                        )
                
                await asyncio.sleep(self.config.POSITION_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Position management error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _execute_spike_trade(self, spike, market):
        """Execute trade for validated spike."""
        try:
            self.logger.info(
                f"💰 EXECUTING TRADE: {spike.market_id} | "
                f"Spike: {spike.change_pct:+.1%} | "
                f"Direction: {spike.direction} | "
                f"Current: ${spike.current_price:.4f}"
            )
            
            # Determine order side (mean reversion strategy)
            # If price spiked UP, we SELL (bet on reversion down)
            # If price dropped DOWN, we BUY (bet on reversion up)
            order_side = "sell" if spike.change_pct > 0 else "buy"
            
            # Calculate position size
            quantity = self.config.TRADE_UNIT
            
            # Submit order
            order = await self.order_executor.submit_order(
                market_id=spike.market_id,
                side=order_side,
                size=quantity,
                price=spike.current_price,
                order_type="limit"
            )
            
            if order and hasattr(order, 'order_id'):
                # Track in position manager
                self.position_manager.add_position(
                    order_id=order.order_id,
                    market_id=spike.market_id,
                    entry_price=spike.current_price,
                    quantity=quantity,
                    side=order_side
                )
                
                self.logger.info(
                    f"✅ Order placed: {order.order_id} | "
                    f"{order_side.upper()} {quantity} @ ${spike.current_price:.4f}"
                )
            else:
                self.logger.warning(f"⚠️ Order submission failed for {spike.market_id}")
            
        except Exception as e:
            self.logger.error(
                f"❌ Trade execution failed for {spike.market_id}: {e}",
                exc_info=True
            )

    
    async def _execute_exit(self, position, reason):
        """Exit a position"""
        try:
            self.logger.info(
                f"Exiting position {position.id} (reason: {reason})"
            )
            
            # Submit closing order
            exit_order = await self.order_executor.submit_order(
                market_id=position.market_id,
                side="sell" if position.side == "buy" else "buy",
                size=position.quantity,
                price=position.current_price,
                order_type="market"  # Use market to ensure fill
            )
            
            # Calculate PnL
            pnl = self.position_manager.calculate_pnl(
                position=position,
                exit_price=exit_order.filled_price
            )
            
            # Remove from tracking
            self.position_manager.remove_position(position.id)
            
            self.logger.info(
                f"✓ Position closed. PnL: ${pnl:.2f}"
            )
            
        except Exception as e:
            self.logger.error(f"Exit execution failed: {e}", exc_info=True)
    
    async def run(self):
        """Main bot loop with concurrent price updates, spike detection, and position management."""
        try:
            # Initialize
            await self.initialize()
            
            # Start all three loops concurrently
            await asyncio.gather(
                self.price_update_loop(),
                self.spike_detection_loop(),
                self.position_management_loop(),
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.logger.info("Bot shutting down")
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.running = False
        
        # Close all positions
        positions = self.position_manager.get_active_positions()
        for position in positions:
            try:
                await self._execute_exit(position, reason="shutdown")
            except Exception as e:
                self.logger.error(f"Failed to close position: {e}")
        
        # Cleanup
        await self.client.close()
        self.logger.info("Bot shutdown complete")
        
    async def evaluate_entry_opportunity(self, market, entry_price, contracts):
        """Calculate fees and P&L before entering."""
        
        # Calculate fees for this entry
        entry_info = self.fee_calc.entry_cost(
            contracts=contracts,
            entry_price=entry_price,
            fee_type="taker"  # Assume market order
        )
        
        self.logger.info(
            f"Entry cost: ${entry_info['notional']:.2f} + "
            f"${entry_info['fee']:.2f} fee = ${entry_info['total_cost']:.2f}"
        )
        
        # Check if entry is affordable
        available_balance = await self.client.get_balance()
        
        if entry_info['total_cost'] > available_balance:
            self.logger.warning(f"❌ Insufficient balance for entry")
            return None
        
        return entry_info
    
    async def calculate_trade_results(self, trade_info):
        """Calculate final P&L after trade completes."""
        
        # Get fill prices
        entry_order = await self.client.get_order(trade_info['entry_order'].order_id)
        exit_order = await self.client.get_order(trade_info['exit_order'].order_id)
        
        if not (entry_order.is_filled and exit_order.is_filled):
            return None
        
        # Calculate complete P&L
        pnl = self.fee_calc.calculate_pnl(
            entry_price=entry_order.avg_fill_price,
            exit_price=exit_order.avg_fill_price,
            contracts=entry_order.quantity,
            entry_fee_type="taker",
            exit_fee_type="taker"
        )
        
        self.logger.info(f"✅ Trade Complete: {pnl}")
        
        return {
            'entry_price': pnl.entry_price,
            'exit_price': pnl.exit_price,
            'contracts': pnl.contracts,
            'entry_cost': pnl.entry_cost,
            'exit_revenue': pnl.exit_revenue,
            'entry_fee': pnl.entry_fee,
            'exit_fee': pnl.exit_fee,
            'gross_profit': pnl.gross_profit,
            'total_fees': pnl.total_fees,
            'net_profit': pnl.net_profit,
            'return_pct': pnl.return_pct
        }
    
    async def manage_positions(self):
        """
        Monitor open positions and execute exits when conditions are met.
        """
        try:
            # Get all active positions
            positions = self.position_manager.get_active_positions()
            
            if not positions:
                return  # No positions to manage
            
            # Get current market data for position markets
            market_ids = [pos['market_id'] for pos in positions]
            
            for position in positions:
                try:
                    # Get current market price
                    market = await self.client.get_market(position['market_id'])
                    current_price = market.price
                    
                    # Evaluate position for exit
                    exit_decision = self.position_manager.evaluate_position(
                        position_id=position['id'],
                        current_price=current_price
                    )
                    
                    if exit_decision['should_exit']:
                        # Execute exit
                        await self.execute_exit(
                            position=position,
                            reason=exit_decision['reason']
                        )
                        
                        self.logger.info(
                            f"📉 Position exited: {position['id']} | "
                            f"Reason: {exit_decision['reason']} | "
                            f"P&L: ${exit_decision.get('net_pnl', 0):+.2f}"
                        )
                
                except Exception as e:
                    self.logger.error(
                        f"Error managing position {position.get('id', 'unknown')}: {e}"
                    )
                    continue
        
        except Exception as e:
            self.logger.error(f"Position management error: {e}", exc_info=True)

    async def should_trade_spike(self, market, spike) -> bool:
        """
        Enhanced pre-trade validation.
        
        Returns True if spike should be traded.
        """
        # 1. Risk manager check
        risk_check = await self.risk_manager.can_trade_pre_submission(spike)
        if not risk_check.passed:
            self.logger.debug(
                f"❌ Risk check failed for {spike.market_id}: {risk_check.reason}"
            )
            return False
        
        # 2. Market quality checks
        # Check liquidity
        if market.liquidity_usd < 0.10:
            self.logger.debug(
                f"❌ Low liquidity for {spike.market_id}: ${market.liquidity_usd:.2f}"
            )
            return False
        
        # Check spread
        if market.best_ask_cents > 0 and market.best_bid_cents > 0:
            spread_pct = (
                (market.best_ask_cents - market.best_bid_cents) / market.last_price_cents
            )
            if spread_pct > 0.30:  # 30% max spread
                self.logger.debug(
                    f"❌ Wide spread for {spike.market_id}: {spread_pct:.1%}"
                )
                return False
        
        # 3. Price history depth
        history = self.spike_detector.price_history.get(market.market_id, [])
        if len(history) < 20:
            self.logger.debug(
                f"❌ Insufficient history for {spike.market_id}: {len(history)} points"
            )
            return False
        
        # 4. Time to expiry
        hours_to_close = market.time_to_expiry_seconds / 3600
        if hours_to_close < 0.5:  # < 30 minutes
            self.logger.debug(
                f"❌ Too close to expiry for {spike.market_id}: {hours_to_close:.1f}h"
            )
            return False
        
        # 5. Spike quality check
        if abs(spike.change_pct) > 0.30:  # > 30% move
            self.logger.debug(
                f"❌ Suspicious spike size for {spike.market_id}: {spike.change_pct:.1%}"
            )
            return False
        
        self.logger.info(
            f"✅ Trade validation passed for {spike.market_id}: "
            f"spike={spike.change_pct:.1%}, price=${market.price:.4f}, "
            f"liquidity=${market.liquidity_usd:.2f}, spread_ok, history={len(history)}"
        )
        
        return True



# Entry point
if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "kalshi"
    bot = TradingBot(platform=platform)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n⚠️  Shutdown signal received")