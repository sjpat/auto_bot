"""
Strategy Manager - Runs multiple trading strategies simultaneously.
"""

import logging
from typing import List, Dict, Any, Optional
from src.strategies.spike_strategy import SpikeStrategy
from src.strategies.mispricing_strategy import MispricingStrategy
from src.strategies.base_strategy import Signal
from src.models.market import Market
from src.models.position import Position


logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages and coordinates multiple trading strategies.
    
    Benefits:
    - Run spike detection AND mispricing detection simultaneously
    - Rank opportunities across all strategies
    - Unified signal generation
    - Strategy-specific exit logic
    """
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.strategies = []
        
        # Track which strategy opened each position
        self.position_strategies: Dict[str, str] = {}  # position_id -> strategy_name
        
        # Initialize Spike Strategy
        if getattr(config, 'ENABLE_SPIKE_STRATEGY', True):
            try:
                spike_config = {
                    'SPIKE_THRESHOLD': config.SPIKE_THRESHOLD,
                    'HISTORY_SIZE': config.PRICE_HISTORY_SIZE,
                    'MIN_HISTORY': 20,
                    'TARGET_PROFIT_USD': config.TARGET_PROFIT_USD,
                    'TARGET_LOSS_USD': config.TARGET_LOSS_USD,
                    'HOLDING_TIME_LIMIT': config.HOLDING_TIME_LIMIT,
                    'COOLDOWN_PERIOD': config.COOLDOWN_PERIOD,
                    'MIN_LIQUIDITY_REQUIREMENT': config.MIN_LIQUIDITY_REQUIREMENT
                }
                self.spike_strategy = SpikeStrategy(spike_config)
                self.strategies.append(('spike', self.spike_strategy))
                self.logger.info("✅ Spike strategy enabled")
            except Exception as e:
                self.logger.error(f"❌ Failed to load spike strategy: {e}")
        else:
            self.logger.info("⏭️  Spike strategy disabled")
        
        # Initialize Mispricing Strategy
        if getattr(config, 'ENABLE_MISPRICING_STRATEGY', True):
            try:
                mispricing_config = {
                    'MIN_EDGE': getattr(config, 'MIN_EDGE', 0.08),
                    'MIN_CONFIDENCE': getattr(config, 'MIN_CONFIDENCE_MISPRICING', 0.60),
                    'MAX_HOLDING_TIME': getattr(config, 'MISPRICING_MAX_HOLDING_TIME', 14400),
                    'HISTORY_SIZE': getattr(config, 'MISPRICING_HISTORY_SIZE', 50),
                    'MIN_LIQUIDITY_REQUIREMENT': config.MIN_LIQUIDITY_REQUIREMENT
                }
                self.mispricing_strategy = MispricingStrategy(mispricing_config)
                self.strategies.append(('mispricing', self.mispricing_strategy))
                self.logger.info("✅ Mispricing strategy enabled")
            except Exception as e:
                self.logger.error(f"❌ Failed to load mispricing strategy: {e}")
        else:
            self.logger.info("⏭️  Mispricing strategy disabled")
        
        if not self.strategies:
            raise ValueError("No strategies enabled! Enable at least one strategy.")
        
        self.logger.info(f"🎯 Strategy Manager initialized with {len(self.strategies)} strategies")
    
    def generate_entry_signals(self, markets: List[Market]) -> List[Signal]:
        """
        Generate trading signals from all enabled strategies.
        
        Args:
            markets: List of available markets
        
        Returns:
            Ranked list of best opportunities across all strategies
        """
        all_signals = []
        
        for strategy_name, strategy in self.strategies:
            try:
                signals = strategy.generate_entry_signals(markets)
                
                # Tag each signal with its source strategy
                for signal in signals:
                    if 'strategy' not in signal.metadata:
                        signal.metadata['strategy'] = strategy_name
                
                all_signals.extend(signals)
                
                if signals:
                    self.logger.info(
                        f"📊 {strategy_name.upper()}: {len(signals)} signals generated"
                    )
            
            except Exception as e:
                self.logger.error(f"❌ Error in {strategy_name} strategy: {e}")
                import traceback
                traceback.print_exc()
        
        # Rank and return top opportunities
        ranked_signals = self._rank_signals(all_signals)
        
        if ranked_signals:
            self.logger.info(
                f"🎯 Total: {len(all_signals)} signals | Returning top {min(len(ranked_signals), 10)}"
            )
        
        return ranked_signals[:10]  # Top 10 opportunities
    
    def generate_exit_signals(
        self,
        positions: List[Position],
        markets: Dict[str, Market]
    ) -> List[Signal]:
        """
        Generate exit signals for open positions.
        
        Routes each position to the strategy that created it.
        
        Args:
            positions: List of open positions
            markets: Current market data
        
        Returns:
            Exit signals from appropriate strategies
        """
        # Group positions by strategy
        strategy_positions = {}
        for position in positions:
            # Determine which strategy owns this position
            strategy_name = position.metadata.get('strategy', 'spike')  # Default to spike
            
            if strategy_name not in strategy_positions:
                strategy_positions[strategy_name] = []
            strategy_positions[strategy_name].append(position)
        
        # Get exit signals from each strategy
        all_exit_signals = []
        
        for strategy_name, strategy in self.strategies:
            if strategy_name not in strategy_positions:
                continue
            
            try:
                positions_subset = strategy_positions[strategy_name]
                signals = strategy.generate_exit_signals(positions_subset, markets)
                all_exit_signals.extend(signals)
                
                if signals:
                    self.logger.info(
                        f"🚪 {strategy_name.upper()}: {len(signals)} exit signals"
                    )
            
            except Exception as e:
                self.logger.error(f"❌ Error getting exits from {strategy_name}: {e}")
        
        return all_exit_signals
    
    def on_market_update(self, market: Market):
        """
        Forward market updates to all strategies.
        
        Both strategies need price history for their logic.
        """
        for strategy_name, strategy in self.strategies:
            try:
                strategy.on_market_update(market)
            except Exception as e:
                self.logger.error(f"❌ Error updating {strategy_name}: {e}")
    
    def _rank_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        Rank signals by quality score.
        
        Scoring:
        - Base: confidence score
        - Multiplier: edge size (if available)
        - Bonus: reliable methods (time decay, arbitrage)
        - Penalty: high risk methods
        """
        if not signals:
            return []
        
        scored_signals = []
        
        for signal in signals:
            # Start with confidence
            score = signal.confidence
            
            # Boost for larger edges
            if 'edge' in signal.metadata:
                edge = signal.metadata['edge']
                score *= (1.0 + edge * 2)  # 10% edge = 1.2x multiplier
            
            # Boost for high-confidence pricing methods
            if 'pricing_method' in signal.metadata:
                method = signal.metadata['pricing_method']
                
                if method in ['time_decay_yes', 'time_decay_no']:
                    score *= 1.3  # Time decay is very reliable
                elif method == 'yes_no_complement':
                    score *= 1.2  # Arbitrage is reliable
                elif method == 'mean_reversion':
                    score *= 0.9  # Mean reversion is less reliable
            
            # Strategy type bonus
            strategy = signal.metadata.get('strategy', 'unknown')
            if strategy == 'mispricing':
                score *= 1.1  # Slight preference for mispricing (works in low volatility)
            
            scored_signals.append((score, signal))
        
        # Sort by score descending
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        
        # Log top opportunities
        for i, (score, signal) in enumerate(scored_signals[:5], 1):
            market_id = signal.market_id[:30]
            strategy = signal.metadata.get('strategy', 'unknown')
            self.logger.debug(
                f"  #{i} {market_id}... | "
                f"Strategy: {strategy} | "
                f"Score: {score:.2f} | "
                f"Confidence: {signal.confidence:.1%}"
            )
        
        return [signal for score, signal in scored_signals]
    
    def record_trade_start(self, market_id: str, strategy_name: str):
        """Record which strategy initiated a trade (for cooldowns)."""
        for name, strategy in self.strategies:
            if name == strategy_name:
                if hasattr(strategy, 'record_trade_start'):
                    strategy.record_trade_start(market_id)
    
    def get_all_price_histories(self) -> Dict[str, Dict[str, List[float]]]:
        """Get price histories from all strategies."""
        histories = {}
        for strategy_name, strategy in self.strategies:
            if hasattr(strategy, 'price_history'):
                # convert deques to lists for serialization
                histories[strategy_name] = {market_id: list(history) for market_id, history in strategy.price_history.items()}
        return histories

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from all strategies."""
        stats = {
            'enabled_strategies': len(self.strategies),
            'strategies': {}
        }
        
        for strategy_name, strategy in self.strategies:
            try:
                stats['strategies'][strategy_name] = strategy.get_statistics()
            except Exception as e:
                self.logger.error(f"Error getting stats from {strategy_name}: {e}")
                stats['strategies'][strategy_name] = {'error': str(e)}
        
        return stats
