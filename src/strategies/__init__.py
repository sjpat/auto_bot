"""
Trading strategies for the bot.
"""

from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.strategies.spike_strategy import SpikeStrategy

__all__ = [
    'BaseStrategy',
    'Signal',
    'SignalType',
    'SpikeStrategy',
]
