from __future__ import annotations
from helpers import extract_video_id_from_url, requests_cookie_to_selenium_cookie
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional, Union
from datetime import datetime
import requests
import json
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.webdriver import WebDriver as Webdriver
import pprint

if TYPE_CHECKING:
    from .tiktok import TikTokApi
    from .video import Video


class InvalidResponseException(Exception):
    """Exception raised when TikTok returns an invalid response."""
    def __init__(self, response_text, message, error_code=None):
        self.response_text = response_text
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class User:
    """
    A TikTok User class using Selenium

    Example Usage
    ```py
    user = api.user(username='therock')
    ```
    """

    parent: ClassVar[TikTokApi]

    id: Optional[str]
    """TikTok's ID of the User"""
    username: Optional[str]
    """The username of the User"""
    nickname: Optional[str]
    """The display name of the User"""
    sec_uid: Optional[str]
    """The sec_uid of the User"""
    avatar_url: Optional[str]
    """The avatar URL of the User"""
    verified: Optional[bool]
    """Whether the User is verified"""
    follower_count: Optional[str]
    """The follower count of the User"""
    following_count: Optional[str]
    """The following count of the User"""
    video_count: Optional[str]
    """The video count of the User"""
    heart_count: Optional[str]
    """The heart count of the User"""
    signature: Optional[str]
    """The signature/bio of the User"""
    as_dict: dict
    """The raw data associated with this User."""
    appProps: Optional[str]
    """The region of published video, if available"""
    def __init__(
        self,
        username: Optional[str] = None,
        sec_uid: Optional[str] = None,
        user_id: Optional[str] = None,
        data: Optional[dict] = None,
        driver = None,
        **kwargs,
    ):
        """
        You must provide the username, sec_uid, or user_id, else this will fail.
        """
        self.username = username
        self.sec_uid = sec_uid
        self.id = user_id
        self.driver = driver
        self.logger = logging.getLogger(f"TTScraper.{self.__class__.__name__}")
        
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        
        if not any([self.username, self.sec_uid, self.id]):
            raise TypeError("You must provide username, sec_uid, or user_id parameter.")

    def info(self, **kwargs) -> dict:
        """
        Returns a dictionary of all data associated with a TikTok User using Selenium.

        Returns:
            dict: A dictionary of all data associated with a TikTok User.

        Raises:
            InvalidResponseException: If TikTok returns an invalid response.

        Example Usage:
            .. code-block:: python

                user_info = await api.user(username='therock').info()
        """
        # Use provided driver or the instance driver
        driver = kwargs.get('driver', self.driver)
        if driver is None:
            raise TypeError("A Selenium WebDriver instance is required.")

        # Construct URL based on available identifier
        if self.username:
            url = f"https://www.tiktok.com/@{self.username}"
        elif self.sec_uid:
            url = f"https://www.tiktok.com/@{self.sec_uid}"
        elif self.id:
            url = f"https://www.tiktok.com/@{self.id}"
        else:
            raise TypeError("No valid identifier found for user.")

        # Navigate to the user URL
        driver.get(url)
        
        # Wait for page to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "script"))
            )
            time.sleep(3)  # Additional wait for dynamic content
        except Exception:
            pass

        # Get page source
        page_source = driver.page_source

        # Try __UNIVERSAL_DATA_FOR_REHYDRATION__ first
        user_info = self._extract_universal_data(page_source)
        #self.logger.debug(f"Extracted user info: {pprint.pformat(user_info)}")
        if user_info is None:
            # Try SIGI_STATE as fallback
            user_info = self._extract_sigi_state(page_source)
            # Download the JSON part of the SIGI_STATE script tag for debugging
            try:
                start = page_source.find('<script id="SIGI_STATE" type="application/json">')
                end = -1
                if start != -1:
                    start += len('<script id="SIGI_STATE" type="application/json">')
                    end = page_source.find("</script>", start)
                    if end != -1:
                        sigi_json = page_source[start:end]
                    with open("sigi_state.json", "w", encoding="utf-8") as f:
                        f.write(sigi_json)
            except Exception as e:
                self.logger.error(f"Failed to save SIGI_STATE JSON: {e}")
            #self.logger.debug(f"Page source length: {len(page_source)}")

        if user_info is None:
            raise InvalidResponseException(
            page_source, "Could not extract user data from page"
            )

        self.as_dict = user_info
        self.__extract_from_data()

        return user_info

    def _extract_sigi_state(self, page_source: str) -> Optional[dict]:
        """Extract user data from SIGI_STATE script tag."""
        try:
            start = page_source.find('<script id="SIGI_STATE" type="application/json">')
            if start == -1:
                return None
                
            start += len('<script id="SIGI_STATE" type="application/json">')
            end = page_source.find("</script>", start)

            if end == -1:
                return None

            data = json.loads(page_source[start:end])
            
            # Try to find user in UserModule
            user_module = data.get("UserModule", {})
            if user_module.get("users"):
                # Get the first user (should be the profile owner)
                user_data = list(user_module["users"].values())[0]
                return user_data
            
            # Try UserPage
            user_page = data.get("UserPage", {})
            if user_page.get("user"):
                return user_page["user"]
                
            return None
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse SIGI_STATE: {e}")
            return None

    def _extract_universal_data(self, page_source: str) -> Optional[dict]:
        """Extract user data from __UNIVERSAL_DATA_FOR_REHYDRATION__ script tag, including __DEFAULT_SCOPE__."""
        try:
            start = page_source.find('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">')
            if start == -1:
                return None

            start += len('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">')
            end = page_source.find("</script>", start)

            if end == -1:
                return None

            json_str = page_source[start:end]
            data = json.loads(json_str)
            # Save the JSON to a file for debugging
            try:
                with open("universal_data.json", "w", encoding="utf-8") as f:
                    f.write(json_str)
            except Exception as e:
                self.logger.error(f"Failed to save UNIVERSAL_DATA JSON: {e}")

            default_scope = data.get("__DEFAULT_SCOPE__", {})
            app_context = default_scope.get("webapp.app-context", {})
            user_detail = default_scope.get("webapp.user-detail", {})

            # Extract userInfo and stats
            user_info = user_detail.get("userInfo", {}).get("user", {})
            stats = user_detail.get("userInfo", {}).get("stats", {})

            # Merge app_context, user_info, and stats into one dict
            merged = {}
            merged.update(app_context)
            merged.update(user_info)
            merged["stats"] = stats  # keep stats as a sub-dict for clarity

            # Optionally, keep the whole __DEFAULT_SCOPE__ for reference
            merged["__DEFAULT_SCOPE__"] = default_scope

            return merged

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse UNIVERSAL_DATA: {e}")
            return None

    def __extract_from_data(self) -> None:
        """Extract user information from raw data."""
        if not self.as_dict:
            return

        data = self.as_dict
        #self.logger.debug(f"Raw user data: {pprint.pformat(data)}")
        # Extract basic info
        self.id = data.get("id") or self.id
        self.username = data.get("uniqueId") or self.username
        self.nickname = data.get("nickname") or self.nickname
        self.sec_uid = data.get("secUid") or self.sec_uid
        self.verified = data.get("verified", False)
        self.signature = data.get("signature")
        self.region = data.get("region") or data.get('webapp.app-context', {}).get('region')
        self.language = data.get("language") or data.get('webapp.app-context', {}).get('language')
        self.follower_count = data.get("followerCount") or data.get("stats", {}).get("followerCount", 0)
        self.following_count = data.get("followingCount") or data.get("stats", {}).get("followingCount", 0)
        self.heart_count = data.get("heartCount") or data.get("stats", {}).get("heartCount", 0)
        self.video_count = data.get("videoCount") or data.get("stats", {}).get("videoCount", 0)
        self.friends_count = data.get("friendCount") or data.get("stats", {}).get("friendCount", 0)
        self.digg_count = data.get("diggCount") or data.get("stats", {}).get("diggCount", 0)
        self.botType = data.get("botType") or data.get('webapp.app-context', {}).get('botType', "unknown")
        # Extract avatar URL
        avatar_data = data.get("avatarLarger") or data.get("avatarMedium") or data.get("avatarThumb")
        if isinstance(avatar_data, str):
            self.avatar_url = avatar_data
        elif isinstance(avatar_data, list) and avatar_data:
            self.avatar_url = avatar_data[0]
        else:
            self.avatar_url = None

        # Extract stats
        stats = data.get("stats", {})
        self.follower_count = stats.get("followerCount", 0)
        self.following_count = stats.get("followingCount", 0)
        self.video_count = stats.get("videoCount", 0)
        self.heart_count = stats.get("heartCount", 0)

        # If _default_scope is present, store it as an attribute for access
        if "__DEFAULT_SCOPE__" in data:
            self.default_scope = data["__DEFAULT_SCOPE__"]

    def videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator[Video]:
        """
        Returns the videos of a TikTok User.

        Parameters:
            count (int): The amount of videos you want returned.
            cursor (int): The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.

        Example Usage
        .. code-block:: python

            for video in user.videos():
                # do something
        """
        found = 0
        while found < count:
            params = {
                "secUid": self.sec_uid,
                "count": min(35, count - found),
                "cursor": cursor,
            }

            # Use make_request from parent API
            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/post/item_list/",
                        params=params,
                        headers=kwargs.get("headers"),
                        **kwargs
                    )

                    if resp is None:
                        break

                    for video_data in resp.get("itemList", []):
                        if found >= count:
                            return
                        yield self.parent.video(data=video_data)
                        found += 1

                    if not resp.get("hasMore", False):
                        break

                    cursor = resp.get("cursor", cursor + len(resp.get("itemList", [])))
                    
                except Exception as e:
                    self.logger.error(f"Error fetching user videos: {e}")
                    break
            else:
                # Fallback: scrape user page for video links
                break

    def liked_videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator[Video]:
        """
        Returns the liked videos of a TikTok User.

        Note: This only works if the user has their liked videos public.

        Parameters:
            count (int): The amount of videos you want returned.
            cursor (int): The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.
        """
        found = 0
        while found < count:
            params = {
                "secUid": self.sec_uid,
                "count": 30,
                "cursor": cursor,
            }

            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/favorite/item_list/",
                        params=params,
                        headers=kwargs.get("headers"),
                        **kwargs
                    )

                    if resp is None:
                        break

                    for video_data in resp.get("itemList", []):
                        if found >= count:
                            return
                        yield self.parent.video(data=video_data)
                        found += 1

                    if not resp.get("hasMore", False):
                        break

                    cursor = resp.get("cursor", cursor + len(resp.get("itemList", [])))
                    
                except Exception as e:
                    self.logger.error(f"Error fetching liked videos: {e}")
                    break
            else:
                break

    def get_summary(self) -> dict:
        """Get a summary of the user information."""
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'verified': self.verified,
            'follower_count': self.follower_count,
            'following_count': self.following_count,
            'video_count': self.video_count,
            'heart_count': self.heart_count,
            'signature': self.signature,
            'avatar_url': self.avatar_url,
            'has_data': bool(self.as_dict)
        }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"User(username='{getattr(self, 'username', None)}')"


# Helper functions
def get_user_info(username: str, driver, wait_time: int = 10) -> User:
    """
    Quick function to get user information from a username.
    
    Args:
        username: TikTok username (without @)
        driver: Selenium WebDriver instance
        wait_time: How long to wait for page load
        
    Returns:
        User instance with loaded data
    """
    user = User(username=username, driver=driver)
    user.info(driver=driver)
    return user


