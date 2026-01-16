"""
Pricing models for calculating theoretical market values.
Used to detect mispricing opportunities.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class FairValue:
    """Calculated fair value for a market."""
    probability: float  # 0.0 - 1.0
    confidence: float  # How confident in this estimate
    method: str  # Which pricing method was used
    metadata: Dict[str, Any]  # Additional context


class PricingModels:
    """
    Collection of pricing models to calculate fair value.
    
    These establish theoretical probabilities that we compare
    to market prices to find edges.
    """
    
    @staticmethod
    def binary_yes_no_complement(market_data: Dict) -> Optional[FairValue]:
        """
        For YES/NO markets, YES + NO should = 100%.
        
        If YES is 60% and NO is 35%, the market is mispriced.
        True probabilities should be normalized.
        
        Args:
            market_data: Dict with 'yes_price' and 'no_price'
        
        Returns:
            FairValue with normalized probabilities
        """
        yes_price = market_data.get('yes_price', 0)
        no_price = market_data.get('no_price', 0)
        
        if yes_price == 0 or no_price == 0:
            return None
        
        total = yes_price + no_price
        
        # If total != 1.0, there's an arbitrage opportunity
        if total < 0.98 or total > 1.02:
            # Calculate fair normalized values
            fair_yes = yes_price / total
            fair_no = no_price / total
            
            # Average the two for a fair estimate
            fair_prob = (fair_yes + (1 - fair_no)) / 2
            
            # Confidence based on how far from 1.0
            confidence = min(abs(1.0 - total), 0.5) * 2  # Max 50% = 1.0 confidence
            
            return FairValue(
                probability=fair_prob,
                confidence=confidence,
                method='yes_no_complement',
                metadata={
                    'yes_price': yes_price,
                    'no_price': no_price,
                    'total': total,
                    'arbitrage_size': abs(1.0 - total)
                }
            )
        
        return None
    
    @staticmethod
    def time_decay_expiration(market_data: Dict) -> Optional[FairValue]:
        """
        Markets near expiration should converge to 0 or 100.
        
        If a market expires in 1 hour and the outcome is clear,
        but it's still priced at 70%, that's mispriced.
        
        Args:
            market_data: Dict with 'time_to_expiry_seconds', 'current_price', 'likely_outcome'
        
        Returns:
            FairValue if near expiration with clear outcome
        """
        time_to_expiry_hours = market_data.get('time_to_expiry_seconds', float('inf')) / 3600
        current_price = market_data.get('current_price', 0.5)
        
        # Only applicable within 6 hours of expiration
        if time_to_expiry_hours > 6:
            return None
        
        # Check if outcome is highly probable
        if current_price > 0.85:
            # Market likely YES, should approach 1.0
            time_factor = max(0, (6 - time_to_expiry_hours) / 6)  # 0-1 scale
            fair_prob = 0.85 + (0.15 * time_factor)  # Approaches 1.0
            
            return FairValue(
                probability=fair_prob,
                confidence=time_factor * 0.8,
                method='time_decay_yes',
                metadata={
                    'current_price': current_price,
                    'time_to_expiry_hours': time_to_expiry_hours,
                    'expected_convergence': fair_prob
                }
            )
        
        elif current_price < 0.15:
            # Market likely NO, should approach 0.0
            time_factor = max(0, (6 - time_to_expiry_hours) / 6)
            fair_prob = 0.15 * (1 - time_factor)  # Approaches 0.0
            
            return FairValue(
                probability=fair_prob,
                confidence=time_factor * 0.8,
                method='time_decay_no',
                metadata={
                    'current_price': current_price,
                    'time_to_expiry_hours': time_to_expiry_hours,
                    'expected_convergence': fair_prob
                }
            )
        
        return None
    
    @staticmethod
    def moving_average_reversion(price_history: list, current_price: float) -> Optional[FairValue]:
        """
        Mean reversion: if price deviates significantly from moving average,
        it should revert.
        
        Args:
            price_history: List of recent prices
            current_price: Current market price
        
        Returns:
            FairValue if significant deviation detected
        """
        if len(price_history) < 10:
            return None
        
        mean = statistics.mean(price_history)
        std_dev = statistics.stdev(price_history) if len(price_history) > 1 else 0.01
        
        # Z-score
        z_score = (current_price - mean) / std_dev if std_dev > 0 else 0
        
        # If price is more than 2 standard deviations away
        if abs(z_score) > 2.0:
            # Fair value is the mean (mean reversion)
            confidence = min(abs(z_score) / 3.0, 1.0)  # Max at 3 sigma
            
            return FairValue(
                probability=mean,
                confidence=confidence * 0.6,  # Lower confidence for statistical
                method='mean_reversion',
                metadata={
                    'current_price': current_price,
                    'mean': mean,
                    'std_dev': std_dev,
                    'z_score': z_score,
                    'history_length': len(price_history)
                }
            )
        
        return None
    
    @staticmethod
    def mutually_exclusive_normalization(related_markets: list) -> Optional[Dict[str, FairValue]]:
        """
        For mutually exclusive events (only one can happen),
        probabilities should sum to 100%.
        
        Example: "Which team wins championship" markets should sum to 100%
        
        Args:
            related_markets: List of markets that are mutually exclusive
        
        Returns:
            Dict of market_id -> FairValue with normalized probabilities
        """
        if len(related_markets) < 2:
            return None
        
        total_prob = sum(m['current_price'] for m in related_markets)
        
        # If sum is far from 1.0, normalize
        if total_prob < 0.95 or total_prob > 1.05:
            fair_values = {}
            
            for market in related_markets:
                normalized_prob = market['current_price'] / total_prob
                edge = normalized_prob - market['current_price']
                
                fair_values[market['market_id']] = FairValue(
                    probability=normalized_prob,
                    confidence=min(abs(edge) * 5, 1.0),
                    method='mutual_exclusivity',
                    metadata={
                        'original_price': market['current_price'],
                        'total_sum': total_prob,
                        'normalized_prob': normalized_prob
                    }
                )
            
            return fair_values
        
        return None
