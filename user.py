from __future__ import annotations
from helpers import extract_video_id_from_url
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional, Union
from datetime import datetime
import asyncio
import requests
import json
import time
import logging

import nodriver as uc
import nodriver.cdp.network as cdp_network
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
    A TikTok User class using nodriver (async CDP).

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
        tab=None,
        # Accept 'driver' kwarg for backward compat, treat as tab
        driver=None,
        **kwargs,
    ):
        """
        You must provide the username, sec_uid, or user_id, else this will fail.
        """
        self.username = username
        self.sec_uid = sec_uid
        self.id = user_id
        self.tab = tab or driver  # backward compat
        self.logger = logging.getLogger(f"TTScraper.{self.__class__.__name__}")

        if data is not None:
            self.as_dict = data
            self.__extract_from_data()

        if not any([self.username, self.sec_uid, self.id]):
            raise TypeError("You must provide username, sec_uid, or user_id parameter.")

    async def info(self, **kwargs) -> dict:
        """
        Returns a dictionary of all data associated with a TikTok User.

        Returns:
            dict: A dictionary of all data associated with a TikTok User.

        Raises:
            InvalidResponseException: If TikTok returns an invalid response.

        Example Usage:
            .. code-block:: python

                user_info = await api.user(username='therock').info()
        """
        # Use provided tab or the instance tab
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

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
        await tab.get(url)

        # Wait for page to load
        await asyncio.sleep(3)

        # Get page source
        page_source = await tab.get_content()

        # Try __UNIVERSAL_DATA_FOR_REHYDRATION__ first
        user_info = self._extract_universal_data(page_source)
        if user_info is None:
            # Try SIGI_STATE as fallback
            user_info = self._extract_sigi_state(page_source)
            # Save debug JSON if available
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
        """Extract user data from __UNIVERSAL_DATA_FOR_REHYDRATION__ script tag."""
        try:
            start = page_source.find(
                '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            )
            if start == -1:
                return None

            start += len(
                '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            )
            end = page_source.find("</script>", start)

            if end == -1:
                return None

            json_str = page_source[start:end]
            data = json.loads(json_str)
            try:
                with open("universal_data.json", "w", encoding="utf-8") as f:
                    f.write(json_str)
            except Exception as e:
                self.logger.error(f"Failed to save UNIVERSAL_DATA JSON: {e}")

            default_scope = data.get("__DEFAULT_SCOPE__", {})
            app_context = default_scope.get("webapp.app-context", {})
            user_detail = default_scope.get("webapp.user-detail", {})

            user_info = user_detail.get("userInfo", {}).get("user", {})
            stats = user_detail.get("userInfo", {}).get("stats", {})

            merged = {}
            merged.update(app_context)
            merged.update(user_info)
            merged["stats"] = stats

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
        self.id = data.get("id") or self.id
        self.username = data.get("uniqueId") or self.username
        self.nickname = data.get("nickname") or self.nickname
        self.sec_uid = data.get("secUid") or self.sec_uid
        self.verified = data.get("verified", False)
        self.signature = data.get("signature")
        self.region = data.get("region") or data.get("webapp.app-context", {}).get("region")
        self.language = data.get("language") or data.get("webapp.app-context", {}).get("language")
        self.follower_count = (
            data.get("followerCount") or data.get("stats", {}).get("followerCount", 0)
        )
        self.following_count = (
            data.get("followingCount") or data.get("stats", {}).get("followingCount", 0)
        )
        self.heart_count = (
            data.get("heartCount") or data.get("stats", {}).get("heartCount", 0)
        )
        self.video_count = (
            data.get("videoCount") or data.get("stats", {}).get("videoCount", 0)
        )
        self.friends_count = (
            data.get("friendCount") or data.get("stats", {}).get("friendCount", 0)
        )
        self.digg_count = (
            data.get("diggCount") or data.get("stats", {}).get("diggCount", 0)
        )
        self.botType = data.get("botType") or data.get("webapp.app-context", {}).get(
            "botType", "unknown"
        )

        avatar_data = (
            data.get("avatarLarger") or data.get("avatarMedium") or data.get("avatarThumb")
        )
        if isinstance(avatar_data, str):
            self.avatar_url = avatar_data
        elif isinstance(avatar_data, list) and avatar_data:
            self.avatar_url = avatar_data[0]
        else:
            self.avatar_url = None

        stats = data.get("stats", {})
        self.follower_count = stats.get("followerCount", 0)
        self.following_count = stats.get("followingCount", 0)
        self.video_count = stats.get("videoCount", 0)
        self.heart_count = stats.get("heartCount", 0)

        if "__DEFAULT_SCOPE__" in data:
            self.default_scope = data["__DEFAULT_SCOPE__"]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CDP Network-Capture Methods
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _ensure_on_profile(self, tab) -> None:
        """Navigate to the user profile page if not already there."""
        profile_url = f"https://www.tiktok.com/@{self.username}"
        try:
            current_url = await tab.evaluate("window.location.href")
            if f"/@{self.username}" not in current_url:
                self.logger.info(f"Navigating to profile: {profile_url}")
                await tab.get(profile_url)
                await asyncio.sleep(4)
            else:
                self.logger.info(f"Already on profile page for @{self.username}")
        except Exception:
            self.logger.info(f"Navigating to profile: {profile_url}")
            await tab.get(profile_url)
            await asyncio.sleep(4)

    async def fetch_videos(self, **kwargs) -> list[dict]:
        """
        Fetch all videos for this user using CDP network capture.

        Navigates to the user profile and scrolls the video grid to trigger
        ``/api/post/item_list/`` pagination via CDP interception.

        Args:
            tab: nodriver Tab instance.
            max_pages: Stop after this many API pages (default 50).
            scroll_pause: Seconds to wait between scrolls (default 2.0).

        Returns:
            list[dict]: Every video dict as returned by TikTok's API.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        max_pages = kwargs.get("max_pages", 50)
        scroll_pause = kwargs.get("scroll_pause", 2.0)

        captured_pages: list[dict] = []

        async def _on_response(event: cdp_network.ResponseReceived):
            url = event.response.url
            if "/api/post/item_list/" not in url:
                return

            self.logger.info(f"CDP captured video list API: status={event.response.status}")
            try:
                body_str, is_base64 = await tab.send(
                    cdp_network.get_response_body(event.request_id)
                )
                if is_base64:
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8", errors="replace")
                data = json.loads(body_str)
            except Exception as e:
                self.logger.warning(f"Could not read video list body: {e}")
                return

            if data.get("status_code", -1) != 0 and data.get("statusCode", -1) != 0:
                self.logger.warning(f"Video list API status: {data.get('status_code', data.get('statusCode'))}")
                return

            items = data.get("itemList", [])
            captured_pages.append({
                "items": items,
                "has_more": data.get("hasMore", False),
                "cursor": data.get("cursor", 0),
            })
            self.logger.info(
                f"Video page {len(captured_pages)}: {len(items)} videos "
                f"(total: {sum(len(p['items']) for p in captured_pages)}, "
                f"hasMore={data.get('hasMore')})"
            )

        tab.add_handler(cdp_network.ResponseReceived, _on_response)
        self.logger.info("CDP handler registered for /api/post/item_list/")

        try:
            await self._ensure_on_profile(tab)

            # Wait for initial video list API call (usually fires on page load)
            for _ in range(10):
                if captured_pages:
                    break
                await asyncio.sleep(1)

            if not captured_pages:
                self.logger.info("No video API call on load, scrolling to trigger...")
                for _ in range(3):
                    await tab.evaluate("window.scrollBy(0, 600)")
                    await asyncio.sleep(2)
                    if captured_pages:
                        break

            # Scroll to load more pages
            same_count = 0
            max_stale = 6

            for scroll_num in range(max_pages * 3):
                prev_total = len(captured_pages)
                await tab.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(scroll_pause)

                if len(captured_pages) > prev_total:
                    same_count = 0
                else:
                    same_count += 1

                if len(captured_pages) >= max_pages:
                    self.logger.info(f"Reached max_pages={max_pages}")
                    break

                if captured_pages and not captured_pages[-1].get("has_more"):
                    self.logger.info("Last page hasMore=false — all videos captured")
                    break

                if same_count >= max_stale:
                    self.logger.info(f"No new data after {max_stale} scrolls — stopping")
                    break

            all_videos = []
            for page in captured_pages:
                all_videos.extend(page.get("items", []))

            self.logger.info(f"Fetched {len(all_videos)} videos total")
            return all_videos

        finally:
            tab.remove_handler(cdp_network.ResponseReceived, _on_response)

    async def fetch_reposts(self, **kwargs) -> list[dict]:
        """
        Fetch reposts for this user using CDP network capture.

        Navigates to the user's reposts tab and scrolls to trigger
        ``/api/repost/item_list/`` pagination.

        Args:
            tab: nodriver Tab instance.
            max_pages: Stop after this many API pages (default 50).
            scroll_pause: Seconds to wait between scrolls (default 2.0).

        Returns:
            list[dict]: Every repost dict as returned by TikTok's API.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        max_pages = kwargs.get("max_pages", 50)
        scroll_pause = kwargs.get("scroll_pause", 2.0)

        captured_pages: list[dict] = []

        async def _on_response(event: cdp_network.ResponseReceived):
            url = event.response.url
            if "/api/repost/item_list/" not in url:
                return

            self.logger.info(f"CDP captured repost list API: status={event.response.status}")
            try:
                body_str, is_base64 = await tab.send(
                    cdp_network.get_response_body(event.request_id)
                )
                if is_base64:
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8", errors="replace")
                data = json.loads(body_str)
            except Exception as e:
                self.logger.warning(f"Could not read repost list body: {e}")
                return

            if data.get("status_code", -1) != 0 and data.get("statusCode", -1) != 0:
                self.logger.warning(f"Repost list API status: {data.get('status_code', data.get('statusCode'))}")
                return

            items = data.get("itemList", data.get("item_list", []))
            captured_pages.append({
                "items": items,
                "has_more": data.get("hasMore", data.get("has_more", False)),
                "cursor": data.get("cursor", 0),
            })
            self.logger.info(
                f"Repost page {len(captured_pages)}: {len(items)} reposts "
                f"(total: {sum(len(p['items']) for p in captured_pages)}, "
                f"hasMore={data.get('hasMore', data.get('has_more'))})"
            )

        tab.add_handler(cdp_network.ResponseReceived, _on_response)
        self.logger.info("CDP handler registered for /api/repost/item_list/")

        try:
            await self._ensure_on_profile(tab)

            # Click the "Reposts" tab on the profile page
            # All strategies use HTML structure / attributes, not text.
            click_js = """
            (function() {
                // Strategy 1: data-e2e attribute
                var repostTab = document.querySelector('[data-e2e="repost-tab"]');
                if (repostTab) { repostTab.click(); return 'clicked data-e2e repost-tab'; }

                // Strategy 2: data-e2e containing "repost"
                var byAttr = document.querySelector('[data-e2e*="repost"]');
                if (byAttr) {
                    var clickable = byAttr.closest('[role="tab"]') || byAttr;
                    clickable.click();
                    return 'clicked data-e2e*=repost';
                }

                // Strategy 3: DivTabItem by position — Reposts is typically
                // the last tab (after Videos and possibly Liked / Favorites)
                var tabItems = document.querySelectorAll('[class*="DivTabItem"]');
                if (tabItems.length > 0) {
                    var last = tabItems[tabItems.length - 1];
                    last.click();
                    return 'clicked last DivTabItem (index ' + (tabItems.length - 1) + ')';
                }

                // Strategy 4: role="tab" containers — pick the last one
                var roleTabs = document.querySelectorAll('[role="tab"]');
                if (roleTabs.length > 0) {
                    var last = roleTabs[roleTabs.length - 1];
                    last.click();
                    return 'clicked last role=tab (index ' + (roleTabs.length - 1) + ')';
                }

                return 'repost tab not found';
            })()
            """

            click_result = await tab.evaluate(click_js)
            self.logger.info(f"Repost tab click: {click_result}")
            await asyncio.sleep(3)

            # Wait for initial repost API call
            for _ in range(10):
                if captured_pages:
                    break
                await asyncio.sleep(1)

            if not captured_pages:
                self.logger.info("No repost API call detected, scrolling...")
                for _ in range(3):
                    await tab.evaluate("window.scrollBy(0, 600)")
                    await asyncio.sleep(2)
                    if captured_pages:
                        break

            # Retry with page refresh if still no repost API calls captured
            retry_count = 0
            max_retries = 3
            while not captured_pages and retry_count < max_retries:
                retry_count += 1
                self.logger.info(
                    f"No repost API captured, refreshing page "
                    f"(attempt {retry_count}/{max_retries})..."
                )
                await asyncio.sleep(5)
                await tab.reload()
                await asyncio.sleep(3)

                # Re-click repost tab after refresh
                click_result = await tab.evaluate(click_js)
                self.logger.info(f"Repost tab click after refresh: {click_result}")
                await asyncio.sleep(3)

                # Wait for API call
                for _ in range(10):
                    if captured_pages:
                        break
                    await asyncio.sleep(1)

                if captured_pages:
                    self.logger.info(f"Repost API captured after retry {retry_count}")
                    break

            # Scroll to load more pages
            same_count = 0
            max_stale = 6

            for scroll_num in range(max_pages * 3):
                prev_total = len(captured_pages)
                await tab.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(scroll_pause)

                if len(captured_pages) > prev_total:
                    same_count = 0
                else:
                    same_count += 1

                if len(captured_pages) >= max_pages:
                    break

                if captured_pages and not captured_pages[-1].get("has_more"):
                    self.logger.info("All reposts captured")
                    break

                if same_count >= max_stale:
                    self.logger.info(f"No new repost data after {max_stale} scrolls")
                    break

            all_reposts = []
            for page in captured_pages:
                all_reposts.extend(page.get("items", []))

            self.logger.info(f"Fetched {len(all_reposts)} reposts total")
            return all_reposts

        finally:
            tab.remove_handler(cdp_network.ResponseReceived, _on_response)

    async def fetch_user_list(self, list_type: str = "following", **kwargs) -> list[dict]:
        """
        Fetch following or followers list using CDP network capture.

        Navigates to the profile, clicks the Following/Followers count to
        open the modal, then scrolls the list container to trigger
        ``/api/user/list/`` pagination.

        The API uses ``scene=21`` for following and ``scene=67`` for followers.

        Args:
            list_type: "following" or "followers".
            tab: nodriver Tab instance.
            max_pages: Stop after this many API pages (default 50).
            scroll_pause: Seconds to wait between scrolls (default 2.0).

        Returns:
            list[dict]: Every user dict from the API ``userList`` array.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        if list_type not in ("following", "followers"):
            raise ValueError("list_type must be 'following' or 'followers'")

        max_pages = kwargs.get("max_pages", 50)
        scroll_pause = kwargs.get("scroll_pause", 2.0)
        # scene=21 → following, scene=67 → followers
        expected_scene = "21" if list_type == "following" else "67"

        captured_pages: list[dict] = []

        async def _on_response(event: cdp_network.ResponseReceived):
            url = event.response.url
            if "/api/user/list/" not in url:
                return
            # Verify the scene parameter matches what we want
            if f"scene={expected_scene}" not in url:
                return

            self.logger.info(
                f"CDP captured {list_type} list API: status={event.response.status}"
            )
            try:
                body_str, is_base64 = await tab.send(
                    cdp_network.get_response_body(event.request_id)
                )
                if is_base64:
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8", errors="replace")
                data = json.loads(body_str)
            except Exception as e:
                self.logger.warning(f"Could not read {list_type} list body: {e}")
                return

            if data.get("status_code", -1) != 0 and data.get("statusCode", -1) != 0:
                self.logger.warning(
                    f"{list_type} list API status: "
                    f"{data.get('status_code', data.get('statusCode'))}"
                )
                return

            users = data.get("userList", [])
            captured_pages.append({
                "users": users,
                "has_more": data.get("hasMore", False),
                "minCursor": data.get("minCursor", 0),
                "maxCursor": data.get("maxCursor", 0),
                "total": data.get("total", 0),
            })
            self.logger.info(
                f"{list_type.capitalize()} page {len(captured_pages)}: "
                f"{len(users)} users "
                f"(total: {sum(len(p['users']) for p in captured_pages)}, "
                f"hasMore={data.get('hasMore')})"
            )

        tab.add_handler(cdp_network.ResponseReceived, _on_response)
        self.logger.info(f"CDP handler registered for /api/user/list/ (scene={expected_scene})")

        try:
            await self._ensure_on_profile(tab)

            # Close any open modal first (e.g. a previous following/followers popup)
            close_modal_js = """
            (function() {
                // data-e2e close button used on follow popups
                var btn = document.querySelector('[data-e2e="follow-popup-close"]');
                if (btn) { btn.click(); return 'closed follow-popup'; }

                // Fallback: DivCloseContainer inside a dialog/modal
                btn = document.querySelector(
                    '[class*="DivCloseContainer"], [aria-label="Close_button"]'
                );
                if (btn) { btn.click(); return 'closed DivCloseContainer'; }

                return 'no modal open';
            })()
            """
            close_result = await tab.evaluate(close_modal_js)
            self.logger.info(f"Pre-open modal close: {close_result}")
            if close_result != 'no modal open':
                await asyncio.sleep(1)

            # Click the Following or Followers count to open the modal.
            # All strategies use HTML structure / attributes, not text.
            # On TikTok profile pages the count links appear in order:
            #   index 0 → Following,  index 1 → Followers
            # We also match by data-e2e, href pattern, and DivTabItem position.
            click_js = f"""
            (function() {{
                var listType = '{list_type}';
                var isFollowing = (listType === 'following');

                // Strategy 1: data-e2e attributes (most reliable)
                var de = isFollowing
                    ? document.querySelector('[data-e2e="following-count"]')
                    : document.querySelector('[data-e2e="followers-count"]');
                if (de) {{
                    var link = de.closest('a') || de.closest('[role="link"]') || de;
                    link.click();
                    return 'clicked data-e2e ' + listType + '-count';
                }}

                // Strategy 2: anchor href containing the list type keyword
                var links = document.querySelectorAll(
                    'a[href*="/' + listType + '"], a[href*="/' + listType.replace('s','') + '"]'
                );
                for (var i = 0; i < links.length; i++) {{
                    var strong = links[i].querySelector('strong');
                    if (strong) {{
                        links[i].click();
                        return 'clicked a[href*=' + listType + ']';
                    }}
                }}

                // Strategy 3: DivTabItem by position
                // Profile stats bar: DivTabItem[0]=Following, DivTabItem[1]=Followers
                var tabItems = document.querySelectorAll('[class*="DivTabItem"]');
                var idx = isFollowing ? 0 : 1;
                if (tabItems.length > idx) {{
                    tabItems[idx].click();
                    return 'clicked DivTabItem[' + idx + ']';
                }}

                // Strategy 4: count links in the stats/header area by position
                // Look for <strong> inside <a> or clickable parent — these
                // appear in the same order: following(0), followers(1)
                var countEls = document.querySelectorAll(
                    '[class*="CountInfo"] strong, '
                    + '[class*="count-info"] strong, '
                    + 'h2 a strong, '
                    + '[class*="DivNumber"] strong'
                );
                if (countEls.length === 0) {{
                    // Broader: any <strong> inside an <a> on the profile header
                    var header = document.querySelector(
                        '[class*="ShareHeader"], [class*="shareHeader"], '
                        + '[class*="UserInfo"], [class*="userInfo"]'
                    );
                    if (header) {{
                        countEls = header.querySelectorAll('a strong, a [class*="Count"]');
                    }}
                }}
                if (countEls.length > idx) {{
                    var target = countEls[idx].closest('a')
                              || countEls[idx].parentElement;
                    if (target) {{ target.click(); }}
                    else {{ countEls[idx].click(); }}
                    return 'clicked count element[' + idx + ']';
                }}

                return listType + ' count link not found';
            }})()
            """

            click_result = await tab.evaluate(click_js)
            self.logger.info(f"{list_type.capitalize()} modal click: {click_result}")
            await asyncio.sleep(3)

            # Wait for initial API call
            for _ in range(10):
                if captured_pages:
                    break
                await asyncio.sleep(1)

            if not captured_pages:
                self.logger.info(f"No {list_type} API call detected, scrolling modal...")

            # Scroll inside the user list modal container
            # The container is DivUserListContainer (css-1sko41r... es9zqxz0)
            scroll_modal_js = """
            (function() {
                // Find the scrollable user list container
                var container = document.querySelector(
                    '[class*="DivUserListContainer"]'
                );
                if (container) {
                    container.scrollTop += 1500;
                    return 'scrolled DivUserListContainer';
                }

                // Fallback: any scrollable modal/dialog
                var modal = document.querySelector(
                    '[role="dialog"], [class*="modal"], [class*="Modal"]'
                );
                if (modal) {
                    var scrollable = modal.querySelector(
                        '[style*="overflow"], [class*="scroll"]'
                    );
                    if (scrollable) {
                        scrollable.scrollTop += 1500;
                        return 'scrolled modal child';
                    }
                    modal.scrollTop += 1500;
                    return 'scrolled modal';
                }

                // Last resort: scroll the main window
                window.scrollBy(0, 1500);
                return 'scrolled window';
            })()
            """

            same_count = 0
            max_stale = 6

            for scroll_num in range(max_pages * 5):
                prev_total = len(captured_pages)

                scroll_result = await tab.evaluate(scroll_modal_js)
                await asyncio.sleep(scroll_pause)

                if len(captured_pages) > prev_total:
                    same_count = 0
                    self.logger.debug(
                        f"Scroll {scroll_num+1}: new {list_type} page captured "
                        f"({scroll_result})"
                    )
                else:
                    same_count += 1

                if len(captured_pages) >= max_pages:
                    break

                if captured_pages and not captured_pages[-1].get("has_more"):
                    self.logger.info(f"All {list_type} captured (hasMore=false)")
                    break

                if same_count >= max_stale:
                    self.logger.info(
                        f"No new {list_type} data after {max_stale} scrolls"
                    )
                    break

            all_users = []
            for page in captured_pages:
                all_users.extend(page.get("users", []))

            self.logger.info(
                f"Fetched {len(all_users)} {list_type} total "
                f"from {len(captured_pages)} pages"
            )
            return all_users

        finally:
            tab.remove_handler(cdp_network.ResponseReceived, _on_response)

    async def fetch_following(self, **kwargs) -> list[dict]:
        """Fetch the user's following list. Shorthand for ``fetch_user_list('following')``."""
        return await self.fetch_user_list(list_type="following", **kwargs)

    async def fetch_followers(self, **kwargs) -> list[dict]:
        """Fetch the user's followers list. Shorthand for ``fetch_user_list('followers')``."""
        return await self.fetch_user_list(list_type="followers", **kwargs)

    # ── Parsing helpers ──────────────────────────────────────────────

    @staticmethod
    def parse_user_list(raw_user_list: list[dict]) -> list[dict]:
        """
        Parse a raw user list from ``/api/user/list/`` into flat records.

        Each entry in the API response has a ``user`` sub-dict with the
        actual user data, plus optional ``stats`` and relationship info.

        Returns:
            list[dict]: Flat list of parsed user records.
        """
        parsed = []
        for entry in raw_user_list:
            user = entry.get("user", entry)
            stats = entry.get("stats", user.get("stats", {}))

            avatar = (
                user.get("avatarLarger")
                or user.get("avatarMedium")
                or user.get("avatarThumb", "")
            )

            record = {
                "user_id": user.get("id", ""),
                "username": user.get("uniqueId", ""),
                "nickname": user.get("nickname", ""),
                "sec_uid": user.get("secUid", ""),
                "verified": user.get("verified", False),
                "signature": user.get("signature", ""),
                "avatar_url": avatar,
                "profile_url": f"https://www.tiktok.com/@{user.get('uniqueId', '')}",
                # Stats
                "follower_count": stats.get("followerCount", 0),
                "following_count": stats.get("followingCount", 0),
                "heart_count": stats.get("heartCount", stats.get("heart", 0)),
                "video_count": stats.get("videoCount", 0),
                "digg_count": stats.get("diggCount", 0),
                # Relationship
                "is_following": entry.get("isFollowing", False),
                "is_followed_by": entry.get("isFollowedBy", False),
                "is_friend": entry.get("isFriend", False),
            }
            parsed.append(record)

        return parsed

    @staticmethod
    def parse_videos(raw_videos: list[dict]) -> list[dict]:
        """
        Parse a raw video list from ``/api/post/item_list/`` into flat records.

        Returns:
            list[dict]: Flat list of parsed video records.
        """
        parsed = []
        for item in raw_videos:
            author = item.get("author", {})
            stats = item.get("stats", {})
            video_info = item.get("video", {})
            music = item.get("music", {})

            create_time = item.get("createTime", 0)
            try:
                create_time_fmt = datetime.fromtimestamp(int(create_time)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, OSError):
                create_time_fmt = str(create_time)

            record = {
                "video_id": item.get("id", ""),
                "description": item.get("desc", ""),
                "create_time": create_time,
                "create_time_formatted": create_time_fmt,
                "url": f"https://www.tiktok.com/@{author.get('uniqueId', '')}/video/{item.get('id', '')}",
                # Stats
                "play_count": stats.get("playCount", 0),
                "digg_count": stats.get("diggCount", 0),
                "comment_count": stats.get("commentCount", 0),
                "share_count": stats.get("shareCount", 0),
                "collect_count": stats.get("collectCount", 0),
                # Video details
                "duration": video_info.get("duration", 0),
                "cover_url": video_info.get("cover", ""),
                "dynamic_cover_url": video_info.get("dynamicCover", ""),
                "play_url": video_info.get("playAddr", ""),
                # Music
                "music_title": music.get("title", ""),
                "music_author": music.get("authorName", ""),
                # Author
                "author_username": author.get("uniqueId", ""),
                "author_nickname": author.get("nickname", ""),
                "author_id": author.get("id", ""),
                # Hashtags
                "hashtags": [
                    {
                        "id": t.get("hashtagId", ""),
                        "name": t.get("hashtagName", ""),
                    }
                    for t in item.get("textExtra", [])
                    if t.get("hashtagName")
                ],
                # Misc
                "is_ad": item.get("isAd", False),
                "is_pinned": item.get("isPinnedItem", False),
            }
            parsed.append(record)

        return parsed

    @staticmethod
    def parse_reposts(raw_reposts: list[dict]) -> list[dict]:
        """
        Parse a raw repost list from ``/api/repost/item_list/`` into flat records.

        Repost items have the same structure as regular video items.

        Returns:
            list[dict]: Flat list of parsed repost records.
        """
        # Reposts share the same item structure as videos
        return User.parse_videos(raw_reposts)

    def videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator[Video]:
        """
        Returns the videos of a TikTok User.

        Parameters:
            count: The amount of videos you want returned.
            cursor: The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.
        """
        found = 0
        while found < count:
            params = {
                "secUid": self.sec_uid,
                "count": min(35, count - found),
                "cursor": cursor,
            }

            if hasattr(self, "parent") and hasattr(self.parent, "make_request"):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/post/item_list/",
                        params=params,
                        headers=kwargs.get("headers"),
                        **kwargs,
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
                break

    def liked_videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator[Video]:
        """
        Returns the liked videos of a TikTok User.

        Note: This only works if the user has their liked videos public.
        """
        found = 0
        while found < count:
            params = {
                "secUid": self.sec_uid,
                "count": 30,
                "cursor": cursor,
            }

            if hasattr(self, "parent") and hasattr(self.parent, "make_request"):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/favorite/item_list/",
                        params=params,
                        headers=kwargs.get("headers"),
                        **kwargs,
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
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "verified": self.verified,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "video_count": self.video_count,
            "heart_count": self.heart_count,
            "signature": self.signature,
            "avatar_url": self.avatar_url,
            "has_data": bool(self.as_dict),
        }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"User(username='{getattr(self, 'username', None)}')"


# Helper functions
async def get_user_info(username: str, tab: uc.Tab, wait_time: int = 10) -> User:
    """
    Quick function to get user information from a username.

    Args:
        username: TikTok username (without @)
        tab: nodriver Tab instance
        wait_time: How long to wait for page load

    Returns:
        User instance with loaded data
    """
    user = User(username=username, tab=tab)
    await user.info(tab=tab)
    return user
