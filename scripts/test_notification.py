#!/usr/bin/env python3
"""
Test Telegram Notification Integration
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.notification_manager import NotificationManager


async def main():
    print("🔔 Testing Telegram Notification...")
    config = Config()
    notifier = NotificationManager(config)

    if not notifier.enabled:
        print(
            "❌ Notifications are disabled in config (check .env for TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)"
        )
        return

    await notifier.send_message(
        "✅ *Test Notification*\nIf you see this, the bot can reach you!"
    )
    print("✅ Message sent! Check your Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
