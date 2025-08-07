from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Optional, Union, Dict, Any
import logging
import json
import time
import requests
from urllib.parse import urljoin, urlparse
from selenium.webdriver.chrome.webdriver import WebDriver
from TTScraper import TTScraper

# Import all the classes
from video import Video
from user import User
from sound import Sound
from hashtag import Hashtag
from comment import Comment

if TYPE_CHECKING:
    pass


class TikTokApi:
    """
    The main TikTok API class using Selenium with undetected chromedriver.
    
    This class coordinates all the other classes (Video, User, Sound, etc.)
    and provides a unified interface for TikTok scraping.

    Example Usage:
    ```py
    api = TikTokApi()
    api.start_session()
    
    # Get video info
    video = api.video(url="https://www.tiktok.com/@user/video/123")
    video_info = video.info()
    
    # Get user info
    user = api.user(username="therock")
    user_info = user.info()
    
    api.close_session()
    ```
    """

    def __init__(self, **kwargs):
        """
        Initialize the TikTok API.
        
        Args:
            **kwargs: Arguments to pass to TTScraper
        """
        self.scraper = None
        self.driver = None
        self.scraper_kwargs = kwargs
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()  # For API requests
        self._session_headers = {}
        
        # Set up logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Set parent reference for all classes
        Video.parent = self
        User.parent = self
        Sound.parent = self
        Hashtag.parent = self
        Comment.parent = self

    def start_session(self, **kwargs) -> WebDriver:
        """
        Start a new Selenium session with undetected chromedriver.
        
        Args:
            **kwargs: Additional arguments for TTScraper
            
        Returns:
            WebDriver: The Selenium WebDriver instance
        """
        if self.driver is not None:
            self.logger.warning("Session already started. Closing existing session.")
            self.close_session()
        
        # Merge kwargs with instance kwargs
        merged_kwargs = {**self.scraper_kwargs, **kwargs}
        
        self.logger.info("Starting TikTok scraping session...")
        self.scraper = TTScraper()
        self.driver = self.scraper.start_driver(**merged_kwargs)
        
        # Update session headers and cookies for API requests
        self._update_session_from_driver()
        
        self.logger.info("Session started successfully")
        return self.driver

    def close_session(self):
        """Close the current Selenium session."""
        if self.driver:
            self.logger.info("Closing TikTok scraping session...")
            self.driver.quit()
            self.driver = None
            self.scraper = None
            self.logger.info("Session closed")

    def get_driver(self) -> Optional[WebDriver]:
        """Get the current WebDriver instance."""
        return self.driver

    def ensure_session(self):
        """Ensure a session is active, start one if not."""
        if self.driver is None:
            self.start_session()

    # Factory methods for creating instances
    
    def video(
        self, 
        id: Optional[str] = None, 
        url: Optional[str] = None, 
        data: Optional[dict] = None,
        **kwargs
    ) -> Video:
        """
        Create a Video instance.
        
        Args:
            id: TikTok video ID
            url: TikTok video URL
            data: Pre-loaded video data
            **kwargs: Additional arguments
            
        Returns:
            Video: Video instance
        """
        self.ensure_session()
        video = Video(id=id, url=url, data=data, driver=self.driver, **kwargs)
        video.parent = self  # type: ignore # Explicitly set parent reference
        return video

    def user(
        self, 
        username: Optional[str] = None, 
        sec_uid: Optional[str] = None,
        user_id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs
    ) -> User:
        """
        Create a User instance.
        
        Args:
            username: TikTok username (without @)
            sec_uid: TikTok sec_uid
            user_id: TikTok user ID
            data: Pre-loaded user data
            **kwargs: Additional arguments
            
        Returns:
            User: User instance
        """
        self.ensure_session()
        user = User(username=username, sec_uid=sec_uid, user_id=user_id, data=data, driver=self.driver, **kwargs)
        user.parent = self  # type: ignore # Explicitly set parent reference
        return user

    def sound(
        self, 
        id: Optional[str] = None, 
        data: Optional[dict] = None,
        **kwargs
    ) -> Sound:
        """
        Create a Sound instance.
        
        Args:
            id: TikTok sound ID
            data: Pre-loaded sound data
            **kwargs: Additional arguments
            
        Returns:
            Sound: Sound instance
        """
        sound = Sound(id=id, data=data, **kwargs)
        sound.parent = self  # type: ignore # Explicitly set parent reference
        return sound

    def hashtag(
        self, 
        name: Optional[str] = None, 
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs
    ) -> Hashtag:
        """
        Create a Hashtag instance.
        
        Args:
            name: Hashtag name (without #)
            id: TikTok hashtag ID
            data: Pre-loaded hashtag data
            **kwargs: Additional arguments
            
        Returns:
            Hashtag: Hashtag instance
        """
        return Hashtag(name=name, id=id, data=data, **kwargs)

    def comment(
        self, 
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs
    ) -> Comment:
        """
        Create a Comment instance.
        
        Args:
            id: TikTok comment ID
            data: Pre-loaded comment data
            **kwargs: Additional arguments
            
        Returns:
            Comment: Comment instance
        """
        return Comment(id=id, data=data, **kwargs)

    # Convenience methods for quick operations
    
    def get_video_info(self, url: str, **kwargs) -> dict:
        """
        Quick method to get video information.
        
        Args:
            url: TikTok video URL
            **kwargs: Additional arguments
            
        Returns:
            dict: Video information
        """
        video = self.video(url=url)
        return video.info(**kwargs)

    def get_user_info(self, username: str, **kwargs) -> dict:
        """
        Quick method to get user information.
        
        Args:
            username: TikTok username (without @)
            **kwargs: Additional arguments
            
        Returns:
            dict: User information
        """
        user = self.user(username=username)
        return user.info(**kwargs)

    def download_video(self, url: str, filename: Optional[str] = None, **kwargs) -> Union[bytes, str]:
        """
        Quick method to download a video.
        
        Args:
            url: TikTok video URL
            filename: Output filename (optional)
            **kwargs: Additional arguments
            
        Returns:
            bytes if no filename, filename if saved to file
        """
        video = self.video(url=url)
        video.info(**kwargs)
        
        # Use the bytes method from Video class
        video_bytes = video.bytes(**kwargs)
        
        if filename:
            with open(filename, 'wb') as f:
                if hasattr(video_bytes, '__iter__') and not isinstance(video_bytes, bytes):
                    # It's a generator/iterator
                    for chunk in video_bytes:
                        if isinstance(chunk, bytes):
                            f.write(chunk)
                else:
                    if isinstance(video_bytes, bytes):
                        f.write(video_bytes)
            return filename
        else:
            if isinstance(video_bytes, bytes):
                return video_bytes
            else:
                # If it's an iterator, collect all bytes
                collected_bytes = b''
                for chunk in video_bytes:
                    if isinstance(chunk, bytes):
                        collected_bytes += chunk
                return collected_bytes

    # Session management methods
    
    def set_proxy(self, proxy: str):
        """
        Set proxy for the session.
        Note: This requires restarting the session.
        
        Args:
            proxy: Proxy string (e.g., "http://proxy:port")
        """
        self.scraper_kwargs['proxy'] = proxy
        if self.driver:
            self.logger.info("Proxy set. Restarting session...")
            self.close_session()
            self.start_session()

    def set_headless(self, headless: bool):
        """
        Set headless mode for the session.
        Note: This requires restarting the session.
        
        Args:
            headless: Whether to run in headless mode
        """
        self.scraper_kwargs['headless'] = headless
        if self.driver:
            self.logger.info("Headless mode changed. Restarting session...")
            self.close_session()
            self.start_session()

    def add_session_cookies(self, cookies: list):
        """Add cookies to the current session."""
        if self.driver:
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.warning(f"Failed to add cookie: {e}")
            
            # Update the requests session as well
            self._update_session_from_driver()

    def navigate_to(self, url: str):
        """Navigate to a specific URL."""
        self.ensure_session()
        if self.driver:
            self.driver.get(url)

    def wait(self, seconds: float):
        """Wait for a specified number of seconds."""
        time.sleep(seconds)

    def _update_session_from_driver(self):
        """Update the requests session with cookies and headers from the Selenium driver."""
        if not self.driver:
            return
        
        # Get cookies from driver
        selenium_cookies = self.driver.get_cookies()
        
        # Clear existing cookies and add new ones
        self.session.cookies.clear()
        for cookie in selenium_cookies:
            self.session.cookies.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', '.tiktok.com'),
                path=cookie.get('path', '/'),
                secure=cookie.get('secure', False)
            )
        
        # Set common headers that mimic browser requests
        user_agent = self.driver.execute_script("return navigator.userAgent;")
        
        self._session_headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.tiktok.com/',
            'Origin': 'https://www.tiktok.com'
        }
        
        self.session.headers.update(self._session_headers)

    def _get_session(self, session_index: Optional[int] = None, **kwargs):
        """
        Get session information for compatibility with original TikTokAPI.
        
        Args:
            session_index: Session index (unused in Selenium implementation)
            **kwargs: Additional arguments
            
        Returns:
            tuple: (session_index, session_object)
        """
        # Update session from driver if needed
        if self.driver:
            self._update_session_from_driver()
        
        # Create a session object that mimics the original API
        session_obj = type('Session', (), {
            'headers': self._session_headers,
            'cookies': dict(self.session.cookies),
            'proxy': kwargs.get('proxy')
        })()
        
        return 0, session_obj

    def make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        session_index: Optional[int] = None,
        method: str = 'GET',
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Make an HTTP request using the current session cookies and headers.
        
        This function mimics the behavior of the original TikTokAPI make_request
        but uses the Selenium driver's session for authentication.
        
        Args:
            url: The URL to make the request to
            params: Query parameters to include in the request
            headers: Additional headers to include
            session_index: Session index (unused in Selenium implementation)
            method: HTTP method (GET, POST, etc.)
            data: Data to send in POST requests
            timeout: Request timeout in seconds
            **kwargs: Additional arguments
            
        Returns:
            dict: JSON response data, or None if request failed
            
        Raises:
            requests.RequestException: If the request fails
        """
        self.ensure_session()
        
        # Update session from driver to get latest cookies
        self._update_session_from_driver()
        
        # Merge headers
        request_headers = self._session_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Ensure we have the required headers for TikTok API
        if 'Referer' not in request_headers:
            request_headers['Referer'] = 'https://www.tiktok.com/'
        
        if 'Origin' not in request_headers:
            request_headers['Origin'] = 'https://www.tiktok.com'
        
        # Get proxy from kwargs or session
        proxy = kwargs.get('proxy')
        proxies = None
        if proxy:
            proxies = {
                'http': proxy,
                'https': proxy
            }
        
        try:
            self.logger.debug(f"Making {method} request to: {url}")
            self.logger.debug(f"Params: {params}")
            self.logger.debug(f"Headers: {request_headers}")
            
            # Make the request
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=request_headers,
                json=data if method.upper() == 'POST' and data else None,
                data=data if method.upper() == 'POST' and not isinstance(data, dict) else None,
                timeout=timeout,
                proxies=proxies,
                allow_redirects=True
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if request was successful
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    self.logger.warning("Response is not valid JSON")
                    return None
            elif response.status_code == 429:
                self.logger.warning("Rate limited by TikTok (429)")
                return None
            elif response.status_code == 403:
                self.logger.warning("Access forbidden (403) - may need to refresh session")
                return None
            else:
                self.logger.warning(f"Request failed with status {response.status_code}")
                self.logger.debug(f"Response text: {response.text[:500]}...")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in make_request: {e}")
            return None

    def set_session_cookies(self, session, cookies: list):
        """
        Set cookies for a session (compatibility with original API).
        
        Args:
            session: Session object (unused in Selenium implementation)
            cookies: List of cookies to set
        """
        if self.driver:
            # Add cookies to the Selenium driver
            current_url = self.driver.current_url
            if not current_url.startswith('https://www.tiktok.com'):
                self.driver.get('https://www.tiktok.com')
            
            for cookie in cookies:
                try:
                    # Convert playwright-style cookie to selenium format if needed
                    selenium_cookie = {
                        'name': cookie.get('name'),
                        'value': cookie.get('value'),
                        'domain': cookie.get('domain', '.tiktok.com'),
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', False)
                    }
                    
                    # Remove None values
                    selenium_cookie = {k: v for k, v in selenium_cookie.items() if v is not None}
                    
                    self.driver.add_cookie(selenium_cookie)
                except Exception as e:
                    self.logger.warning(f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}")
            
            # Update the requests session as well
            self._update_session_from_driver()

    def get_session_cookies(self, session=None) -> Dict[str, str]:
        """
        Get session cookies (compatibility with original API).
        
        Args:
            session: Session object (unused in Selenium implementation)
            
        Returns:
            dict: Dictionary of cookie name-value pairs
        """
        if self.driver:
            selenium_cookies = self.driver.get_cookies()
            return {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        return {}

    def refresh_session(self):
        """Refresh the session by updating cookies and headers from the driver."""
        if self.driver:
            self._update_session_from_driver()
            self.logger.info("Session refreshed with latest cookies and headers")

    def __enter__(self):
        """Context manager entry."""
        self.start_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_session()

    def __del__(self):
        """Destructor to ensure session is closed."""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.close_session()
            except:
                pass
