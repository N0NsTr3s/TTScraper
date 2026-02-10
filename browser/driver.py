"""
Enhanced TTScraper driver with configuration support (nodriver-based).
"""
import logging
import os
from typing import Optional, Any

import nodriver as uc


class EnhancedTTScraper:
    """
    Enhanced TTScraper with better configuration management and reduced complexity.

    Uses ``nodriver`` for async CDP-based browser automation.
    """

    def __init__(self, config=None):
        from ..config.settings import DEFAULT_CONFIG
        self.config = config or DEFAULT_CONFIG
        self.browser: Optional[uc.Browser] = None
        self.tab: Optional[uc.Tab] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start_driver(self, url: str = "https://www.tiktok.com/", **kwargs) -> uc.Tab:
        """
        Start Chrome browser with configuration via nodriver.

        Args:
            url: Initial URL to navigate to
            **kwargs: Override configuration options

        Returns:
            nodriver.Tab: The active browser tab.
        """
        try:
            browser_args: list[str] = []

            # Apply basic configuration with safe defaults
            user_data_dir = kwargs.get(
                "user_data_dir",
                getattr(self.config.browser, "user_data_dir", None)
                if self.config.browser
                else None,
            )

            # Only add chrome_args the user explicitly configured
            chrome_args = (
                getattr(self.config.browser, "chrome_args", [])
                if self.config.browser
                else []
            )
            for arg in chrome_args or []:
                browser_args.append(arg)

            # Override with kwargs
            headless = kwargs.get(
                "headless",
                getattr(self.config.browser, "headless", False)
                if self.config.browser
                else False,
            )

            # Build nodriver Config
            config = uc.Config()
            config.headless = headless

            # nodriver's add_argument rejects args it manages via attributes
            _managed = ("headless", "data-dir", "data_dir", "no-sandbox", "no_sandbox", "lang")
            for arg in browser_args:
                if any(m in arg.lower() for m in _managed):
                    if "no-sandbox" in arg.lower() or "no_sandbox" in arg.lower():
                        config.sandbox = False
                    continue
                config.add_argument(arg)

            if not user_data_dir:
                user_data_dir = os.path.join(os.getcwd(), "browser_profiles")
            os.makedirs(user_data_dir, exist_ok=True)
            config.user_data_dir = user_data_dir

            # Create browser
            self.browser = await uc.start(config)

            # Navigate to initial URL
            self.tab = await self.browser.get(url)

            # Enable network monitoring if requested
            enable_cdp = (
                getattr(self.config.network, "enable_cdp", True)
                if self.config.network
                else True
            )
            if enable_cdp:
                try:
                    import nodriver.cdp.network as net
                    await self.tab.send(net.enable())
                    self.logger.debug("Network monitoring enabled")
                except Exception as e:
                    self.logger.warning(f"Could not enable network monitoring: {e}")

            self.logger.info(f"Browser started successfully, navigated to: {url}")
            return self.tab

        except Exception as e:
            self.logger.error(f"Failed to start browser: {e}")
            raise

    def close_driver(self) -> None:
        """Close the browser safely."""
        if self.browser:
            try:
                self.browser.stop()
                self.logger.info("Browser closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")
            finally:
                self.browser = None
                self.tab = None
