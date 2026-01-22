# src/config.py

import os
from typing import Literal
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    """Configuration container for both Polymarket and Kalshi"""
    
    platform: Literal["polymarket", "kalshi"] = "kalshi"
    
    # ===== API Configuration =====
    # Polymarket
    CLOB_HOST: str = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
    POLYMARKET_SETTLEMENT_CONTRACT: str = os.getenv(
        "POLYMARKET_SETTLEMENT_CONTRACT",
        "0x56C79347e95530c01A2FC76E732f9566dA16E113"
    )
    
    # KALSHI API
    KALSHI_API_KEY = os.getenv('KALSHI_API_KEY')
    KALSHI_PRIVATE_KEY_PATH = os.getenv('KALSHI_PRIVATE_KEY_PATH')
    KALSHI_DEMO = os.getenv('KALSHI_DEMO', 'false').lower() == 'true'

    # Fee Settings
    TAKER_FEE_MULTIPLIER: float = float(
        os.getenv("TAKER_FEE_MULTIPLIER", "0.07")
    )
    MAKER_FEE_MULTIPLIER: float = float(
        os.getenv("MAKER_FEE_MULTIPLIER", "0.0175")
    )

    DEFAULT_ENTRY_FEE_TYPE = 'taker'
    DEFAULT_EXIT_FEE_TYPE = 'taker'
    DEFAULT_PROFIT_TARGET = 2.50
    DEFAULT_CONTRACTS_PER_TRADE = 100

    
    # ===== Wallet/Account Configuration =====
    # Polymarket
    PK: str = os.getenv("PK", "")  # Private key for Web3 signing
    BOT_TRADER_ADDRESS: str = os.getenv("BOT_TRADER_ADDRESS", "")
    YOUR_PROXY_WALLET: str = os.getenv("YOUR_PROXY_WALLET", "")
    USDC_CONTRACT_ADDRESS: str = os.getenv(
        "USDC_CONTRACT_ADDRESS",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    )
    # ===== Mispricing Strategy Parameters =====
    MIN_EDGE: float = float(os.getenv("MIN_EDGE", "0.08"))
    MIN_CONFIDENCE_MISPRICING: float = float(os.getenv("MIN_CONFIDENCE_MISPRICING", "0.60"))
    MISPRICING_MAX_HOLDING_TIME: int = int(os.getenv("MISPRICING_MAX_HOLDING_TIME", "14400"))  # 4 hours
    MISPRICING_HISTORY_SIZE: int = int(os.getenv("MISPRICING_HISTORY_SIZE", "50"))

    # ===== Strategy Selection =====
    ENABLE_SPIKE_STRATEGY: bool = os.getenv("ENABLE_SPIKE_STRATEGY", "true").lower() == "true"
    ENABLE_MISPRICING_STRATEGY: bool = os.getenv("ENABLE_MISPRICING_STRATEGY", "true").lower() == "true"
    ENABLE_MOMENTUM_STRATEGY: bool = os.getenv("ENABLE_MOMENTUM_STRATEGY", "false").lower() == "true"
    ENABLE_VOLUME_STRATEGY: bool = os.getenv("ENABLE_VOLUME_STRATEGY", "false").lower() == "true"

    # ===== Momentum Strategy Parameters =====
    MOMENTUM_WINDOW: int = int(os.getenv("MOMENTUM_WINDOW", "6"))
    MOMENTUM_THRESHOLD: float = float(os.getenv("MOMENTUM_THRESHOLD", "0.03"))
    MIN_CONFIDENCE_MOMENTUM: float = float(os.getenv("MIN_CONFIDENCE_MOMENTUM", "0.65"))
    MOMENTUM_REVERSAL_MULTIPLIER: float = float(os.getenv("MOMENTUM_REVERSAL_MULTIPLIER", "0.5"))

    # ===== Volume Strategy Parameters =====
    VOLUME_SPIKE_THRESHOLD: float = float(os.getenv("VOLUME_SPIKE_THRESHOLD", "3.0"))  # 3x average
    MIN_VOLUME_FOR_STRATEGY: int = int(os.getenv("MIN_VOLUME_FOR_STRATEGY", "100"))

    # ===== Trading Parameters =====
    TRADE_UNIT: int = int(float(os.getenv("TRADE_UNIT", "50")))
    SPIKE_THRESHOLD: float = float(os.getenv("SPIKE_THRESHOLD", "0.04"))
    SOLD_POSITION_TIME: int = int(os.getenv("SOLD_POSITION_TIME", "120"))
    HOLDING_TIME_LIMIT: int = int(os.getenv("HOLDING_TIME_LIMIT", "3600"))
    PRICE_HISTORY_SIZE: int = int(os.getenv("PRICE_HISTORY_SIZE", "100"))
    COOLDOWN_PERIOD: int = int(os.getenv("COOLDOWN_PERIOD", "10"))
    MAX_CONCURRENT_TRADES: int = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
    MIN_LIQUIDITY_REQUIREMENT: float = float(
        os.getenv("MIN_LIQUIDITY_REQUIREMENT", "200.0")
    )

    # ===== Fee-Aware Parameters (Kalshi) =====
    TARGET_PROFIT_USD: float = float(os.getenv("TARGET_PROFIT_USD", "2.00"))
    TARGET_LOSS_USD: float = float(os.getenv("TARGET_LOSS_USD", "-1.5"))
    MIN_PRICE_POINT: float = float(os.getenv("MIN_PRICE_POINT", "0.05"))
    MAX_PRICE_POINT: float = float(os.getenv("MAX_PRICE_POINT", "0.95"))
    FEE_AWARE_SPIKE_THRESHOLD: float = float(
        os.getenv("FEE_AWARE_SPIKE_THRESHOLD", "0.03")
    )

    # ===== Trailing Stop Parameters =====
    USE_TRAILING_STOP: bool = os.getenv("USE_TRAILING_STOP", "false").lower() == "true"
    TRAILING_STOP_ACTIVATION_USD: float = float(os.getenv("TRAILING_STOP_ACTIVATION_USD", "5.00"))
    TRAILING_STOP_DISTANCE_USD: float = float(os.getenv("TRAILING_STOP_DISTANCE_USD", "2.50"))
    
    # ===== Risk Management =====
    MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.15"))
    MAX_SLIPPAGE_TOLERANCE: float = float(
        os.getenv("MAX_SLIPPAGE_TOLERANCE", "0.025")
    )
    MIN_TIME_TO_EXPIRY_SECONDS: int = int(
        os.getenv("MIN_TIME_TO_EXPIRY_SECONDS", "3600")
    )
    ORDER_TIMEOUT_SECONDS: int = int(os.getenv("ORDER_TIMEOUT_SECONDS", "5"))
    MAX_ORDER_RETRIES: int = int(os.getenv("MAX_ORDER_RETRIES", "3"))
    MAX_CONCURRENT_POSITIONS: int = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
    MAX_DAILY_TRADES: int = int(os.getenv("MAX_DAILY_TRADES", "20"))
    MIN_SECONDS_BETWEEN_TRADES: int = int(os.getenv("MIN_SECONDS_BETWEEN_TRADES", "2"))

    VALID_PRICE_MIN: float = float(os.getenv("VALID_PRICE_MIN", "0.05"))
    VALID_PRICE_MAX: float = float(os.getenv("VALID_PRICE_MAX", "0.95"))

    MAX_ORDER_LATENCY_SECONDS: int = int(
        os.getenv("MAX_ORDER_LATENCY_SECONDS", "5")
    )
    MAX_BACKOFF_SECONDS: int = int(os.getenv("MAX_BACKOFF_SECONDS", "1"))

    # ===== Notifications =====
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")


    # ===== Operational =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")
    PRICE_UPDATE_INTERVAL: float = float(
        os.getenv("PRICE_UPDATE_INTERVAL", "1.0")  # seconds
    )
    SPIKE_CHECK_INTERVAL: float = float(
        os.getenv("SPIKE_CHECK_INTERVAL", "0.5")  # seconds
    )
    POSITION_CHECK_INTERVAL: float = float(
        os.getenv("POSITION_CHECK_INTERVAL", "0.5")  # seconds
    )
    MIN_ACCOUNT_BALANCE: float = float(
        os.getenv("MIN_ACCOUNT_BALANCE", "100.0")  # Minimum $100
    )

    # ===== Paper Trading Configuration =====
    PAPER_TRADING = bool(os.getenv("PAPER_TRADING", False))
    PAPER_STARTING_BALANCE = float(os.getenv("PAPER_STARTING_BALANCE", "1000.0"))
    PAPER_SIMULATE_SLIPPAGE = bool(os.getenv("PAPER_SIMULATE_SLIPPAGE", True))
    PAPER_MAX_SLIPPAGE_PCT = float(os.getenv("PAPER_MAX_SLIPPAGE_PCT", "0.005"))
    PAPER_SAVE_HISTORY = bool(os.getenv("PAPER_SAVE_HISTORY", True))
    PAPER_HISTORY_FILE = os.getenv("PAPER_HISTORY_FILE", "logs/paper_trading_history.json")
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.platform == "polymarket":
            if not self.PK:
                raise ValueError("PK (private key) required for Polymarket")
            if not self.BOT_TRADER_ADDRESS:
                raise ValueError("BOT_TRADER_ADDRESS required for Polymarket")
        
        elif self.platform == "kalshi":
            if not self.KALSHI_API_KEY:
                raise ValueError("KALSHI_API_KEY required for Kalshi")
            if not self.KALSHI_PRIVATE_KEY_PATH:
                raise ValueError("KALSHI_PRIVATE_KEY_PATH required for Kalshi")
            if not os.path.exists(self.KALSHI_PRIVATE_KEY_PATH):
                raise ValueError(
                    f"Kalshi private key file not found: "
                    f"{self.KALSHI_PRIVATE_KEY_PATH}"
                )
