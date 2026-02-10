"""
Basic TTScraper Setup Example

This example demonstrates the basic initialization and configuration of TTScraper
with proper error handling and logging setup, using nodriver (async CDP).
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path to import TTScraper modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TTScraper import TTScraper


def setup_logging(level=logging.INFO):
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ttscraper_example.log')
        ]
    )
    return logging.getLogger("TTScraper.Example")


async def basic_setup_example():
    """
    Demonstrate basic TTScraper setup with logging and error handling.
    """
    logger = setup_logging(level=logging.INFO)
    logger.info("🚀 Starting TTScraper Basic Setup Example")

    scraper = None
    try:
        # Initialize TTScraper with default settings
        logger.info("Initializing TTScraper...")
        scraper = TTScraper()

        # Start the browser (returns a nodriver Tab)
        logger.info("Starting browser...")
        tab = await scraper.start_browser()

        # Verify the tab is working
        logger.info("Verifying browser functionality...")
        await tab.get("https://www.tiktok.com")

        logger.info("✓ Successfully loaded TikTok homepage")

        # Show browser capabilities
        user_agent = await tab.evaluate("navigator.userAgent")
        logger.info(f"\nBrowser Configuration:")
        logger.info(f"  - User Agent: {user_agent}")
        logger.info(f"  - Tab is ready for scraping operations")

        # Keep browser open for demonstration (remove in production)
        input("\nPress Enter to close the browser...")

    except Exception as e:
        logger.error(f"❌ Error in basic setup: {e}")
        raise
    finally:
        if scraper:
            scraper.close()
            logger.info("✓ Browser closed successfully")


async def advanced_setup_example():
    """
    Demonstrate advanced TTScraper setup with custom configuration.
    """
    logger = setup_logging(level=logging.DEBUG)
    logger.info("🔧 Starting TTScraper Advanced Setup Example")

    scraper = None
    try:
        # Initialize TTScraper with custom parameters
        logger.info("Initializing TTScraper with custom configuration...")

        custom_args = [
            "--disable-images",
            "--disable-plugins",
            "--window-size=1920,1080",
            "--disable-extensions",
            "--no-first-run",
            "--disable-default-apps",
        ]

        scraper = TTScraper(args=custom_args)

        # Start browser with advanced configuration
        logger.info("Starting browser with advanced monitoring...")
        tab = await scraper.start_browser(headless=False)

        # Navigate with timing
        import time
        start_time = time.time()
        await tab.get("https://www.tiktok.com")
        load_time = time.time() - start_time

        logger.info(f"✓ Page loaded in {load_time:.2f} seconds")

        # Check performance metrics via JS
        performance_data = await tab.evaluate("""
            (function() {
                return {
                    loadTime: window.performance.timing.loadEventEnd - window.performance.timing.navigationStart,
                    domContentLoaded: window.performance.timing.domContentLoadedEventEnd - window.performance.timing.navigationStart,
                    firstPaint: (window.performance.getEntriesByType('paint')[0] || {}).startTime || 0
                };
            })()
        """)

        logger.info("Performance Metrics:")
        logger.info(f"  - Total Load Time: {performance_data['loadTime']}ms")
        logger.info(f"  - DOM Content Loaded: {performance_data['domContentLoaded']}ms")
        logger.info(f"  - First Paint: {performance_data['firstPaint']}ms")

        # Test error handling with a non-existent element
        logger.info("Testing error handling...")
        try:
            result = await tab.evaluate("document.getElementById('non-existent-element')")
            logger.info(f"✓ Error handling working: element returned {result}")
        except Exception as e:
            logger.info(f"✓ Error handling working: {type(e).__name__}")

        input("\nPress Enter to close the browser...")

    except Exception as e:
        logger.error(f"❌ Error in advanced setup: {e}")
        raise
    finally:
        if scraper:
            scraper.close()
            logger.info("✓ Browser closed successfully")


if __name__ == "__main__":
    print("TTScraper Basic Setup Examples")
    print("=" * 40)
    print("1. Basic Setup")
    print("2. Advanced Setup")
    print("3. Exit")

    choice = input("\nChoose an example (1-3): ").strip()

    if choice == "1":
        asyncio.run(basic_setup_example())
    elif choice == "2":
        asyncio.run(advanced_setup_example())
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice. Please run again.")
