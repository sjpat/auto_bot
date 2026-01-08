"""
Test logger functionality.
"""

from src.logger import setup_logger, LoggerContextManager

def test_logger():
    """Test basic logger functionality."""
    print("Testing logger...")
    
    # Setup logger
    logger = setup_logger(
        name="kalshi_bot",
        log_file="logs/kalshi_bot.log",
        level="INFO"
    )
    
    # Test different levels
    logger.debug("Debug message (should NOT appear in console)")
    logger.info("✅ Info message (should appear)")
    logger.warning("⚠️ Warning message")
    logger.error("❌ Error message")
    
    # Test exception logging
    try:
        raise ValueError("Test exception")
    except ValueError:
        logger.error("Exception caught:", exc_info=True)
    
    print("✅ Logger test complete!")
    print("Check logs/kalshi_bot.log for detailed output")

if __name__ == "__main__":
    test_logger()
