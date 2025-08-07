"""
Basic TTScraper Setup Example

This example demonstrates the basic initialization and configuration of TTScraper
with proper error handling and logging setup.
"""

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


def basic_setup_example():
    """
    Demonstrate basic TTScraper setup with logging and error handling.
    """
    # Setup logging
    logger = setup_logging(level=logging.INFO)
    logger.info("🚀 Starting TTScraper Basic Setup Example")
    
    try:
        # Initialize TTScraper with default settings
        logger.info("Initializing TTScraper...")
        scraper = TTScraper()
        
        # Start the browser driver
        logger.info("Starting Chrome driver...")
        driver = scraper.start_driver()
        
        # Verify the driver is working
        logger.info("Verifying driver functionality...")
        driver.get("https://www.tiktok.com")
        
        logger.info(f"✓ Successfully loaded TikTok homepage")
        logger.info(f"✓ Current page title: {driver.title}")
        logger.info(f"✓ Driver is ready for scraping operations")
        
        # Show driver capabilities
        logger.info("\nDriver Configuration:")
        logger.info(f"  - User Agent: {driver.execute_script('return navigator.userAgent;')}")
        logger.info(f"  - Window Size: {driver.get_window_size()}")
        logger.info(f"  - Session ID: {driver.session_id}")
        
        # Keep browser open for demonstration (remove in production)
        input("\nPress Enter to close the browser...")
        
    except Exception as e:
        logger.error(f"❌ Error in basic setup: {e}")
        raise
    finally:
        # Always clean up
        try:
            driver.quit()
            logger.info("✓ Browser closed successfully")
        except:
            logger.warning("⚠️ Could not close browser cleanly")


def advanced_setup_example():
    """
    Demonstrate advanced TTScraper setup with custom configuration.
    """
    logger = setup_logging(level=logging.DEBUG)
    logger.info("🔧 Starting TTScraper Advanced Setup Example")
    
    try:
        # Initialize TTScraper with custom parameters
        logger.info("Initializing TTScraper with custom configuration...")
        
        # Custom Chrome options
        custom_args = [
            "--disable-images",           # Faster loading
            "--disable-css",              # Faster loading  
            "--disable-plugins",          # Reduce memory usage
            "--window-size=1920,1080",    # Set specific window size
            "--disable-extensions",       # Disable extensions
            "--disable-web-security",     # For testing only
            "--no-first-run",            # Skip first run experience
            "--disable-default-apps"      # Disable default apps
        ]
        
        scraper = TTScraper(args=custom_args)
        
        # Start driver with advanced configuration
        logger.info("Starting driver with advanced monitoring...")
        driver = scraper.start_driver(
            headless=False,              # Show browser for debugging
            profile_directory="Default", # Use default profile
            enable_cdp_events=True,      # Enable Chrome DevTools Protocol
            log_level=0,                 # Verbose logging
            debug=True,                  # Enable debug mode
            no_sandbox=True,             # Required for many environments
            suppress_welcome=True,       # Suppress welcome message
            use_subprocess=True          # Use subprocess for stability
        )
        
        # Test advanced features
        logger.info("Testing advanced browser features...")
        
        # Enable console logging capture
        driver.execute_cdp_cmd('Runtime.enable', {})
        driver.execute_cdp_cmd('Console.enable', {})
        
        # Navigate with timing
        import time
        start_time = time.time()
        driver.get("https://www.tiktok.com")
        load_time = time.time() - start_time
        
        logger.info(f"✓ Page loaded in {load_time:.2f} seconds")
        
        # Check performance metrics
        performance_data = driver.execute_script("""
            return {
                loadTime: window.performance.timing.loadEventEnd - window.performance.timing.navigationStart,
                domContentLoaded: window.performance.timing.domContentLoadedEventEnd - window.performance.timing.navigationStart,
                firstPaint: window.performance.getEntriesByType('paint')[0]?.startTime || 0
            };
        """)
        
        logger.info(f"Performance Metrics:")
        logger.info(f"  - Total Load Time: {performance_data['loadTime']}ms")
        logger.info(f"  - DOM Content Loaded: {performance_data['domContentLoaded']}ms")
        logger.info(f"  - First Paint: {performance_data['firstPaint']}ms")
        
        # Test error handling
        logger.info("Testing error handling...")
        try:
            # Try to find a non-existent element (should fail gracefully)
            driver.find_element("id", "non-existent-element")
        except Exception as e:
            logger.info(f"✓ Error handling working: {type(e).__name__}")
        
        input("\nPress Enter to close the browser...")
        
    except Exception as e:
        logger.error(f"❌ Error in advanced setup: {e}")
        raise
    finally:
        try:
            driver.quit()
            logger.info("✓ Browser closed successfully")
        except:
            logger.warning("⚠️ Could not close browser cleanly")


if __name__ == "__main__":
    print("TTScraper Basic Setup Examples")
    print("=" * 40)
    print("1. Basic Setup")
    print("2. Advanced Setup")
    print("3. Exit")
    
    choice = input("\nChoose an example (1-3): ").strip()
    
    if choice == "1":
        basic_setup_example()
    elif choice == "2":
        advanced_setup_example()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice. Please run again.")
