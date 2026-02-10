from __future__ import annotations
from helpers import extract_video_id_from_url
from typing import TYPE_CHECKING, AsyncIterator, ClassVar, Iterator, Optional, Union
from datetime import date, datetime
import asyncio
import requests
import re
import os
import glob
import json
import time
import traceback

import nodriver as uc
import nodriver.cdp.network as cdp_network

# Import core utilities
from core.logging_config import get_logger, ProgressIndicator
from core.error_handling import retry_on_exception, safe_execute, validate_url
from core.file_utils import json_handler, file_manager

if TYPE_CHECKING:
    from tiktok import TikTokApi
    from user import User
    from sound import Sound
    from hashtag import Hashtag
    from comment import Comment


class InvalidResponseException(Exception):
    """Exception raised when TikTok returns an invalid response."""
    def __init__(self, response_text, message, error_code=None):
        self.response_text = response_text
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class Video:
    """
    A TikTok Video class using nodriver (async CDP).

    Example Usage
    ```py
    video = api.video(id='7041997751718137094')
    ```
    """

    parent: ClassVar[TikTokApi]

    id: Optional[str]
    """TikTok's ID of the Video"""
    url: Optional[str]
    """The URL of the Video"""
    create_time: Optional[datetime]
    """The creation time of the Video"""
    stats: Optional[dict]
    """TikTok's stats of the Video"""
    author: Optional[User]
    """The User who created the Video"""
    sound: Optional[Sound]
    """The Sound that is associated with the Video"""
    hashtags: Optional[list[Hashtag]]
    """A List of Hashtags on the Video"""
    as_dict: dict
    """The raw data associated with this Video."""

    def __init__(
        self,
        id: Optional[str] = None,
        url: Optional[str] = None,
        data: Optional[dict] = None,
        tab=None,
        # Accept 'driver' kwarg for backward compat, treat as tab
        driver=None,
        **kwargs
    ):
        """
        You must provide the id or a valid url, else this will fail.
        """
        self.id = id
        self.url = url
        self.tab = tab or driver  # backward compat
        self.logger = get_logger("Video")

        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        elif url is not None:
            if not validate_url(url):
                self.logger.warning(f"URL format may be invalid: {url}")
            self.id = extract_video_id_from_url(url)

        if getattr(self, "id", None) is None:
            raise TypeError("You must provide id or url parameter.")

    async def info(self, **kwargs) -> dict:
        """
        Returns a dictionary of all data associated with a TikTok Video.

        Returns:
            dict: A dictionary of all data associated with a TikTok Video.

        Raises:
            InvalidResponseException: If TikTok returns an invalid response.

        Example Usage:
            .. code-block:: python

                url = "https://www.tiktok.com/@user/video/1234567890"
                video_info = await video.info()
        """
        if self.url is None:
            raise TypeError("To call video.info() you need to set the video's url.")

        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        # Navigate to the video URL
        self.logger.info(f"Navigating to: {self.url}")
        await tab.get(self.url)

        # Wait for page to load
        await asyncio.sleep(3)

        # Log the current URL (may differ from requested if redirected)
        try:
            current_url = await tab.evaluate("window.location.href")
            self.logger.debug(f"Current URL after navigation: {current_url}")
        except Exception:
            current_url = "(could not read)"

        # Get page source
        page_source = await tab.get_content()
        page_length = len(page_source) if page_source else 0
        self.logger.debug(f"Page source length: {page_length:,} chars")

        if page_length == 0:
            raise InvalidResponseException(
                "", "Page source is empty – browser may not have loaded the page."
            )

        # ── Diagnostics: detect common blocking scenarios ────────────
        page_lower = page_source[:5000].lower()

        # Page title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page_source[:3000], re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1).strip() if title_match else "(no <title>)"
        self.logger.info(f"Page title: {page_title}")

        # Captcha / verification check
        captcha_indicators = ["captcha", "verify", "verification", "tiktok-verify-page"]
        detected_captcha = [ind for ind in captcha_indicators if ind in page_lower]
        if detected_captcha:
            self.logger.warning(f"Possible CAPTCHA/verification detected: {detected_captcha}")

        # Login wall check
        login_indicators = ["login-modal", "loginContainer", "please log in", "log in to tiktok"]
        detected_login = [ind for ind in login_indicators if ind in page_lower]
        if detected_login:
            self.logger.warning(f"Possible login wall detected: {detected_login}")

        # List all <script id="..."> tags to see what data TikTok provided
        script_ids = re.findall(r'<script\s+id="([^"]+)"', page_source)
        self.logger.debug(f"Script IDs found in page: {script_ids}")

        # ── Extract JSON from a <script id="…"> tag ─────────────────
        # Uses regex so attribute order doesn't matter (TikTok changes this).
        def _extract_script_json(script_id: str) -> Optional[dict]:
            """Find <script id="script_id" …>…</script> and parse its JSON."""
            pattern = re.compile(
                rf'<script\s[^>]*id\s*=\s*"{re.escape(script_id)}"[^>]*>(.*?)</script>',
                re.DOTALL,
            )
            m = pattern.search(page_source)
            if not m:
                return None
            raw = m.group(1).strip()
            self.logger.debug(f"Found <script id=\"{script_id}\"> — content length: {len(raw):,} chars")
            return json.loads(raw)

        # ── Try SIGI_STATE first ─────────────────────────────────────
        sigi_data = None
        try:
            sigi_data = _extract_script_json("SIGI_STATE")
        except json.JSONDecodeError as e:
            self.logger.error(f"SIGI_STATE JSON parse error: {e}")

        if sigi_data is not None:
            self.logger.debug(f"SIGI_STATE top-level keys: {list(sigi_data.keys())[:15]}")
            try:
                if "ItemModule" not in sigi_data:
                    self.logger.error(f"'ItemModule' not found. Keys: {list(sigi_data.keys())[:15]}")
                    raise KeyError("ItemModule")

                item_ids = list(sigi_data["ItemModule"].keys())[:10]
                self.logger.debug(f"ItemModule video IDs: {item_ids}  (looking for: {self.id})")
                video_info = sigi_data["ItemModule"][self.id]
            except KeyError as e:
                raise InvalidResponseException(
                    page_source, f"SIGI_STATE data missing expected key: {e}"
                )
        else:
            self.logger.debug("SIGI_STATE not found, trying __UNIVERSAL_DATA_FOR_REHYDRATION__")

            # ── Try __UNIVERSAL_DATA_FOR_REHYDRATION__ ───────────────
            universal_data = None
            try:
                universal_data = _extract_script_json("__UNIVERSAL_DATA_FOR_REHYDRATION__")
            except json.JSONDecodeError as e:
                self.logger.error(f"__UNIVERSAL_DATA JSON parse error: {e}")
                raise InvalidResponseException(
                    page_source, f"Failed to parse __UNIVERSAL_DATA JSON: {e}"
                )

            if universal_data is None:
                self._dump_page_snippet(page_source, "Neither SIGI_STATE nor __UNIVERSAL_DATA_FOR_REHYDRATION__ found")
                raise InvalidResponseException(
                    page_source,
                    f"No known data script tag found in page. "
                    f"Page title='{page_title}', url='{current_url}', "
                    f"page_length={page_length:,}, script_ids={script_ids}. "
                    f"This may indicate a CAPTCHA, login wall, geo-block, or page structure change."
                )

            available_keys = list(universal_data.keys())[:15]
            self.logger.debug(f"__UNIVERSAL_DATA top-level keys: {available_keys}")

            default_scope = universal_data.get("__DEFAULT_SCOPE__", {})
            scope_keys = list(default_scope.keys())[:15]
            self.logger.debug(f"__DEFAULT_SCOPE__ keys: {scope_keys}")

            video_detail = default_scope.get("webapp.video-detail", {})
            status_code = video_detail.get("statusCode", "(missing)")
            status_msg = video_detail.get("statusMsg", "(none)")
            self.logger.debug(f"video-detail statusCode={status_code}, statusMsg='{status_msg}'")

            if video_detail.get("statusCode", 0) != 0:
                self.logger.error(
                    f"TikTok returned error status: code={status_code}, msg='{status_msg}'"
                )
                raise InvalidResponseException(
                    page_source,
                    f"TikTok video-detail error: statusCode={status_code}, statusMsg='{status_msg}'"
                )

            video_info = video_detail.get("itemInfo", {}).get("itemStruct")
            if video_info is None:
                detail_keys = list(video_detail.keys())[:15]
                self.logger.error(
                    f"'itemStruct' not found in video-detail. "
                    f"video-detail keys: {detail_keys}"
                )
                raise InvalidResponseException(
                    page_source,
                    f"itemStruct missing from video-detail. Keys present: {detail_keys}"
                )

            self.logger.debug(f"Successfully extracted video_info (keys: {list(video_info.keys())[:10]})")

        self.as_dict = video_info
        self.__extract_from_data()

        # Update parent session with cookies if available
        if hasattr(self, "parent") and hasattr(self.parent, "_update_session_from_tab"):
            await self.parent._update_session_from_tab()

        return video_info

    def _dump_page_snippet(self, page_source: str, reason: str) -> None:
        """Log a truncated page source snippet for debugging."""
        self.logger.error(f"Page diagnosis: {reason}")
        # Log first 1500 chars to capture <head> / visible structure
        snippet = page_source[:1500] if page_source else "(empty)"
        self.logger.debug(f"Page source snippet (first 1500 chars):\n{snippet}")

    def bytes(self, stream: bool = False, **kwargs) -> Union[bytes, Iterator[bytes]]:
        """
        Returns the bytes of a TikTok Video.

        Example Usage:
            .. code-block:: python

                video_bytes = video.bytes()

                # Saving The Video
                with open('saved_video.mp4', 'wb') as output:
                    output.write(video_bytes)
        """
        if not hasattr(self, "as_dict") or not self.as_dict:
            raise ValueError("Video info must be loaded first. Call info() method.")

        cookies = {}
        if hasattr(self, "parent") and hasattr(self.parent, "get_session_cookies"):
            # get_session_cookies is async but bytes() is sync — use cached session cookies
            cookies = dict(self.parent.session.cookies)

        download_addr = self.as_dict.get("video", {}).get("downloadAddr")
        if not download_addr:
            raise ValueError("Download address not found in video data.")

        headers = {
            "range": "bytes=0-",
            "accept-encoding": "identity;q=1, *;q=0",
            "referer": "https://www.tiktok.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        if stream:
            def stream_bytes():
                resp = requests.get(download_addr, headers=headers, cookies=cookies, stream=True)
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            return stream_bytes()
        else:
            resp = requests.get(download_addr, headers=headers, cookies=cookies)
            resp.raise_for_status()
            return resp.content

    def __extract_from_data(self) -> None:
        """Extract video information from raw data."""
        data = self.as_dict
        self.id = data.get("id")

        timestamp = data.get("createTime", None)
        if timestamp is not None:
            try:
                timestamp = int(timestamp)
                self.create_time = datetime.fromtimestamp(timestamp)
            except (ValueError, TypeError):
                self.create_time = None
        else:
            self.create_time = None

        self.stats = data.get("statsV2") or data.get("stats")

        author = data.get("author")
        if hasattr(self, "parent"):
            if isinstance(author, str):
                self.author = self.parent.user(username=author)
            else:
                self.author = self.parent.user(data=author)

            self.sound = self.parent.sound(data=data)

            self.hashtags = [
                self.parent.hashtag(data=hashtag) for hashtag in data.get("challenges", [])
            ]
        else:
            self.author = author
            self.sound = data.get("music")
            self.hashtags = data.get("challenges", [])

        if getattr(self, "id", None) is None and hasattr(self, "parent"):
            if hasattr(self.parent, "logger"):
                self.parent.logger.error(
                    f"Failed to create Video with data: {data}\nwhich has keys {data.keys()}"
                )

    async def fetch_comments(self, **kwargs) -> list[dict]:
        """
        Fetch all comments **and their replies** for this video using CDP
        network capture.

        **Phase 1** — Top-level comments:
          Navigate to the video page, click the comment button, and scroll
          to trigger ``/api/comment/list/`` pagination via CDP interception.

        **Phase 2** — Replies:
          For every top-level comment that has ``reply_comment_total > 0``,
          click the *"View N replies"* expander inside the comment panel.
          TikTok will call ``/api/comment/list/reply/``; we capture those
          responses the same way.

        Args:
            tab: nodriver Tab instance (or 'driver' for backward compat).
            max_pages: Stop after this many top-level API pages (default 50).
            scroll_pause: Seconds to wait between scrolls (default 2.0).
            fetch_replies: Whether to also fetch replies (default True).
            max_reply_pages_per_comment: Max reply pages per comment (default 20).

        Returns:
            list[dict]: Every comment and reply dict exactly as returned by
            TikTok's API, including the nested ``user`` object.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        if not self.url:
            raise ValueError("Video URL is not set.")

        max_pages = kwargs.get("max_pages", 50)
        scroll_pause = kwargs.get("scroll_pause", 2.0)
        fetch_replies = kwargs.get("fetch_replies", True)
        max_reply_pages_per_comment = kwargs.get("max_reply_pages_per_comment", 20)

        # ── Storage for captured API responses ───────────────────────
        captured_comment_pages: list[dict] = []   # /api/comment/list/
        captured_reply_pages: list[dict] = []     # /api/comment/list/reply/
        total_expected = None

        # ── CDP event handler ────────────────────────────────────────
        async def _on_response(event: cdp_network.ResponseReceived):
            """Fires for every HTTP response the browser receives."""
            url = event.response.url
            if "/api/comment/list/" not in url:
                return

            is_reply_api = "/api/comment/list/reply/" in url
            kind = "reply" if is_reply_api else "comment"

            self.logger.info(
                f"CDP captured {kind} API response: "
                f"status={event.response.status}, url={url[:200]}"
            )

            # Fetch the response body
            try:
                body_str, is_base64 = await tab.send(
                    cdp_network.get_response_body(event.request_id)
                )

                if is_base64:
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8", errors="replace")

                data = json.loads(body_str)
            except Exception as e:
                self.logger.warning(f"Could not read body for {url[:120]}: {e}")
                return

            status_code = data.get("status_code", -1)
            if status_code != 0:
                self.logger.warning(
                    f"API status_code={status_code}, "
                    f"status_msg='{data.get('status_msg', '')}'"
                )
                return

            comments = data.get("comments") or data.get("comment_list") or []
            has_more = data.get("has_more", 0)
            next_cursor = data.get("cursor", 0)

            page_record = {
                "comments": comments,
                "has_more": has_more,
                "cursor": next_cursor,
                "total": data.get("total"),
            }

            if is_reply_api:
                captured_reply_pages.append(page_record)
                self.logger.info(
                    f"Reply page {len(captured_reply_pages)}: got {len(comments)} replies "
                    f"(running reply total: {sum(len(r['comments']) for r in captured_reply_pages)}, "
                    f"has_more={has_more})"
                )
            else:
                nonlocal total_expected
                if total_expected is None:
                    total_expected = data.get("total")
                    self.logger.info(
                        f"TikTok reports {total_expected} total comments for this video"
                    )
                captured_comment_pages.append(page_record)
                self.logger.info(
                    f"Comment page {len(captured_comment_pages)}: got {len(comments)} comments "
                    f"(running total: {sum(len(r['comments']) for r in captured_comment_pages)}, "
                    f"has_more={has_more})"
                )

        # ── 1. Register CDP handler ──────────────────────────────────
        tab.add_handler(cdp_network.ResponseReceived, _on_response)
        self.logger.info("CDP Network.responseReceived handler registered")

        try:
            # ── 2. Navigate to the video page ────────────────────────
            self.logger.info(f"Navigating to video page: {self.url}")
            await tab.get(self.url)
            await asyncio.sleep(4)

            try:
                current_url = await tab.evaluate("window.location.href")
                self.logger.info(f"Current URL: {current_url}")
            except Exception:
                pass

            # ── 3. Click the comment button to open the panel ────────
            self.logger.info("Clicking the comment button to open comment panel...")

            click_js = """
            (function() {
                // Strategy 1: data-e2e attribute on the icon span
                var icon = document.querySelector('[data-e2e="comment-icon"]');
                if (icon) {
                    var btn = icon.closest('button') || icon;
                    btn.click();
                    return 'clicked via data-e2e comment-icon';
                }

                // Strategy 2: button whose aria-label contains "comment"
                var buttons = document.querySelectorAll('button[aria-label]');
                for (var i = 0; i < buttons.length; i++) {
                    var label = buttons[i].getAttribute('aria-label').toLowerCase();
                    if (label.includes('comment') || label.includes('comentar')) {
                        buttons[i].click();
                        return 'clicked via aria-label: ' + buttons[i].getAttribute('aria-label');
                    }
                }

                // Strategy 3: SVG path heuristic (the speech-bubble icon)
                var svgs = document.querySelectorAll('button svg path');
                for (var j = 0; j < svgs.length; j++) {
                    var d = svgs[j].getAttribute('d') || '';
                    if (d.includes('21.5') && d.includes('comment')) {
                        var svgBtn = svgs[j].closest('button');
                        if (svgBtn) { svgBtn.click(); return 'clicked via SVG path'; }
                    }
                }

                return 'comment button not found';
            })()
            """

            click_result = await tab.evaluate(click_js)
            self.logger.info(f"Comment button click result: {click_result}")
            await asyncio.sleep(3)

            # ── 4. Wait for initial comment API call ─────────────────
            self.logger.info("Waiting for comment API response after click...")
            for wait_sec in range(15):
                if captured_comment_pages:
                    break
                await asyncio.sleep(1)

            if not captured_comment_pages:
                self.logger.warning(
                    "No comment API call detected after clicking. "
                    "Trying to scroll the page to trigger loading..."
                )
                for _ in range(3):
                    await tab.evaluate("window.scrollBy(0, 400)")
                    await asyncio.sleep(2)
                    if captured_comment_pages:
                        break

            if not captured_comment_pages:
                self.logger.error(
                    "Still no comment API calls. The comment panel may not "
                    "have opened (CAPTCHA, login wall, or layout change)."
                )

            # ── 5. Scroll through top-level comments ─────────────────
            same_count = 0
            max_stale = 6

            for scroll_num in range(max_pages * 3):
                previous_total = len(captured_comment_pages)

                await tab.evaluate("""
                    (function() {
                        var list = document.querySelector('[data-e2e="comment-list"]');
                        if (list) {
                            var p = list.parentElement;
                            while (p && p.scrollHeight <= p.clientHeight + 10) p = p.parentElement;
                            if (p) { p.scrollTop += 600; return; }
                        }
                        var rightPanel = document.querySelector(
                            '#main-content-video_detail > div > div:nth-child(2)'
                        );
                        if (rightPanel && rightPanel.scrollHeight > rightPanel.clientHeight + 10) {
                            rightPanel.scrollTop += 600;
                            return;
                        }
                        var clsCont = document.querySelector('[class*="DivCommentListContainer"]');
                        if (clsCont) { clsCont.scrollTop += 600; return; }
                        var ce = document.querySelector('[data-e2e="comment-icon"]');
                        if (ce) {
                            var ancestor = ce.closest('[style*="overflow"]')
                                || document.querySelector('[class*="CommentList"]');
                            if (ancestor) { ancestor.scrollTop += 600; return; }
                        }
                        window.scrollBy(0, 600);
                    })()
                """)

                await asyncio.sleep(scroll_pause)

                if len(captured_comment_pages) > previous_total:
                    same_count = 0
                    self.logger.debug(
                        f"Scroll {scroll_num + 1}: new API page captured "
                        f"(total pages: {len(captured_comment_pages)})"
                    )
                else:
                    same_count += 1

                if len(captured_comment_pages) >= max_pages:
                    self.logger.info(f"Reached max_pages={max_pages} — stopping")
                    break

                if captured_comment_pages and not captured_comment_pages[-1].get("has_more"):
                    self.logger.info("Last page has_more=0 — all top-level comments captured")
                    break

                if same_count >= max_stale:
                    self.logger.info(
                        f"No new data after {max_stale} scrolls — stopping "
                        f"(captured {len(captured_comment_pages)} pages)"
                    )
                    break

            # ── Flatten top-level comments ───────────────────────────
            all_top_comments: list[dict] = []
            for page in captured_comment_pages:
                all_top_comments.extend(page.get("comments", []))

            self.logger.info(
                f"Phase 1 complete: {len(all_top_comments)} top-level comments "
                f"(expected {total_expected}, from {len(captured_comment_pages)} pages)"
            )

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # Phase 2 — Fetch replies for comments that have them
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            all_replies: list[dict] = []

            if fetch_replies:
                comments_with_replies = [
                    c for c in all_top_comments
                    if (c.get("reply_comment_total") or 0) > 0
                ]

                if comments_with_replies:
                    self.logger.info(
                        f"Phase 2: {len(comments_with_replies)} comments have replies — "
                        f"expanding reply threads..."
                    )

                    # Click every "View N replies" link in the DOM.
                    # TikTok renders these as <p data-e2e="view-more-X">
                    # or generic clickable elements with text like
                    # "View 2 replies" / "Ver 2 respuestas" / etc.
                    # We click them all at once, then scroll to trigger
                    # pagination for threads that have has_more=1.

                    expand_js = """
                    (function() {
                        var clicked = 0;

                        // Strategy 1: data-e2e attributes for reply expanders
                        var expanders = document.querySelectorAll(
                            '[data-e2e="view-more-1"], '
                            + '[data-e2e="view-more-2"], '
                            + '[data-e2e="view-more-3"]'
                        );
                        expanders.forEach(function(el) {
                            el.click();
                            clicked++;
                        });

                        // Strategy 2: any element whose text matches
                        // "View N replies" / "View N more replies" pattern
                        // (works across localizations by matching digits)
                        var allP = document.querySelectorAll(
                            'p[data-e2e*="view-more"], '
                            + 'span[data-e2e*="view-more"], '
                            + '[class*="ReplyActionText"]'
                        );
                        allP.forEach(function(el) {
                            if (!el.dataset._ttclicked) {
                                el.click();
                                el.dataset._ttclicked = '1';
                                clicked++;
                            }
                        });

                        // Strategy 3: walk all elements with reply-like text
                        var walker = document.createTreeWalker(
                            document.body, NodeFilter.SHOW_ELEMENT
                        );
                        while (walker.nextNode()) {
                            var node = walker.currentNode;
                            var txt = (node.textContent || '').trim();
                            // Match "View 3 replies", "View 1 reply",
                            // "View more replies", localized variants, etc.
                            if (/^(view|ver|vezi|voir|bekijk|zeige)\\s+\\d+/i.test(txt)
                                || /^view\\s+more\\s+repl/i.test(txt)) {
                                // Only click leaf / near-leaf elements
                                if (node.children.length <= 2
                                    && !node.dataset._ttclicked) {
                                    node.click();
                                    node.dataset._ttclicked = '1';
                                    clicked++;
                                }
                            }
                        }

                        return clicked;
                    })()
                    """

                    reply_pages_before = len(captured_reply_pages)
                    expand_count = await tab.evaluate(expand_js)
                    self.logger.info(
                        f"Clicked {expand_count} 'View replies' expanders"
                    )

                    # Wait for reply API calls to come in
                    await asyncio.sleep(3)

                    # Keep scrolling + re-clicking to handle pagination
                    # inside reply threads (has_more=1 on reply pages)
                    reply_stale = 0
                    max_reply_stale = 4

                    for reply_scroll in range(max_reply_pages_per_comment * len(comments_with_replies)):
                        prev_reply_count = len(captured_reply_pages)

                        # Scroll the comment panel
                        await tab.evaluate("""
                            (function() {
                                var list = document.querySelector('[data-e2e="comment-list"]');
                                if (list) {
                                    var p = list.parentElement;
                                    while (p && p.scrollHeight <= p.clientHeight + 10) p = p.parentElement;
                                    if (p) { p.scrollTop += 600; return; }
                                }
                                var rightPanel = document.querySelector(
                                    '#main-content-video_detail > div > div:nth-child(2)'
                                );
                                if (rightPanel && rightPanel.scrollHeight > rightPanel.clientHeight + 10) {
                                    rightPanel.scrollTop += 600;
                                    return;
                                }
                                var clsCont = document.querySelector('[class*="DivCommentListContainer"]');
                                if (clsCont) { clsCont.scrollTop += 600; return; }
                                window.scrollBy(0, 600);
                            })()
                        """)

                        await asyncio.sleep(scroll_pause)

                        # Re-click any newly visible "View more replies" buttons
                        await tab.evaluate(expand_js)
                        await asyncio.sleep(0.5)

                        if len(captured_reply_pages) > prev_reply_count:
                            reply_stale = 0
                            self.logger.debug(
                                f"Reply scroll {reply_scroll + 1}: new reply page "
                                f"(total reply pages: {len(captured_reply_pages)})"
                            )
                        else:
                            reply_stale += 1

                        if reply_stale >= max_reply_stale:
                            self.logger.info(
                                f"No new reply data after {max_reply_stale} scrolls — "
                                f"stopping (captured {len(captured_reply_pages)} reply pages)"
                            )
                            break

                    # Flatten replies
                    for page in captured_reply_pages:
                        all_replies.extend(page.get("comments", []))

                    self.logger.info(
                        f"Phase 2 complete: {len(all_replies)} replies extracted "
                        f"from {len(captured_reply_pages)} reply API pages"
                    )
                else:
                    self.logger.info(
                        "Phase 2: no top-level comments have replies — skipping"
                    )

        finally:
            # ── Remove handler ───────────────────────────────────────
            try:
                tab.handlers.get(cdp_network.ResponseReceived, []).clear()
            except Exception:
                pass

        # ── Merge top-level comments + replies ───────────────────────
        all_comments = all_top_comments + all_replies

        self.logger.info(
            f"Total extracted: {len(all_top_comments)} comments + "
            f"{len(all_replies)} replies = {len(all_comments)} "
            f"(expected {total_expected})"
        )
        return all_comments

    def parse_comments(self, raw_comments: list[dict]) -> list[dict]:
        """
        Parse raw TikTok API comment dicts into clean, flat records with
        user details.

        Handles both top-level comments (from ``/api/comment/list/``) and
        replies (from ``/api/comment/list/reply/``).  Replies are identified
        by ``reply_id != "0"``.

        Args:
            raw_comments: List of comment dicts straight from the API.

        Returns:
            list[dict]: Cleaned comment records.
        """
        parsed: list[dict] = []
        for c in raw_comments:
            user = c.get("user") or {}
            avatar = user.get("avatar_thumb") or {}
            avatar_urls = avatar.get("url_list") or []

            # Label (e.g. "Creator" when the commenter is the video author)
            label_list = c.get("label_list") or []
            label_text = c.get("label_text") or ""
            if not label_text and label_list:
                label_text = label_list[0].get("text", "")

            # Determine parent comment ID for replies
            reply_id = c.get("reply_id", "0")
            is_reply = reply_id != "0"

            record = {
                # ── comment fields ─────────────────────────────────
                "comment_id": c.get("cid"),
                "text": c.get("text", ""),
                "create_time": c.get("create_time"),
                "create_time_formatted": None,
                "digg_count": c.get("digg_count", 0),
                "reply_count": c.get("reply_comment_total", 0),
                "is_author_digged": c.get("is_author_digged", False),
                "comment_language": c.get("comment_language", ""),
                "is_reply": is_reply,
                "reply_id": reply_id,
                "reply_to_reply_id": c.get("reply_to_reply_id", "0"),
                "parent_comment_id": reply_id if is_reply else None,
                "aweme_id": c.get("aweme_id"),
                # ── label / badge ──────────────────────────────────
                "label_text": label_text,
                # ── user fields ────────────────────────────────────
                "user_id": user.get("uid"),
                "username": user.get("unique_id"),
                "nickname": user.get("nickname"),
                "sec_uid": user.get("sec_uid"),
                "avatar_url": avatar_urls[0] if avatar_urls else None,
                "user_profile_url": (
                    f"https://www.tiktok.com/@{user.get('unique_id')}"
                    if user.get("unique_id") else None
                ),
                # ── images attached to comment ─────────────────────
                "has_images": bool(c.get("image_list")),
                "image_urls": [],
            }

            # Format timestamp
            if record["create_time"]:
                try:
                    record["create_time_formatted"] = datetime.fromtimestamp(
                        int(record["create_time"])
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            # Collect image URLs if present
            for img in (c.get("image_list") or []):
                crop = img.get("crop_url") or img.get("origin_url") or {}
                urls = crop.get("url_list") or []
                if urls:
                    record["image_urls"].append(urls[0])

            parsed.append(record)
        return parsed

    async def fetch_comments_from_network(self, **kwargs) -> list[dict]:
        """
        Fetch comments dynamically by scrolling and downloading network API responses directly.

        Uses comprehensive network monitoring including Chrome DevTools Protocol (CDP) and
        JavaScript interception to capture TikTok comment API requests with authentication tokens.

        Args:
            tab: nodriver Tab instance (or pass as 'driver' for backward compat).

        Returns:
            list: List of all comment JSONs captured from the network.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        if not self.url:
            raise ValueError("Video URL is not set.")

        self.logger.info(f"Starting comment extraction for video: {self.id}")
        self.logger.info(f"Navigating to video URL: {self.url}")
        await tab.get(self.url)
        await asyncio.sleep(3)

        comment_responses = []
        seen_request_urls = set()
        collected_api_urls = []

        self.logger.info("Initializing network monitoring and request capture...")

        # ── Enable CDP monitoring ────────────────────────────────────
        self.logger.debug("Setting up CDP network monitoring...")
        try:
            import nodriver.cdp.network as net
            import nodriver.cdp.runtime as runtime_cdp
            import nodriver.cdp.page as page_cdp
            import nodriver.cdp.security as security_cdp

            await tab.send(net.enable(
                max_total_buffer_size=10_000_000,
                max_resource_buffer_size=5_000_000,
                max_post_data_size=65536,
            ))
            await tab.send(runtime_cdp.enable())
            await tab.send(page_cdp.enable())
            await tab.send(security_cdp.enable())

            # Set user agent override
            await tab.send(net.set_user_agent_override(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ))

            self.logger.info("CDP network monitoring enabled (network, runtime, page, security)")
        except Exception as e:
            self.logger.warning(f"Could not enable CDP: {e}")

        # ── JavaScript-based request interception ────────────────────
        monitor_script = """
        (function() {
            window.capturedCommentRequests = window.capturedCommentRequests || [];
            window.allNetworkActivity = window.allNetworkActivity || [];
            window.realTimeRequests = window.realTimeRequests || [];

            const urlObserver = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'href') {
                        const url = mutation.target.href;
                        if (url && url.includes('/api/comment/list/')) {
                            window.realTimeRequests.push({
                                type: 'url_modification',
                                url: url,
                                timestamp: Date.now()
                            });
                        }
                    }
                });
            });
            urlObserver.observe(document, {
                attributes: true,
                subtree: true,
                attributeFilter: ['href', 'src']
            });

            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                const originalUrl = args[0];
                const options = args[1] || {};
                const promise = originalFetch.apply(this, args);
                promise.then(response => {
                    const finalUrl = response.url;
                    if (finalUrl && finalUrl.includes('/api/comment/list/')) {
                        const requestInfo = {
                            type: 'fetch_complete',
                            originalUrl: originalUrl,
                            finalUrl: finalUrl,
                            method: options.method || 'GET',
                            headers: options.headers || {},
                            body: options.body,
                            timestamp: Date.now(),
                            status: response.status,
                            redirected: response.redirected
                        };
                        window.capturedCommentRequests.push(requestInfo);
                        window.realTimeRequests.push(requestInfo);
                    }
                }).catch(function(){});
                return promise;
            };

            const originalXHROpen = XMLHttpRequest.prototype.open;
            const originalXHRSend = XMLHttpRequest.prototype.send;
            const originalXHRSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                this._method = method;
                this._originalUrl = url;
                this._headers = {};
                this._requestId = Math.random().toString(36).substr(2, 9);
                if (typeof url === 'string' && url.includes('/api/comment/list/')) {
                    this._isCommentRequest = true;
                }
                return originalXHROpen.apply(this, [method, url, ...args]);
            };

            XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                if (this._isCommentRequest) {
                    this._headers[name] = value;
                }
                return originalXHRSetRequestHeader.apply(this, arguments);
            };

            XMLHttpRequest.prototype.send = function(body) {
                if (this._isCommentRequest) {
                    this.addEventListener('readystatechange', () => {
                        if (this.readyState === 4) {
                            const finalUrl = this.responseURL || this._originalUrl;
                            const requestInfo = {
                                type: 'xhr_complete',
                                originalUrl: this._originalUrl,
                                finalUrl: finalUrl,
                                method: this._method,
                                headers: this._headers,
                                body: body,
                                timestamp: Date.now(),
                                status: this.status,
                                requestId: this._requestId
                            };
                            window.capturedCommentRequests.push(requestInfo);
                            window.realTimeRequests.push(requestInfo);
                        }
                    });
                }
                return originalXHRSend.apply(this, arguments);
            };

            window.getRealTimeRequests = function() {
                return window.realTimeRequests.slice();
            };

            console.log('Enhanced real-time comment API monitoring active');
            return 'Monitoring /api/comment/list/ with real-time URL tracking';
        })();
        """

        result = await tab.evaluate(monitor_script)
        self.logger.info(f"JS interception hooks injected: {result}")

        # Verify hooks are active
        hooks_check = await tab.evaluate(
            "typeof window.capturedCommentRequests !== 'undefined' "
            "&& typeof window.fetch.__proto__ !== 'undefined'"
        )
        self.logger.info(f"JS hooks verification: {'OK' if hooks_check else 'FAILED — hooks may not work'}")
        await asyncio.sleep(1)

        try:
            # ── Helper: collect JS-captured URLs ─────────────────────
            async def collect_js_urls():
                captured = await tab.evaluate(
                    "window.capturedCommentRequests || []"
                )
                for req in (captured or []):
                    full_url = req.get("finalUrl", req.get("fullUrl", req.get("url", "")))
                    if full_url and full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ JS captured: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  URL: {full_url}")

            async def collect_realtime_urls():
                real_time = await tab.evaluate(
                    "window.getRealTimeRequests ? window.getRealTimeRequests() : []"
                )
                for req in (real_time or []):
                    full_url = req.get("finalUrl", req.get("fullUrl", req.get("url", "")))
                    if full_url and full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ Real-time captured: {full_url}")

            async def collect_perf_urls():
                perf_requests = await tab.evaluate("""
                    (function() {
                        var requests = [];
                        if (window.performance && window.performance.getEntriesByType) {
                            var entries = window.performance.getEntriesByType('resource');
                            for (var i = 0; i < entries.length; i++) {
                                if (entries[i].name.includes('/api/comment/list/')) {
                                    requests.push({url: entries[i].name});
                                }
                            }
                        }
                        return requests;
                    })()
                """)
                for request in (perf_requests or []):
                    if request["url"] not in seen_request_urls:
                        seen_request_urls.add(request["url"])
                        collected_api_urls.append(request["url"])
                        self.logger.debug(f"✓ Performance API captured: {request['url']}")

            # ── Wait for comment section ─────────────────────────────
            comment_list_css = '#main-content-video_detail div div:nth-child(2) div:nth-child(1) div:nth-child(2) div:nth-child(2)'
            try:
                await tab.select(comment_list_css, timeout=10)
                self.logger.info("Comment section found on page")
            except Exception:
                self.logger.warning("Comment section not found (CSS selector timed out) — scrolling anyway")

            # ── Scroll loop ──────────────────────────────────────────
            last_count = -1
            same_count = 0
            max_same = 5
            scroll_iteration = 0

            self.logger.info("Scrolling through comment section to capture API requests...")

            while True:
                # Count current comments for logging
                count_result = await tab.evaluate("""
                    (function() {
                        var section = document.querySelector('#main-content-video_detail');
                        if (!section) return {count: 0, height: 0};
                        var commentContainer = section.querySelector('div > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)');
                        if (!commentContainer) return {count: 0, height: document.body.scrollHeight};
                        return {
                            count: commentContainer.children.length,
                            height: commentContainer.scrollHeight
                        };
                    })()
                """)
                count = (count_result or {}).get("count", 0)

                if count == last_count:
                    same_count += 1
                else:
                    same_count = 0
                last_count = count

                # Collect captured requests after each scroll
                prev_url_count = len(collected_api_urls)
                await collect_js_urls()
                await collect_realtime_urls()
                await collect_perf_urls()
                new_urls = len(collected_api_urls) - prev_url_count

                self.logger.info(
                    f"Scroll {scroll_iteration + 1}: "
                    f"{count} comments on page, "
                    f"{len(collected_api_urls)} API URLs captured "
                    f"(+{new_urls} new), "
                    f"stale={same_count}/{max_same}"
                )

                # Scroll down
                await tab.evaluate("window.scrollBy(0, 500);")
                await asyncio.sleep(2.0)
                scroll_iteration += 1

                if same_count >= max_same:
                    self.logger.info(
                        f"Reached end of comments after {scroll_iteration} scrolls"
                    )
                    break

            # ── Extended final check ─────────────────────────────────
            self.logger.info("Performing extended final check for API requests...")
            await asyncio.sleep(3)
            await collect_js_urls()
            await collect_realtime_urls()
            await collect_perf_urls()

            # ── Diagnostic: dump ALL network activity from Performance API ──
            all_perf = await tab.evaluate("""
                (function() {
                    var entries = performance.getEntriesByType('resource');
                    var apis = [];
                    for (var i = 0; i < entries.length; i++) {
                        if (entries[i].name.includes('/api/')) {
                            apis.push(entries[i].name.substring(0, 200));
                        }
                    }
                    return {
                        total_resources: entries.length,
                        api_urls: apis,
                        captured_hooks: (window.capturedCommentRequests || []).length,
                        realtime_hooks: (window.realTimeRequests || []).length
                    };
                })()
            """)
            if all_perf:
                self.logger.info(f"Performance API: {all_perf.get('total_resources', 0)} total resources")
                api_urls_found = all_perf.get('api_urls', [])
                self.logger.info(f"Performance API: {len(api_urls_found)} /api/ URLs found")
                for u in api_urls_found[:20]:
                    self.logger.info(f"  → {u}")
                self.logger.info(f"JS hooks state: capturedCommentRequests={all_perf.get('captured_hooks', 0)}, realTimeRequests={all_perf.get('realtime_hooks', 0)}")
            else:
                self.logger.warning("Could not read Performance API entries")

            # ── Process collected API URLs ────────────────────────────
            self.logger.info(f"\n=== PROCESSING COLLECTED API URLS ===")
            unique_urls = list(set(collected_api_urls))
            self.logger.info(
                f"Found {len(collected_api_urls)} total URLs ({len(unique_urls)} unique) to process"
            )

            all_responses_data = []

            self.logger.info(f"Processing {len(unique_urls)} unique API URLs...")
            for i, api_url in enumerate(unique_urls, 1):
                self.logger.debug(f"\nProcessing API URL {i}/{len(unique_urls)}")
                self.logger.debug(f"URL: {api_url}")

                try:
                    # Navigate directly to the API URL
                    await tab.get(api_url)
                    await asyncio.sleep(2)

                    # Extract JSON from <pre> tag
                    try:
                        json_text = await tab.evaluate(
                            "document.querySelector('pre') ? document.querySelector('pre').textContent : document.body.innerText"
                        )

                        parsed_json = json.loads(json_text)

                        comment_responses.append(parsed_json)
                        all_responses_data.append({
                            "url": api_url,
                            "json_data": parsed_json,
                            "timestamp": int(time.time() * 1000),
                            "processing_order": i,
                        })

                        self.logger.debug(f"✓ Successfully extracted JSON from {api_url}")

                        if "comments" in parsed_json:
                            ccount = len(parsed_json.get("comments", []))
                            self.logger.debug(f"  Found {ccount} comments in this response")
                        elif "comment_list" in parsed_json:
                            ccount = len(parsed_json.get("comment_list", []))
                            self.logger.debug(f"  Found {ccount} comments in this response")

                    except Exception as e:
                        self.logger.error(
                            f"✗ Error extracting JSON for {api_url}: {e}"
                        )
                        all_responses_data.append({
                            "url": api_url,
                            "error": str(e),
                            "timestamp": int(time.time() * 1000),
                            "processing_order": i,
                        })

                    await asyncio.sleep(1)

                except Exception as e:
                    self.logger.error(f"✗ Error processing {api_url}: {e}")
                    all_responses_data.append({
                        "url": api_url,
                        "error": str(e),
                        "timestamp": int(time.time() * 1000),
                        "processing_order": i,
                    })

            # ── Save responses ────────────────────────────────────────
            self.logger.info(f"\n=== SAVING COLLECTED RESPONSES ===")

            consolidated_filename = f"all_api_responses_{self.id}.json"
            with open(consolidated_filename, "w", encoding="utf-8") as f:
                json.dump(all_responses_data, f, indent=2, ensure_ascii=False)
            self.logger.info(
                f"✓ Saved all {len(all_responses_data)} API responses to {consolidated_filename}"
            )

            for i, response_data in enumerate(all_responses_data, 1):
                if "json_data" in response_data:
                    individual_filename = f"api_response_{i}_{self.id}.json"
                    with open(individual_filename, "w", encoding="utf-8") as f:
                        json.dump(response_data, f, indent=2, ensure_ascii=False)

            successful_responses = sum(1 for r in all_responses_data if "json_data" in r)
            failed_responses = len(all_responses_data) - successful_responses

            self.logger.info(f"✓ Processing summary:")
            self.logger.info(f"  - Successful responses: {successful_responses}")
            self.logger.info(f"  - Failed responses: {failed_responses}")
            self.logger.info(f"  - Total URLs processed: {len(unique_urls)}")

            # Save debug data
            final_captured = await tab.evaluate(
                "window.capturedCommentRequests || []"
            ) or []

            debug_data = {
                "comment_list_requests": final_captured,
                "unique_urls": unique_urls,
                "all_urls": collected_api_urls,
                "total_captured": len(final_captured),
                "unique_count": len(unique_urls),
                "total_urls": len(collected_api_urls),
                "total_responses": len(comment_responses),
                "successful_responses": successful_responses,
                "failed_responses": failed_responses,
            }

            debug_filename = f"comment_list_requests_{self.id}.json"
            with open(debug_filename, "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved debug data to {debug_filename}")

            # Summary
            if collected_api_urls:
                self.logger.info(
                    f"\nCaptured /api/comment/list/ URLs "
                    f"({len(collected_api_urls)} total, {len(unique_urls)} unique):"
                )
                urls_with_mstoken = sum(1 for u in unique_urls if "msToken" in u)
                for i, url in enumerate(unique_urls, 1):
                    has_mstoken = "msToken" in url
                    indicator = " ✓ msToken" if has_mstoken else " ⚠️ No msToken"
                    self.logger.info(f"  {i}. {url[:100]}...{indicator}")

                self.logger.info(
                    f"\nSummary: {urls_with_mstoken}/{len(unique_urls)} URLs contain msToken"
                )
            else:
                self.logger.info("⚠️  No /api/comment/list/ requests found!")

        except Exception as e:
            self.logger.info(f"Error during network capture: {e}")
            traceback.print_exc()

        self.logger.info(f"\nCaptured {len(comment_responses)} comment response objects")

        # Cleanup individual response files
        self.logger.info("\n=== CLEANING UP API RESPONSE FILES ===")
        pattern = f"api_response_*_{self.id}.json"
        files_to_delete = glob.glob(pattern)

        if not files_to_delete:
            patterns = [
                f"api_response_*_{self.id}.json",
                f"api_response_*{self.id}.json",
                f"*api_response*{self.id}*.json",
            ]
            for pat in patterns:
                found_files = glob.glob(pat)
                if found_files:
                    files_to_delete.extend(found_files)

        if files_to_delete:
            self.logger.info(f"Found {len(files_to_delete)} API response files to delete:")
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    self.logger.info(f"✓ Deleted: {file_path}")
                except Exception as e:
                    self.logger.info(f"✗ Error deleting {file_path}: {e}")
        else:
            self.logger.info("No API response files found to delete")

        return comment_responses

    def read_all_api_responses(self, **kwargs) -> list[dict]:
        """
        Read all saved API responses and extract comprehensive comment data.

        Returns:
            list: List of all comments with complete data from API responses
        """
        clean_id = re.sub(r'[?:<>|"*/\\]', "_", str(self.id))
        consolidated_filename = f"all_api_responses_{clean_id}.json"

        try:
            with open(consolidated_filename, "r", encoding="utf-8") as f:
                api_responses = json.load(f)

            self.logger.info(
                f"✓ Loaded {len(api_responses)} API responses from {consolidated_filename}"
            )

            all_comments = []
            total_comments_found = 0

            for response_idx, response_data in enumerate(api_responses):
                self.logger.info(
                    f"\nProcessing API response {response_idx + 1}/{len(api_responses)}"
                )

                if "json_data" not in response_data:
                    self.logger.info(f"  Skipping response {response_idx + 1}: No JSON data")
                    continue

                json_data = response_data["json_data"]
                response_url = response_data.get("url", "Unknown URL")

                comments = []
                if "comments" in json_data:
                    comments = json_data["comments"]
                elif "comment_list" in json_data:
                    comments = json_data["comment_list"]
                elif "data" in json_data and isinstance(json_data["data"], list):
                    comments = json_data["data"]
                else:
                    self.logger.info(f"  No comments found in response {response_idx + 1}")
                    continue

                for comment_idx, comment_data in enumerate(comments):
                    try:
                        detailed_comment = self.extract_comment_details(comment_data)
                        detailed_comment.update({
                            "source_response_index": response_idx,
                            "source_comment_index": comment_idx,
                            "source_url": response_url,
                            "source_timestamp": response_data.get("timestamp", 0),
                            "processing_order": response_data.get(
                                "processing_order", response_idx + 1
                            ),
                        })
                        all_comments.append(detailed_comment)
                        total_comments_found += 1
                    except Exception as e:
                        self.logger.info(
                            f"  Error processing comment {comment_idx + 1}: {e}"
                        )
                        error_comment = {
                            "error": str(e),
                            "raw_comment_data": comment_data,
                            "source_response_index": response_idx,
                            "source_comment_index": comment_idx,
                            "source_url": response_url,
                        }
                        all_comments.append(error_comment)
                        total_comments_found += 1

            self.logger.info(
                f"\n✓ Successfully processed {total_comments_found} total comments"
            )

            if all_comments:
                detailed_filename = f"all_comments_extracted_{self.id}.json"
                with open(detailed_filename, "w", encoding="utf-8") as f:
                    json.dump(all_comments, f, indent=2, ensure_ascii=False)
                self.logger.info(
                    f"✓ Saved {len(all_comments)} detailed comments to {detailed_filename}"
                )

            return all_comments

        except FileNotFoundError:
            self.logger.info(f"✗ API responses file not found: {consolidated_filename}")
            return []
        except json.JSONDecodeError as e:
            self.logger.info(f"✗ Error parsing JSON from {consolidated_filename}: {e}")
            return []
        except Exception as e:
            self.logger.info(f"✗ Error reading API responses: {e}")
            return []

    def get_comments_with_replies(self, **kwargs) -> dict:
        """
        Get all comments and organize them with their replies.
        """
        all_comments = self.read_all_api_responses(**kwargs)

        if not all_comments:
            return {"comments": [], "total": 0, "organized": False}

        comment_tree = {}
        top_level_comments = []

        for comment in all_comments:
            if "error" in comment:
                continue

            comment_id = comment.get("comment_id")
            reply_id = comment.get("reply_id", "0")

            comment["replies"] = []

            if reply_id == "0":
                top_level_comments.append(comment)
                comment_tree[comment_id] = comment
            else:
                if reply_id in comment_tree:
                    comment_tree[reply_id]["replies"].append(comment)
                else:
                    if "orphaned_replies" not in comment_tree:
                        comment_tree["orphaned_replies"] = []
                    comment_tree["orphaned_replies"].append(comment)

        top_level_comments.sort(key=lambda x: x.get("create_time", 0), reverse=True)

        for comment in top_level_comments:
            if comment["replies"]:
                comment["replies"].sort(key=lambda x: x.get("create_time", 0))

        result = {
            "comments": top_level_comments,
            "total_comments": len(top_level_comments),
            "total_replies": sum(len(c["replies"]) for c in top_level_comments),
            "total_all": len(all_comments),
            "organized": True,
            "orphaned_replies": comment_tree.get("orphaned_replies", []),
        }

        organized_filename = f"comments_organized_{self.id}.json"
        with open(organized_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        self.logger.info(f"✓ Saved organized comments to {organized_filename}")

        return result

    def extract_comment_details(self, comment_data: dict) -> dict:
        """Extract comprehensive comment details from TikTok API response."""
        try:
            comment_details = {
                "comment_id": comment_data.get("cid"),
                "text": comment_data.get("text", ""),
                "create_time": comment_data.get("create_time"),
                "digg_count": comment_data.get("digg_count", 0),
                "reply_comment_total": comment_data.get("reply_comment_total", 0),
                "is_author_digged": comment_data.get("is_author_digged", False),
                "user_digged": comment_data.get("user_digged", 0),
                "aweme_id": comment_data.get("aweme_id"),
                "reply_id": comment_data.get("reply_id", "0"),
                "reply_to_reply_id": comment_data.get("reply_to_reply_id", "0"),
                "status": comment_data.get("status", 1),
                "stick_position": comment_data.get("stick_position", 0),
            }

            user_info = comment_data.get("user", {})
            if user_info:
                comment_details.update({
                    "user_id": user_info.get("uid"),
                    "sec_uid": user_info.get("sec_uid"),
                    "username": user_info.get("unique_id"),
                    "nickname": user_info.get("nickname"),
                    "avatar_thumb": user_info.get("avatar_thumb", {}).get("url_list", []),
                    "avatar_medium": user_info.get("avatar_medium", {}).get("url_list", []),
                    "avatar_larger": user_info.get("avatar_larger", {}).get("url_list", []),
                    "signature": user_info.get("signature", ""),
                    "create_time_user": user_info.get("create_time"),
                    "verification_type": user_info.get("verification_type", 0),
                    "custom_verify": user_info.get("custom_verify", ""),
                    "unique_id_modify_time": user_info.get("unique_id_modify_time"),
                    "verified": user_info.get("verified", False),
                })

            if comment_details["create_time"]:
                try:
                    comment_details["create_time_formatted"] = datetime.fromtimestamp(
                        int(comment_details["create_time"])
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    comment_details["create_time_formatted"] = None

            return comment_details

        except Exception as e:
            self.logger.info(f"Error extracting comment details: {e}")
            return {"error": str(e), "raw_data": comment_data}

    async def safe_comments(self, **kwargs) -> AsyncIterator[dict]:
        """
        Fetch comments by scrolling the TikTok video page and scraping the DOM.

        Args:
            tab: nodriver Tab instance (or 'driver' for backward compat).

        Yields:
            dict: Extracted data for each comment, with replies under 'replies'.
        """
        tab = kwargs.get("tab", kwargs.get("driver", self.tab))
        if tab is None:
            raise TypeError("A nodriver Tab instance is required.")

        if not self.url:
            raise ValueError("Video URL is not set.")

        await asyncio.sleep(3)

        # Wait for the comment section to load
        comment_list_css = '#main-content-video_detail div div:nth-child(2) div:nth-child(1) div:nth-child(2) div:nth-child(2)'
        try:
            await tab.select(comment_list_css, timeout=10)
            self.logger.debug("Comment section found")
        except Exception:
            self.logger.debug("Comment section did not load, continuing anyway...")

        # Scroll to load all comments
        last_count = -1
        same_count = 0
        max_same = 5
        scroll_iteration = 0

        self.logger.info("Scrolling through comment section to capture comments...")

        while True:
            count_result = await tab.evaluate("""
                (function() {
                    var section = document.querySelector('#main-content-video_detail');
                    if (!section) return 0;
                    var container = section.querySelector('div > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)');
                    return container ? container.children.length : 0;
                })()
            """)
            count = count_result or 0
            self.logger.debug(
                f"Scroll iteration {scroll_iteration + 1}: Found {count} comments"
            )

            if count == last_count:
                same_count += 1
            else:
                same_count = 0
            last_count = count

            await tab.evaluate("window.scrollBy(0, 500);")
            await asyncio.sleep(2.0)
            scroll_iteration += 1

            if same_count >= max_same:
                self.logger.info(f"✓ Reached end of comments after {scroll_iteration} scrolls")
                break

        # Extract all comments from DOM
        comments_data = await tab.evaluate("""
            (function() {
                var section = document.querySelector('#main-content-video_detail');
                if (!section) return [];
                var container = section.querySelector('div > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)');
                if (!container) return [];

                var results = [];
                var children = container.children;
                for (var i = 0; i < children.length; i++) {
                    var el = children[i];
                    var data = {};

                    // Username
                    var usernameEl = el.querySelector('a p');
                    data.username = usernameEl ? usernameEl.textContent.trim() : null;

                    // User profile URL
                    var profileEl = el.querySelector('.link-a11y-focus');
                    data.user_profile_url = profileEl ? profileEl.href : null;

                    // Comment text
                    var textEl = el.querySelector('span span');
                    data.text = textEl ? textEl.innerText.trim() : null;

                    // Comment time
                    var timeEls = el.querySelectorAll('[class*="TUXText"]');
                    data.time = timeEls.length > 0 ? timeEls[timeEls.length - 1].textContent.trim() : null;

                    // Like count
                    var likeEl = el.querySelector('div:nth-child(2) div:nth-child(2) span');
                    data.like_count = likeEl ? likeEl.textContent.trim() : null;

                    // Comment ID
                    data.comment_id = el.getAttribute('data-id');

                    // Reply count indicator
                    var replyBtn = el.querySelector('[class*="ReplyAction"]') || el.querySelector('span[role="button"]');
                    data.reply_count = 0;
                    if (replyBtn) {
                        var match = replyBtn.textContent.match(/\\d+/);
                        data.reply_count = match ? parseInt(match[0]) : 0;
                    }

                    data.index = i + 1;
                    results.push(data);
                }
                return results;
            })()
        """)

        self.logger.info(f"Found {len(comments_data or [])} comments.")

        for data in (comments_data or []):
            data["replies"] = []
            data["time_now"] = date.today().strftime("%Y-%m-%d %H:%M:%S")
            yield data

    def related_videos(
        self, count: int = 30, cursor: int = 0, **kwargs
    ) -> Iterator[Video]:
        """
        Returns related videos of a TikTok Video.

        Parameters:
            count: The amount of related videos you want returned.
            cursor: The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.
        """
        found = 0
        while found < count:
            params = {
                "itemID": self.id,
                "count": min(16, count - found),
            }

            if hasattr(self, "parent") and hasattr(self.parent, "make_request"):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/related/item_list/",
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

                    break

                except Exception as e:
                    self.logger.info(f"Error fetching related videos: {e}")
                    break
            else:
                break

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"Video(id='{getattr(self, 'id', None)}')"


# Example usage function
async def create_video_from_url(url: str, tab: uc.Tab, **kwargs) -> Video:
    """
    Helper function to create a Video instance from a URL.

    Args:
        url: TikTok video URL
        tab: nodriver Tab instance

    Returns:
        Video: Initialized Video instance
    """
    video = Video(url=url, tab=tab, **kwargs)
    await video.info(tab=tab)
    return video


def create_video_from_id(video_id: str, tab: uc.Tab = None, **kwargs) -> Video:
    """
    Helper function to create a Video instance from an ID.

    Args:
        video_id: TikTok video ID
        tab: nodriver Tab instance

    Returns:
        Video: Initialized Video instance
    """
    video = Video(id=video_id, tab=tab, **kwargs)
    return video
