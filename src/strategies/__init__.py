"""
Trading strategies for the bot.
"""

from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.strategies.spike_strategy import SpikeStrategy
from src.strategies.mispricing_strategy import MispricingStrategy
from src.strategies.momentum_strategy import MomentumStrategy

__all__ = [
    'BaseStrategy',
    'Signal',
    'SignalType',
    'SpikeStrategy',
    'MispricingStrategy',
    'MomentumStrategy',
]
