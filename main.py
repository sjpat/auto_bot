# test.py - Main execution file

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

    
    async def trade_execution_loop(self):
        """Main loop for fetching data, generating signals, and executing trades."""
        while self.running:
            try:
                # 1. Fetch all open markets
                all_markets = await self.client.get_markets(
                    status="open",
                    limit=200,
                    filter_untradeable=False
                )

                if not all_markets:
                    self.logger.warning("No open markets found.")
                    await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)
                    continue

                # 2. Update price history for all markets
                for market in all_markets:
                    self.strategy_manager.on_market_update(market)
                self.logger.debug(f"Updated price history for {len(all_markets)} markets")

                # 3. Apply comprehensive filtering
                tradeable_markets = self.market_filter.filter_tradeable_markets(all_markets)

                if not tradeable_markets:
                    self.logger.debug("No tradeable markets after filtering")
                    await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)
                    continue

                # 4. Rank by opportunity
                # In the future, the spike_detector could be made a property of the strategy_manager
                spike_detector = self.strategy_manager.spike_strategy if hasattr(self.strategy_manager, 'spike_strategy') else None
                if not spike_detector:
                    self.logger.warning("Spike detector not found in strategy manager. Skipping ranking.")
                    ranked_markets = tradeable_markets
                else:
                    ranked_markets = self.market_filter.rank_markets_by_opportunity(
                        tradeable_markets,
                        spike_detector
                    )

                # 5. Generate signals from top markets
                top_markets = ranked_markets[:20]
                signals = self.strategy_manager.generate_entry_signals(top_markets)

                if signals:
                    self.logger.info(f"🔔 Detected {len(signals)} opportunity(ies)!")

                    for signal in signals:
                        market = next((m for m in top_markets if m.market_id == signal.market_id), None)
                        if not market:
                            continue

                        # 6. Risk check and execution
                        if await self.should_trade_signal(market, signal):
                            await self.execute_signal_trade(signal, market)
                else:
                    self.logger.debug(
                        f"No signals generated from {len(top_markets)} top markets "
                        f"({len(tradeable_markets)} tradeable, {len(all_markets)} total)"
                    )

                await asyncio.sleep(self.config.PRICE_UPDATE_INTERVAL)

            except Exception as e:
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
        
        spike_obj = MockSpike(
            change_pct=signal.metadata.get('spike_magnitude', 0.0),
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
            spread_pct = (
                (market.best_ask_cents - market.best_bid_cents) / market.last_price_cents
            )
            if spread_pct > self.config.MAX_SPREAD_PCT:
                self.logger.debug(
                    f"❌ Wide spread for {signal.market_id}: {spread_pct:.1%}"
                )
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
                
                self.logger.info(
                    f"✓ Position closed. PnL: ${pnl:.2f}"
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
            
            # Start all loops concurrently
            await asyncio.gather(
                self.trade_execution_loop(),
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

        # Save price history
        self.logger.info("Saving price history...")
        price_histories = self.strategy_manager.get_all_price_histories()
        if price_histories:
            try:
                with open("data/price_history.json", "w") as f:
                    json.dump(price_histories, f, indent=2)
                self.logger.info("✅ Price history saved to data/price_history.json")
            except Exception as e:
                self.logger.error(f"Failed to save price history: {e}")
        
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


# Entry point
if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "kalshi"
    bot = TradingBot(platform=platform)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n⚠️  Shutdown signal received")