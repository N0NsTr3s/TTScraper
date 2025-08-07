"""
Enhanced TTScraper driver with configuration support.
"""
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import logging


class EnhancedTTScraper:
    """
    Enhanced TTScraper with better configuration management and reduced complexity.
    """
    
    def __init__(self, config=None):
        from ..config.settings import DEFAULT_CONFIG
        self.config = config or DEFAULT_CONFIG
        self.driver = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def start_driver(self, url="https://www.tiktok.com/", **kwargs):
        """
        Start Chrome driver with configuration.
        
        Args:
            url: Initial URL to navigate to
            **kwargs: Override configuration options
        """
        try:
            # Set up Chrome options
            options = Options()
            
            # Apply basic configuration with safe defaults
            user_data_dir = kwargs.get('user_data_dir', getattr(self.config.browser, 'user_data_dir', None) if self.config.browser else None)
            profile_dir = kwargs.get('profile_directory', getattr(self.config.browser, 'profile_directory', 'Profile 1') if self.config.browser else 'Profile 1')
            
            if user_data_dir:
                options.add_argument(f"--user-data-dir={user_data_dir}")
            if profile_dir:
                options.add_argument(f"--profile-directory={profile_dir}")
            
            # Add Chrome arguments from config
            chrome_args = getattr(self.config.browser, 'chrome_args', []) if self.config.browser else []
            for arg in chrome_args or []:
                options.add_argument(arg)
            
            # Override with kwargs
            headless = kwargs.get('headless', getattr(self.config.browser, 'headless', False) if self.config.browser else False)
            if headless:
                options.add_argument("--headless")
            
            # Additional options for better stability
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Create driver
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=ChromeDriverManager().install(),
                use_subprocess=kwargs.get('use_subprocess', True),
                version_main=kwargs.get('version_main'),
                port=kwargs.get('port', 0)
            )
            
            # Navigate to initial URL
            self.driver.get(url)
            
            # Enable network monitoring if requested
            enable_cdp = getattr(self.config.network, 'enable_cdp', True) if self.config.network else True
            if enable_cdp:
                try:
                    self.driver.execute_cdp_cmd("Network.enable", {})
                    self.logger.debug("Network monitoring enabled")
                except Exception as e:
                    self.logger.warning(f"Could not enable network monitoring: {e}")
            
            self.logger.info(f"Driver started successfully, navigated to: {url}")
            return self.driver
            
        except Exception as e:
            self.logger.error(f"Failed to start driver: {e}")
            raise
    
    def close_driver(self):
        """Close the driver safely."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Driver closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
