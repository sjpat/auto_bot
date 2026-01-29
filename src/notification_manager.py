import aiohttp
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Manages sending notifications to external services (Telegram, etc.)
    """

    def __init__(self, config):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

        if self.enabled:
            self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            logger.info("✅ Telegram notifications enabled")
        else:
            logger.info("ℹ️ Telegram notifications disabled (missing token/chat_id)")

    async def send_message(self, message: str):
        """Send a text message to Telegram."""
        if not self.enabled:
            return

        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(
                            f"Failed to send Telegram message: {await response.text()}"
                        )
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    async def send_trade_alert(
        self, market_id: str, side: str, price: float, quantity: int, strategy: str
    ):
        """Format and send a trade entry alert."""
        icon = "🟢" if side.lower() == "buy" else "🔴"
        msg = (
            f"{icon} *TRADE EXECUTED*\n"
            f"Market: `{market_id}`\n"
            f"Side: *{side.upper()}*\n"
            f"Price: `${price:.4f}`\n"
            f"Qty: `{quantity}`\n"
            f"Strategy: _{strategy}_"
        )
        await self.send_message(msg)

    async def send_exit_alert(
        self, market_id: str, pnl: float, reason: str, return_pct: float
    ):
        """Format and send a trade exit alert."""
        icon = "💰" if pnl > 0 else "🔻"
        msg = (
            f"{icon} *POSITION CLOSED*\n"
            f"Market: `{market_id}`\n"
            f"PnL: `${pnl:+.2f}` ({return_pct:+.2%})\n"
            f"Reason: _{reason}_"
        )
        await self.send_message(msg)

    async def send_error(self, error_msg: str):
        """Send critical error alert."""
        await self.send_message(f"⚠️ *CRITICAL ERROR*\n`{error_msg}`")
