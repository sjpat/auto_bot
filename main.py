# main.py - Main execution file

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional
import os
import json

from src.config import Config
from src.logger import setup_logger
# from src.clients.polymarket_client import PolymarketClient
from src.clients.kalshi_client import KalshiClient
from src.strategies.strategy_manager import StrategyManager
from src.trading.order_executor import OrderExecutor
from src.trading.position_manager import PositionManager
from src.trading.risk_manager import RiskManager
from src.trading.fee_calculator import FeeCalculator
from src.trading.market_filter import MarketFilter
from src.trading.correlation_manager import CorrelationManager
from src.notification_manager import NotificationManager
from src.utils.db_manager import DatabaseManager


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
        self.db = DatabaseManager(config=self.config)

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
        self.strategy_manager = StrategyManager(config=self.config)
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
        
        # Initialize Correlation Manager
        self.correlation_manager = CorrelationManager(
            config=self.config,
            position_manager=self.position_manager
        )
        
        # Initialize Notifications
        self.notification_manager = NotificationManager(config=self.config)

        self.loop_count = 0
        self.running = False
        
        # Health monitoring
        self.last_markets_found_ts = datetime.now()
        self.last_alert_ts = None
        self.consecutive_errors = 0
        self.daily_pnl = 0.0
        self.starting_balance = 0.0
        self.loss_warning_sent = False
    
    async def initialize(self):
        try:
            self.logger.info(f"Initializing {self.platform} bot...")
            self.logger.info(f"Environment: {'DEMO' if self.config.KALSHI_DEMO else 'PRODUCTION'}")
            
            # Verify API connection
            await self.client.verify_connection()
            self.logger.info("✅ API connection verified")
            
            # Check balance
            balance = await self.client.get_balance()
            self.logger.info(f"Account balance: ${balance:.2f}")
            self.starting_balance = balance
            
            if balance < self.config.MIN_ACCOUNT_BALANCE:
                raise ValueError(f"Insufficient balance: ${balance:.2f}")
            
            # ✅ Initialize daily risk limits
            await self.risk_manager.initialize_daily(balance)
            self.logger.info("✅ Daily risk limits initialized")
            
            # Fetch initial market data
            markets = await self.client.get_markets(status="open", filter_untradeable=False)
            self.logger.info(f"Loaded {len(markets)} markets")
            
            # Load historical data from SQLite into StrategyManager
            self.logger.info("Loading price history from database...")
            active_ids = [m.market_id for m in markets]
            history = self.db.get_recent_history(market_ids=active_ids, hours=24)
            if history and hasattr(self.strategy_manager, 'load_historical_data'):
                self.strategy_manager.load_historical_data(history)
                self.logger.info(f"✅ Loaded history for {len(history)} markets")

            await self.notification_manager.send_message(f"🤖 *Bot Started* ({self.platform})\nBalance: `${balance:.2f}`")
            self.running = True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            raise

    
    async def trade_execution_loop(self):
        """Main loop for fetching data, generating signals, and executing trades."""
        while self.running:
            try:
                # 1. Fetch all open markets
                all_markets = await self.client.get_markets(
                    status="open",
                    limit=1000,
                    filter_untradeable=False
                )

                if not all_markets:
                    self.logger.warning("No open markets found.")
                    
                    # Alert if no markets found for extended period (e.g. 12 hours)
                    time_since_found = datetime.now() - self.last_markets_found_ts
                    if time_since_found.total_seconds() > 12 * 3600:
                        # Throttle alerts to once every 6 hours to avoid spam
                        if not self.last_alert_ts or (datetime.now() - self.last_alert_ts).total_seconds() > 6 * 3600:
                            await self.notification_manager.send_message(
                                f"⚠️ *Market Data Alert*\nNo open markets found for {time_since_found.total_seconds()/3600:.1f} hours."
                            )
                            self.last_alert_ts = datetime.now()
                    
                    await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)
                    continue
                
                # Update heartbeat on success
                self.last_markets_found_ts = datetime.now()

                # 2. Update price history for all markets
                for market in all_markets:
                    self.strategy_manager.on_market_update(market)
                
                # Persist updates to SQLite
                self.db.save_markets(all_markets)
                self.logger.debug(f"Updated price history for {len(all_markets)} markets")

                # 3. Generate signals from all markets
                signals = self.strategy_manager.generate_entry_signals(all_markets)

                if signals:
                    self.logger.info(f"🔔 Detected {len(signals)} opportunity(ies)!")

                    for signal in signals:
                        # Find the corresponding market object for the signal
                        market = next((m for m in all_markets if m.market_id == signal.market_id), None)
                        if not market:
                            self.logger.warning(f"Market object not found for signal on {signal.market_id}")
                            continue

                        # 4. Risk check and execution
                        if await self.should_trade_signal(market, signal):
                            await self.execute_signal_trade(signal, market)
                else:
                    self.logger.debug(
                        f"No signals generated from {len(all_markets)} total markets"
                    )

                # Reset error counter on successful iteration
                self.consecutive_errors = 0
                await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)

            except Exception as e:
                self.consecutive_errors += 1
                if self.consecutive_errors == 10:
                    await self.notification_manager.send_error("⚠️ *Unstable Bot Alert*\nEncountered 10 consecutive errors in execution loop.")
                
                self.logger.error(f"Error in trade execution loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def should_trade_signal(self, market, signal) -> bool:
        """Perform risk and quality checks before executing a trade."""
        # 1. Risk manager check
        # Create a mock spike object if signal doesn't have change_pct (compatibility)
        class MockSpike:
            def __init__(self, change_pct, market_id):
                self.change_pct = change_pct
                self.market_id = market_id
        
        # Map strategy-specific metrics to 'change_pct' for RiskManager validation
        magnitude = signal.metadata.get('spike_magnitude', 0.0)
        if magnitude == 0.0:
            if 'roc' in signal.metadata:
                magnitude = abs(signal.metadata['roc'])
            elif 'edge' in signal.metadata:
                magnitude = signal.metadata['edge']
        
        spike_obj = MockSpike(
            change_pct=magnitude,
            market_id=signal.market_id
        )

        risk_check = await self.risk_manager.can_trade_pre_submission(spike_obj)
        if not risk_check.passed:
            self.logger.debug(
                f"❌ Risk check failed for {signal.market_id}: {risk_check.reason}"
            )
            return False
        
        # 2. Market quality checks
        # Check liquidity
        if market.liquidity_usd < self.config.MIN_LIQUIDITY_USD:
            self.logger.debug(
                f"❌ Low liquidity for {signal.market_id}: ${market.liquidity_usd:.2f}"
            )
            return False
        
        # Check spread
        if market.best_ask_cents > 0 and market.best_bid_cents > 0:
            mid_price_cents = (market.best_ask_cents + market.best_bid_cents) / 2
            if mid_price_cents > 0:
                spread_pct = (market.best_ask_cents - market.best_bid_cents) / mid_price_cents
                if spread_pct > self.config.MAX_SPREAD_PCT:
                    self.logger.debug(
                        f"❌ Wide spread for {signal.market_id}: {spread_pct:.1%}"
                    )
                    return False
        
        # 3. Correlation check
        # Estimate cost: price * trade_unit
        estimated_cost = market.price * self.config.TRADE_UNIT
        corr_passed, corr_reason = self.correlation_manager.check_exposure(
            market.market_id, 
            estimated_cost
        )
        if not corr_passed:
            self.logger.debug(f"❌ {corr_reason}")
            return False
        
        self.logger.info(
            f"✅ Trade validation passed for {signal.market_id}: "
            f"conf={signal.confidence:.1%}, price=${market.price:.4f}"
        )
        return True
    
    async def execute_signal_trade(self, signal, market):
        """Executes a trade based on a signal."""
        # This method can be a dispatcher based on signal type or strategy
        # For now, we'll assume all signals lead to a 'spike-like' trade
        await self._execute_spike_trade(signal, market)

    async def position_management_loop(self):
        """Monitor open positions and execute exits"""
        while self.running:
            try:
                # Check all open positions
                positions = self.position_manager.get_active_positions()
                
                # 1. Strategy-based exits (e.g. Mispricing convergence)
                # We need to fetch current market data for these positions
                if positions:
                    # Note: In a real scenario, we might want to batch fetch these
                    # For now, we rely on the fact that we likely have recent data or fetch individually
                    # StrategyManager expects a dict of {market_id: Market}
                    # We will skip this optimization for now and rely on PositionManager's internal checks
                    # OR implement the strategy check if PositionManager doesn't cover it.
                    pass
                
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
                        continue

                    # Check Strategy Manager Exits (Parity with Backtest)
                    # This allows strategies to signal exits (e.g. fair value reached)
                    # We need to construct a minimal market map for the strategy
                    try:
                        market = await self.client.get_market(position.market_id)
                        market_map = {position.market_id: market}
                        exit_signals = self.strategy_manager.generate_exit_signals([position], market_map)
                        
                        if exit_signals:
                            signal = exit_signals[0]
                            await self._execute_exit(
                                position=position,
                                reason=signal.metadata.get('reason', 'strategy_exit')
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error checking strategy exit for {position.market_id}: {e}"
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
                f"Direction: {spike.signal_type} | "
                f"Current: ${spike.price:.4f}"
            )
            
            # Determine order side
            order_side = "buy" if spike.signal_type == "buy" else "sell"
            
            # Calculate position size
            quantity = self.config.TRADE_UNIT
            
            # Submit order
            order = await self.order_executor.submit_order(
                market_id=spike.market_id,
                side=order_side,
                size=quantity,
                price=spike.price,
                order_type="limit"
            )
            
            if order and order.get('success'):
                order_details = order.get('order')
                if order_details and hasattr(order_details, 'order_id'):
                    # Track in position manager
                    self.position_manager.add_position(
                        order_id=order_details.order_id,
                        market_id=spike.market_id,
                        entry_price=spike.price,
                        quantity=quantity,
                        side=order_side
                    )
                    
                    self.logger.info(
                        f"✅ Order placed: {order_details.order_id} | "
                        f"{order_side.upper()} {quantity} @ ${spike.price:.4f}"
                    )
                    
                    # Send Notification
                    await self.notification_manager.send_trade_alert(
                        market_id=spike.market_id,
                        side=order_side,
                        price=spike.price,
                        quantity=quantity,
                        strategy=spike.metadata.get('strategy', 'unknown')
                    )
                else:
                    self.logger.warning(f"⚠️ Order submission did not return order_id for {spike.market_id}")
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
            exit_order_result = await self.order_executor.submit_order(
                market_id=position.market_id,
                side="sell" if position.side == "buy" else "buy",
                size=position.quantity,
                price=position.current_price,
                order_type="market"  # Use market to ensure fill
            )

            if exit_order_result and exit_order_result.get('success'):
                exit_order = exit_order_result.get('order')
                # Calculate PnL
                pnl = self.position_manager.calculate_pnl(
                    position=position,
                    exit_price=exit_order.avg_fill_price if hasattr(exit_order, 'avg_fill_price') else position.current_price
                )
                
                # Remove from tracking
                self.position_manager.remove_position(position.id)
                
                # Track Daily P&L for alerts
                self.daily_pnl += pnl
                if self.starting_balance > 0:
                    max_loss_usd = self.starting_balance * self.config.MAX_DAILY_LOSS_PCT
                    if self.daily_pnl <= -(max_loss_usd * 0.8) and not self.loss_warning_sent:
                        await self.notification_manager.send_message(
                            f"⚠️ *Risk Warning*\nDaily P&L (${self.daily_pnl:.2f}) has reached 80% of daily loss limit (${max_loss_usd:.2f})."
                        )
                        self.loss_warning_sent = True
                
                self.logger.info(
                    f"✓ Position closed. PnL: ${pnl:.2f}"
                )
                
                # Send Notification
                await self.notification_manager.send_exit_alert(
                    market_id=position.market_id,
                    pnl=pnl,
                    reason=reason,
                    return_pct=position.return_pct
                )
            else:
                self.logger.error(f"Exit order submission failed for position {position.id}")
            
        except Exception as e:
            self.logger.error(f"Exit execution failed: {e}", exc_info=True)
    
    async def run(self):
        """Main bot loop with concurrent execution of trading and position management."""
        try:
            # Initialize
            await self.initialize()
            
            # Register signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            
            # Start all loops concurrently
            await asyncio.gather(
                self.trade_execution_loop(),
                self.position_management_loop(),
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
            await self.notification_manager.send_error(str(e))
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
        await self.notification_manager.send_message("🛑 *Bot Shutdown Complete*")
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


# Entry point
if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "kalshi"
    bot = TradingBot(platform=platform)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n⚠️  Shutdown signal received")