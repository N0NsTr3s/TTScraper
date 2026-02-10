from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Optional, Union, Dict, Any
import asyncio
import logging
import json
import time
import requests
from urllib.parse import urljoin, urlparse

import nodriver as uc

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
    The main TikTok API class using nodriver (async CDP browser).

    This class coordinates all the other classes (Video, User, Sound, etc.)
    and provides a unified interface for TikTok scraping.

    Example Usage:
    ```py
    import asyncio

    async def main():
        api = TikTokApi()
        await api.start_session()

        # Get video info
        video = api.video(url="https://www.tiktok.com/@user/video/123")
        video_info = await video.info()

        # Get user info
        user = api.user(username="therock")
        user_info = await user.info()

        api.close_session()

    asyncio.run(main())
    ```
    """

    def __init__(self, **kwargs):
        """
        Initialize the TikTok API.

        Args:
            **kwargs: Arguments to pass to TTScraper
        """
        self.scraper: Optional[TTScraper] = None
        self.tab: Optional[uc.Tab] = None
        self.scraper_kwargs = kwargs
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()  # For API requests
        self._session_headers: Dict[str, str] = {}

        # Set up logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # Set parent reference for all classes
        Video.parent = self
        User.parent = self
        Sound.parent = self
        Hashtag.parent = self
        Comment.parent = self

    async def start_session(self, **kwargs) -> uc.Tab:
        """
        Start a new browser session with nodriver.

        Args:
            **kwargs: Additional arguments for TTScraper

        Returns:
            nodriver.Tab: The active browser tab
        """
        if self.tab is not None:
            self.logger.warning("Session already started. Closing existing session.")
            self.close_session()

        # Merge kwargs with instance kwargs
        merged_kwargs = {**self.scraper_kwargs, **kwargs}

        self.logger.info("Starting TikTok scraping session...")
        self.scraper = TTScraper()
        self.tab = await self.scraper.start_browser(**merged_kwargs)

        # Update session headers and cookies for API requests
        await self._update_session_from_tab()

        self.logger.info("Session started successfully")
        return self.tab

    def close_session(self) -> None:
        """Close the current browser session."""
        if self.scraper:
            self.logger.info("Closing TikTok scraping session...")
            self.scraper.close()
            self.tab = None
            self.scraper = None
            self.logger.info("Session closed")

    def get_tab(self) -> Optional[uc.Tab]:
        """Get the current Tab instance."""
        return self.tab

    # Backward-compat alias
    def get_driver(self) -> Optional[uc.Tab]:
        """Get the current Tab instance (backward-compat alias)."""
        return self.tab

    async def ensure_session(self) -> None:
        """Ensure a session is active, start one if not."""
        if self.tab is None:
            await self.start_session()

    # Factory methods for creating instances

    def video(
        self,
        id: Optional[str] = None,
        url: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
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
        video = Video(id=id, url=url, data=data, tab=self.tab, **kwargs)
        video.parent = self  # type: ignore
        return video

    def user(
        self,
        username: Optional[str] = None,
        sec_uid: Optional[str] = None,
        user_id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
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
        user = User(
            username=username,
            sec_uid=sec_uid,
            user_id=user_id,
            data=data,
            tab=self.tab,
            **kwargs,
        )
        user.parent = self  # type: ignore
        return user

    def sound(
        self,
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
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
        sound.parent = self  # type: ignore
        return sound

    def hashtag(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
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
        **kwargs,
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

    async def get_video_info(self, url: str, **kwargs) -> dict:
        """
        Quick method to get video information.

        Args:
            url: TikTok video URL
            **kwargs: Additional arguments

        Returns:
            dict: Video information
        """
        await self.ensure_session()
        video = self.video(url=url)
        return await video.info(**kwargs)

    async def get_user_info(self, username: str, **kwargs) -> dict:
        """
        Quick method to get user information.

        Args:
            username: TikTok username (without @)
            **kwargs: Additional arguments

        Returns:
            dict: User information
        """
        await self.ensure_session()
        user = self.user(username=username)
        return await user.info(**kwargs)

    async def download_video(
        self, url: str, filename: Optional[str] = None, **kwargs
    ) -> Union[bytes, str]:
        """
        Quick method to download a video.

        Args:
            url: TikTok video URL
            filename: Output filename (optional)
            **kwargs: Additional arguments

        Returns:
            bytes if no filename, filename if saved to file
        """
        await self.ensure_session()
        video = self.video(url=url)
        await video.info(**kwargs)

        # Use the bytes method from Video class
        video_bytes = video.bytes(**kwargs)

        if filename:
            with open(filename, "wb") as f:
                if hasattr(video_bytes, "__iter__") and not isinstance(video_bytes, bytes):
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
                collected_bytes = b""
                for chunk in video_bytes:
                    if isinstance(chunk, bytes):
                        collected_bytes += chunk
                return collected_bytes

    # Session management methods

    def set_proxy(self, proxy: str) -> None:
        """
        Set proxy for the session.
        Note: This requires restarting the session.

        Args:
            proxy: Proxy string (e.g., "http://proxy:port")
        """
        self.scraper_kwargs["proxy"] = proxy
        if self.tab:
            self.logger.info("Proxy set. Session must be restarted.")

    def set_headless(self, headless: bool) -> None:
        """
        Set headless mode for the session.
        Note: This requires restarting the session.

        Args:
            headless: Whether to run in headless mode
        """
        self.scraper_kwargs["headless"] = headless
        if self.tab:
            self.logger.info("Headless mode changed. Session must be restarted.")

    async def add_session_cookies(self, cookies: list) -> None:
        """Add cookies to the current session via CDP."""
        if self.tab:
            import nodriver.cdp.network as net

            for cookie in cookies:
                try:
                    await self.tab.send(
                        net.set_cookie(
                            name=cookie.get("name", ""),
                            value=cookie.get("value", ""),
                            domain=cookie.get("domain", ".tiktok.com"),
                            path=cookie.get("path", "/"),
                            secure=cookie.get("secure", False),
                            http_only=cookie.get("httpOnly", False),
                        )
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to add cookie: {e}")

            # Update the requests session as well
            await self._update_session_from_tab()

    async def navigate_to(self, url: str) -> None:
        """Navigate to a specific URL."""
        await self.ensure_session()
        if self.tab:
            await self.tab.get(url)

    def wait(self, seconds: float) -> None:
        """Wait for a specified number of seconds (sync)."""
        time.sleep(seconds)

    async def _update_session_from_tab(self) -> None:
        """Update the requests session with cookies and headers from the browser tab."""
        if not self.tab:
            return

        # Get cookies via CDP
        try:
            import nodriver.cdp.network as net

            all_cookies = await self.tab.send(net.get_all_cookies())

            # Clear existing cookies and add new ones
            self.session.cookies.clear()
            for cookie in all_cookies:
                self.session.cookies.set(
                    name=cookie.name,
                    value=cookie.value,
                    domain=cookie.domain or ".tiktok.com",
                    path=cookie.path or "/",
                    secure=cookie.secure or False,
                )
        except Exception as e:
            self.logger.warning(f"Could not get cookies via CDP: {e}")

        # Set common headers that mimic browser requests
        try:
            user_agent = await self.tab.evaluate("navigator.userAgent")
        except Exception:
            user_agent = "Mozilla/5.0"

        self._session_headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.tiktok.com/",
            "Origin": "https://www.tiktok.com",
        }

        self.session.headers.update(self._session_headers)

    def _get_session(self, session_index: Optional[int] = None, **kwargs):
        """
        Get session information for compatibility with original TikTokAPI.
        """
        session_obj = type(
            "Session",
            (),
            {
                "headers": self._session_headers,
                "cookies": dict(self.session.cookies),
                "proxy": kwargs.get("proxy"),
            },
        )()

        return 0, session_obj

    def make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        session_index: Optional[int] = None,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Make an HTTP request using the current session cookies and headers.

        Args:
            url: The URL to make the request to
            params: Query parameters
            headers: Additional headers
            session_index: Session index (unused)
            method: HTTP method
            data: Data for POST requests
            timeout: Request timeout in seconds
            **kwargs: Additional arguments

        Returns:
            dict: JSON response data, or None if request failed
        """
        # Merge headers
        request_headers = self._session_headers.copy()
        if headers:
            request_headers.update(headers)

        if "Referer" not in request_headers:
            request_headers["Referer"] = "https://www.tiktok.com/"
        if "Origin" not in request_headers:
            request_headers["Origin"] = "https://www.tiktok.com"

        proxy = kwargs.get("proxy")
        proxies = None
        if proxy:
            proxies = {"http": proxy, "https": proxy}

        try:
            self.logger.debug(f"Making {method} request to: {url}")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=request_headers,
                json=data if method.upper() == "POST" and data else None,
                data=data
                if method.upper() == "POST" and not isinstance(data, dict)
                else None,
                timeout=timeout,
                proxies=proxies,
                allow_redirects=True,
            )

            self.logger.debug(f"Response status: {response.status_code}")

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
                return None

        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in make_request: {e}")
            return None

    async def set_session_cookies(self, session, cookies: list) -> None:
        """
        Set cookies for a session (compatibility with original API).
        """
        if self.tab:
            import nodriver.cdp.network as net

            for cookie in cookies:
                try:
                    await self.tab.send(
                        net.set_cookie(
                            name=cookie.get("name", ""),
                            value=cookie.get("value", ""),
                            domain=cookie.get("domain", ".tiktok.com"),
                            path=cookie.get("path", "/"),
                            secure=cookie.get("secure", False),
                            http_only=cookie.get("httpOnly", False),
                        )
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}"
                    )

            await self._update_session_from_tab()

    async def get_session_cookies(self, session=None) -> Dict[str, str]:
        """
        Get session cookies via CDP.

        Returns:
            dict: Dictionary of cookie name-value pairs
        """
        if self.tab:
            try:
                import nodriver.cdp.network as net

                all_cookies = await self.tab.send(net.get_all_cookies())
                return {c.name: c.value for c in all_cookies}
            except Exception:
                return {}
        return {}

    async def refresh_session(self) -> None:
        """Refresh the session by updating cookies and headers from the browser."""
        if self.tab:
            await self._update_session_from_tab()
            self.logger.info("Session refreshed with latest cookies and headers")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close_session()

    def __del__(self):
        """Destructor to ensure session is closed."""
        if hasattr(self, "tab") and self.tab:
            try:
                self.close_session()
            except Exception:
                pass
