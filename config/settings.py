"""
Configuration management for TTScraper
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import os


@dataclass
class BrowserConfig:
    """Browser configuration settings"""
    headless: bool = False
    user_data_dir: Optional[str] = None
    profile_directory: str = "Profile 1"
    window_size: tuple = (1920, 1080)
    disable_blink_features: Optional[List[str]] = None
    chrome_args: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.user_data_dir is None:
            self.user_data_dir = os.getcwd()
        if self.disable_blink_features is None:
            self.disable_blink_features = ["AutomationControlled"]
        if self.chrome_args is None:
            self.chrome_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--no-first-run",
                "--disable-default-apps"
            ]


@dataclass 
class ScrapingConfig:
    """Scraping behavior configuration"""
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 2.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    
    
@dataclass
class NetworkConfig:
    """Network monitoring configuration"""
    enable_cdp: bool = True
    capture_headers: bool = True
    capture_request_body: bool = False
    max_buffer_size: int = 10000000  # 10MB
    max_resource_buffer: int = 5000000  # 5MB


@dataclass
class TTScraperConfig:
    """Main configuration class"""
    browser: Optional[BrowserConfig] = None
    scraping: Optional[ScrapingConfig] = None
    network: Optional[NetworkConfig] = None
    
    def __post_init__(self):
        if self.browser is None:
            self.browser = BrowserConfig()
        if self.scraping is None:
            self.scraping = ScrapingConfig()
        if self.network is None:
            self.network = NetworkConfig()


# Default configuration instance
DEFAULT_CONFIG = TTScraperConfig()
