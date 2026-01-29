import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import polars as pl


class DatabaseManager:
    """Handles SQLite persistence for market price history."""

    def __init__(self, config):
        self.logger = logging.getLogger("TradingBot.DatabaseManager")
        # Use path from config or default to data directory
        self.db_path = getattr(config, "DB_PATH", "data/bot_history.db")
        self._init_db()
        self.prune_old_data(days=3)

    def _init_db(self):
        """Initialize the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS price_history (
                        market_id TEXT,
                        timestamp DATETIME,
                        price REAL,
                        yes_price REAL,
                        no_price REAL,
                        liquidity REAL,
                        PRIMARY KEY (market_id, timestamp)
                    )
                """)
                # Index for faster strategy lookups
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_market_time ON price_history (market_id, timestamp)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_timestamp ON price_history (timestamp)"
                )
                self.logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")

    def save_markets(self, markets: List[Any]):
        """Save a batch of market updates to the database."""
        now = datetime.now().isoformat()
        data = [
            (m.market_id, now, m.price, m.yes_price, m.no_price, m.liquidity_usd)
            for m in markets
        ]
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO price_history VALUES (?, ?, ?, ?, ?, ?)",
                    data,
                )
        except Exception as e:
            self.logger.error(f"Failed to save market batch to DB: {e}")

    def prune_old_data(self, days: int = 7):
        """Delete data older than X days to keep DB size manageable."""
        limit = (datetime.now() - timedelta(days=days)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM price_history WHERE timestamp < ?", (limit,)
                )
                if cursor.rowcount > 0:
                    self.logger.info(f"Pruned {cursor.rowcount} old price records")
        except Exception as e:
            self.logger.error(f"Failed to prune database: {e}")

    def get_recent_history(
        self, market_ids: List[str] = None, hours: int = 24
    ) -> Dict[str, List]:
        """
        Load recent history from the database.
        Returns a format compatible with StrategyManager.
        """
        history = {}  # Initialize early to avoid UnboundLocalError
        limit_per_market = 40
        since_ts = (datetime.now() - timedelta(hours=hours)).isoformat()

        market_filter = ""
        params = [since_ts]
        if market_ids:
            placeholders = ",".join(["?"] * len(market_ids))
            market_filter = f"AND market_id IN ({placeholders})"
            params.extend(market_ids)

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Debug: Check if table has any data at all
                total_rows = conn.execute(
                    "SELECT COUNT(*) FROM price_history"
                ).fetchone()[0]
                if total_rows == 0:
                    self.logger.warning("Database is empty. No history to load.")
                    return {}

                query = f"""
                    SELECT market_id, price, timestamp FROM (
                        SELECT 
                            market_id, price, timestamp,
                            ROW_NUMBER() OVER (PARTITION BY market_id ORDER BY timestamp DESC) as rn
                        FROM price_history
                        WHERE timestamp > ? {market_filter}
                    ) WHERE rn <= {limit_per_market}
                    ORDER BY timestamp ASC
                """

                # Execute via sqlite3 for maximum compatibility with Polars versions
                cursor = conn.execute(query, tuple(params))
                rows = cursor.fetchall()

                if not rows:
                    self.logger.info(f"No recent history found since {since_ts}")
                    return {}

                # Load into Polars for high-speed datetime parsing
                df = pl.DataFrame(
                    rows, schema=["market_id", "price", "timestamp"], orient="row"
                )
                self.logger.info(
                    f"Fetched {len(df)} historical points. Processing with Polars..."
                )

                # Convert to required dictionary format
                df = df.with_columns(pl.col("timestamp").str.to_datetime())

                # Reconstruct the history dictionary
                for m_id_tuple, group in df.group_by("market_id"):
                    # Polars group_by keys are returned as tuples
                    m_id = (
                        m_id_tuple[0] if isinstance(m_id_tuple, tuple) else m_id_tuple
                    )
                    history[m_id] = list(zip(group["price"], group["timestamp"]))

                return history

        except Exception as e:
            self.logger.error(f"Failed to load history from DB: {e}")
        return history
