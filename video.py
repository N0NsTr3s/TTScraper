from __future__ import annotations
from helpers import extract_video_id_from_url
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional, Union
from datetime import date, datetime
import requests
import re
import os
import glob
import json
import time
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

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
    A TikTok Video class using Selenium

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
        driver=None,
        **kwargs
    ):
        """
        You must provide the id or a valid url, else this will fail.
        """
        self.id = id
        self.url = url
        self.driver = driver
        self.logger = get_logger("Video")
        
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        elif url is not None:
            # Validate URL format
            if not validate_url(url):
                self.logger.warning(f"URL format may be invalid: {url}")
            # Extract video ID from URL - simplified without session dependency
            self.id = extract_video_id_from_url(url)

        if getattr(self, "id", None) is None:
            raise TypeError("You must provide id or url parameter.")

    def info(self, **kwargs) -> dict:
        """
        Returns a dictionary of all data associated with a TikTok Video using Selenium.

        Note: This requires a Selenium WebDriver instance.

        Returns:
            dict: A dictionary of all data associated with a TikTok Video.

        Raises:
            InvalidResponseException: If TikTok returns an invalid response, or one we don't understand.

        Example Usage:
            .. code-block:: python

                url = "https://www.tiktok.com/@davidteathercodes/video/7106686413101468970"
                video_info = video.info(driver=driver)
        """
        if self.url is None:
            raise TypeError("To call video.info() you need to set the video's url.")
            
        # Use provided driver or the instance driver
        driver = kwargs.get('driver', self.driver)
        if driver is None:
            raise TypeError("A Selenium WebDriver instance is required.")

        # Navigate to the video URL
        driver.get(self.url)
        
        # Wait for page to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "script"))
            )
        except Exception:
            pass  # Continue even if wait times out

        # Get page source
        page_source = driver.page_source
        
        # Try SIGI_STATE first
        
        start = page_source.find('<script id="SIGI_STATE" type="application/json">')
        if start != -1:
            start += len('<script id="SIGI_STATE" type="application/json">')
            end = page_source.find("</script>", start)

            if end == -1:
                raise InvalidResponseException(
                    page_source, "TikTok returned an invalid response."
                )

            try:
                data = json.loads(page_source[start:end])
                video_info = data["ItemModule"][self.id]
            except (json.JSONDecodeError, KeyError) as e:
                raise InvalidResponseException(
                    page_source, f"Failed to parse SIGI_STATE data: {e}"
                )
        else:
            # Try __UNIVERSAL_DATA_FOR_REHYDRATION__ next
            start = page_source.find('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">')
            if start == -1:
                raise InvalidResponseException(
                    page_source, "TikTok returned an invalid response."
                )

            start += len('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">')
            end = page_source.find("</script>", start)

            if end == -1:
                raise InvalidResponseException(
                    page_source, "TikTok returned an invalid response."
                )

            try:
                data = json.loads(page_source[start:end])
                default_scope = data.get("__DEFAULT_SCOPE__", {})
                video_detail = default_scope.get("webapp.video-detail", {})
                if video_detail.get("statusCode", 0) != 0:  # assume 0 if not present
                    raise InvalidResponseException(
                        page_source, "TikTok returned an invalid response structure."
                    )
                video_info = video_detail.get("itemInfo", {}).get("itemStruct")
                if video_info is None:
                    raise InvalidResponseException(
                        page_source, "TikTok returned an invalid response structure."
                    )
            except (json.JSONDecodeError, KeyError) as e:
                raise InvalidResponseException(
                    page_source, f"Failed to parse UNIVERSAL_DATA data: {e}"
                )

        self.as_dict = video_info
        self.__extract_from_data()

        # Update parent session with cookies if available
        if hasattr(self, 'parent') and hasattr(self.parent, '_update_session_from_driver'):
            self.parent._update_session_from_driver()

        return video_info

    def bytes(self, stream: bool = False, **kwargs) -> Union[bytes, Iterator[bytes]]:
        """
        Returns the bytes of a TikTok Video.

        Example Usage:
            .. code-block:: python

                video_bytes = video.bytes()

                # Saving The Video
                with open('saved_video.mp4', 'wb') as output:
                    output.write(video_bytes)

                # Streaming (if stream=True)
                for chunk in video.bytes(stream=True):
                    # Process or upload chunk
        """
        if not hasattr(self, 'as_dict') or not self.as_dict:
            raise ValueError("Video info must be loaded first. Call info() method.")
            
        # Get cookies from parent if available
        cookies = {}
        if hasattr(self, 'parent') and hasattr(self.parent, 'get_session_cookies'):
            cookies = self.parent.get_session_cookies()
        
        # Get download URL from video data
        download_addr = self.as_dict.get("video", {}).get("downloadAddr")
        if not download_addr:
            raise ValueError("Download address not found in video data.")

        # Set up headers for video download
        headers = {
            "range": 'bytes=0-',
            "accept-encoding": 'identity;q=1, *;q=0',
            "referer": 'https://www.tiktok.com/',
            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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

        self.stats = data.get('statsV2') or data.get('stats')

        # Handle author data
        author = data.get("author")
        if hasattr(self, 'parent'):
            if isinstance(author, str):
                self.author = self.parent.user(username=author)
            else:
                self.author = self.parent.user(data=author)
            
            # Handle sound data
            self.sound = self.parent.sound(data=data)

            # Handle hashtags
            self.hashtags = [
                self.parent.hashtag(data=hashtag) for hashtag in data.get("challenges", [])
            ]
        else:
            self.author = author
            self.sound = data.get("music")
            self.hashtags = data.get("challenges", [])

        if getattr(self, "id", None) is None and hasattr(self, 'parent'):
            # Log error if parent has logger
            if hasattr(self.parent, 'logger'):
                self.parent.logger.error(
                    f"Failed to create Video with data: {data}\nwhich has keys {data.keys()}"
                )


    def fetch_comments_from_network(self, **kwargs) -> list[dict]:
        """
        Fetch comments dynamically by scrolling and downloading network API responses directly.
        
        Uses comprehensive network monitoring including Chrome DevTools Protocol (CDP) and 
        JavaScript interception to capture TikTok comment API requests with authentication tokens.

        Args:
            driver: undetected-chromedriver WebDriver instance.

        Returns:
            list: List of all comment JSONs captured from the network.
        """
        from selenium.webdriver.common.keys import Keys
        import requests
        import json
        import time
        import re
        import traceback

        driver = kwargs.get('driver', self.driver)
        if driver is None:
            raise TypeError("A Selenium WebDriver instance is required.")

        if not self.url:
            raise ValueError("Video URL is not set.")
        
        self.logger.info(f"Starting comment extraction for video: {self.id}")
        self.logger.info(f"Navigating to video URL: {self.url}")
        driver.get(self.url)
        time.sleep(3)  # Let the page load

        # Store captured responses
        comment_responses = []
        seen_request_urls = set()
        collected_api_urls = []

        self.logger.info("Initializing network monitoring and request capture...")
        
        # Enhanced network monitoring setup using Chrome DevTools Protocol
        self.logger.debug("Setting up Chrome DevTools Protocol network monitoring...")
        
        try:
            # Enable comprehensive CDP monitoring
            driver.execute_cdp_cmd('Network.enable', {
                'maxTotalBufferSize': 10000000,  # 10MB buffer
                'maxResourceBufferSize': 5000000,  # 5MB per resource
                'maxPostDataSize': 65536  # 64KB post data
            })
            driver.execute_cdp_cmd('Runtime.enable', {})
            driver.execute_cdp_cmd('Page.enable', {})
            driver.execute_cdp_cmd('Security.enable', {})
            
            # Set user agent override to ensure proper request headers
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            self.logger.debug("✓ Enhanced Chrome DevTools Protocol enabled with comprehensive monitoring")
            
            # Store request IDs for complete request lifecycle tracking
            pending_requests = {}
            
            def handle_request_will_be_sent(message):
                """Handle Network.requestWillBeSent events"""
                try:
                    params = message.get('params', {})
                    request = params.get('request', {})
                    url = request.get('url', '')
                    request_id = params.get('requestId', '')
                    
                    if '/api/comment/list/' in url:
                        pending_requests[request_id] = {
                            'url': url,
                            'method': request.get('method', 'GET'),
                            'headers': request.get('headers', {}),
                            'timestamp': message.get('timestamp', 0),
                            'initiator': params.get('initiator', {}),
                            'hasUserGesture': params.get('hasUserGesture', False)
                        }
                        self.logger.debug(f"CDP tracking request: {request_id} -> {url}")
                        if 'msToken' in url:
                            self.logger.debug(f"  ✓ msToken found in request URL!")
                except Exception as e:
                    self.logger.error(f"Error handling request: {e}")
            
            def handle_response_received(message):
                """Handle Network.responseReceived events"""
                try:
                    params = message.get('params', {})
                    response = params.get('response', {})
                    request_id = params.get('requestId', '')
                    final_url = response.get('url', '')
                    
                    if request_id in pending_requests and '/api/comment/list/' in final_url:
                        original_data = pending_requests[request_id]
                        self.logger.debug(f"CDP response for request {request_id}:")
                        self.logger.debug(f"  Original URL: {original_data['url']}")
                        self.logger.debug(f"  Final URL: {final_url}")
                        
                        if original_data['url'] != final_url:
                            self.logger.warning(f"  ⚠️ URL CHANGED during request!")
                            if final_url not in seen_request_urls:
                                seen_request_urls.add(final_url)
                                collected_api_urls.append(final_url)
                                self.logger.debug(f"  ✓ Added changed URL to collection")
                        
                        if 'msToken' in final_url:
                            self.logger.debug(f"  ✓ msToken found in final URL!")
                        
                        # Update the stored request with final URL
                        pending_requests[request_id]['final_url'] = final_url
                        pending_requests[request_id]['status'] = response.get('status', 0)
                        
                except Exception as e:
                    self.logger.error(f"Error handling response: {e}")
            
            # Store the handlers for later use
            driver._request_handler = handle_request_will_be_sent
            driver._response_handler = handle_response_received
            
        except Exception as e:
            self.logger.warning(f"⚠️ Could not enable CDP: {e}")
        
        # JavaScript-based request interception with real-time URL modification tracking
        monitor_script = """
        (function() {
            window.capturedCommentRequests = window.capturedCommentRequests || [];
            window.allNetworkActivity = window.allNetworkActivity || [];
            window.realTimeRequests = window.realTimeRequests || [];
            
            // Enhanced URL observer to catch dynamic modifications
            const urlObserver = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'href') {
                        const url = mutation.target.href;
                        if (url && url.includes('/api/comment/list/')) {
                            console.log('URL_MODIFIED:', url);
                            window.realTimeRequests.push({
                                type: 'url_modification',
                                url: url,
                                timestamp: Date.now()
                            });
                        }
                    }
                });
            });
            
            // Observe document for URL changes
            urlObserver.observe(document, {
                attributes: true,
                subtree: true,
                attributeFilter: ['href', 'src']
            });
            
            // Override fetch to capture complete request lifecycle
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                const originalUrl = args[0];
                const options = args[1] || {};
                
                // Capture the request
                const promise = originalFetch.apply(this, args);
                
                // Monitor the actual resolved URL
                promise.then(response => {
                    const finalUrl = response.url;
                    if (finalUrl && finalUrl.includes('/api/comment/list/')) {
                        console.log('FETCH_FINAL_URL:', finalUrl);
                        console.log('FETCH_ORIGINAL_URL:', originalUrl);
                        
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
                }).catch(error => {
                    console.log('FETCH_ERROR:', error);
                });
                
                return promise;
            };
            
            // Enhanced XMLHttpRequest override with URL tracking
            const originalXHROpen = XMLHttpRequest.prototype.open;
            const originalXHRSend = XMLHttpRequest.prototype.send;
            const originalXHRSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
            
            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                this._method = method;
                this._originalUrl = url;
                this._headers = {};
                this._requestId = Math.random().toString(36).substr(2, 9);
                
                // Track URL changes during request lifecycle
                Object.defineProperty(this, 'responseURL', {
                    get: function() {
                        const actualUrl = Object.getOwnPropertyDescriptor(XMLHttpRequest.prototype, 'responseURL').get.call(this);
                        if (actualUrl && actualUrl.includes('/api/comment/list/') && actualUrl !== this._originalUrl) {
                            console.log('XHR_URL_CHANGED:', this._originalUrl, '->', actualUrl);
                            window.realTimeRequests.push({
                                type: 'xhr_url_change',
                                originalUrl: this._originalUrl,
                                finalUrl: actualUrl,
                                requestId: this._requestId,
                                timestamp: Date.now()
                            });
                        }
                        return actualUrl;
                    }
                });
                
                if (typeof url === 'string' && url.includes('/api/comment/list/')) {
                    console.log('XHR_COMMENT_LIST OPEN:', method, url);
                    this._isCommentRequest = true;
                }
                return originalXHROpen.apply(this, [method, url, ...args]);
            };
            
            XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                if (this._isCommentRequest) {
                    this._headers[name] = value;
                    console.log('XHR_HEADER_SET:', name, value);
                }
                return originalXHRSetRequestHeader.apply(this, arguments);
            };
            
            XMLHttpRequest.prototype.send = function(body) {
                if (this._isCommentRequest) {
                    console.log('XHR_COMMENT_LIST SEND:', this._originalUrl);
                    console.log('XHR_HEADERS:', this._headers);
                    
                    // Monitor state changes to capture final URL
                    this.addEventListener('readystatechange', () => {
                        if (this.readyState === 4) { // DONE
                            const finalUrl = this.responseURL || this._originalUrl;
                            console.log('XHR_FINAL_URL:', finalUrl);
                            
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
            
            // Add a function to get real-time captured requests
            window.getRealTimeRequests = function() {
                return window.realTimeRequests.slice(); // Return copy
            };
            
            console.log('Enhanced real-time comment API monitoring active');
            return 'Monitoring /api/comment/list/ with real-time URL tracking';
        })();
        """
        
        # Inject the monitoring script
        result = driver.execute_script(monitor_script)
        self.logger.debug(f"Monitor script result: {result}")
        time.sleep(1)

        try:
            # Function to get network logs from Chrome DevTools Protocol with enhanced monitoring
            def get_cdp_network_logs():
                try:
                    # Get network logs with enhanced filtering
                    logs = driver.get_log('driver')
                    comment_requests = []
                    
                    for log in logs:
                        try:
                            message = json.loads(log['message'])
                            log_message = message.get('message', {})
                            method = log_message.get('method', '')
                            
                            # Process with our handlers
                            if method == 'Network.requestWillBeSent' and hasattr(driver, '_request_handler'):
                                driver._request_handler(log_message)
                            elif method == 'Network.responseReceived' and hasattr(driver, '_response_handler'):
                                driver._response_handler(log_message)
                            
                            # Capture both request and response events
                            if method == 'Network.requestWillBeSent':
                                params = log_message.get('params', {})
                                request = params.get('request', {})
                                url = request.get('url', '')
                                
                                if '/api/comment/list/' in url:
                                    request_info = {
                                        'type': 'cdp_request',
                                        'url': url,
                                        'method': request.get('method', 'GET'),
                                        'headers': request.get('headers', {}),
                                        'timestamp': log['timestamp'],
                                        'level': log['level'],
                                        'fullUrl': url,
                                        'requestId': params.get('requestId', ''),
                                        'initiator': params.get('initiator', {}),
                                        'postData': request.get('postData', ''),
                                        'hasUserGesture': params.get('hasUserGesture', False)
                                    }
                                    comment_requests.append(request_info)
                                    
                                    # Enhanced auth token detection
                                    if 'msToken' in url:
                                        self.logger.debug(f"CDP captured comment request with msToken: {url}")
                                    
                                    headers = request.get('headers', {})
                                    for header_name, header_value in headers.items():
                                        if 'bogus' in header_name.lower():
                                            self.logger.debug(f"  ✓ Contains X-Bogus header: {header_name}")
                                        if 'gnarly' in header_name.lower():
                                            self.logger.debug(f"  ✓ Contains X-Gnarly header: {header_name}")
                                        if 'token' in header_name.lower():
                                            self.logger.debug(f"  ✓ Contains token header: {header_name}")
                            
                            # Also capture response events to see full data flow
                            elif method == 'Network.responseReceived':
                                params = log_message.get('params', {})
                                response = params.get('response', {})
                                url = response.get('url', '')
                                request_id = params.get('requestId', '')
                                
                                if '/api/comment/list/' in url:
                                    response_info = {
                                        'type': 'cdp_response',
                                        'url': url,
                                        'status': response.get('status', 0),
                                        'statusText': response.get('statusText', ''),
                                        'headers': response.get('headers', {}),
                                        'timestamp': log['timestamp'],
                                        'requestId': request_id,
                                        'fullUrl': url
                                    }
                                    comment_requests.append(response_info)
                                    
                                    if 'msToken' in url:
                                        self.logger.debug(f"CDP captured comment response with msToken: {url}")
                        
                        except (json.JSONDecodeError, KeyError) as e:
                            continue  # Skip malformed log entries
                    
                    return comment_requests
                except Exception as e:
                    self.logger.error(f"Error getting CDP network logs: {e}")
                    return []

            # Wait for the comment section to load (similar to safe_comments)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]'))
                )
                self.logger.debug("Comment section found")
            except Exception:
                self.logger.debug("Comment section did not load, continuing anyway...")

            comment_list_xpath = '//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]'
            comment_xpath_prefix = comment_list_xpath + '/div'

            # Scroll to the end of the comment section (based on safe_comments logic)
            last_count = -1
            same_count = 0
            max_same = 5
            scroll_iteration = 0
            last_scroll_height = -1
            same_height_count = 0
            
            self.logger.info("Scrolling through comment section to capture API requests...")
            
            while True:
                # Get current scroll height of the comment section
                try:
                    comment_section = driver.find_element(By.XPATH, comment_list_xpath)
                    current_scroll_height = driver.execute_script(
                        "return arguments[0].scrollHeight;", comment_section
                    )
                except:
                    # Fallback to page scroll height
                    current_scroll_height = driver.execute_script("return document.body.scrollHeight")
                
                # Count current comments for logging
                comments = driver.find_elements(By.XPATH, comment_xpath_prefix)
                count = len(comments)
                self.logger.debug(f"Scroll iteration {scroll_iteration + 1}: Found {count} comments, scroll height: {current_scroll_height}")
                
                # Check if comment count has changed
                if count == last_count:
                    same_count += 1
                else:
                    same_count = 0
                last_count = count
                
                if current_scroll_height == last_scroll_height:
                    same_height_count += 1
                else:
                    same_height_count = 0
                last_scroll_height = current_scroll_height


                # Check for captured requests after each scroll (JavaScript)
                captured_requests = driver.execute_script("return window.capturedCommentRequests || [];")
                for req in captured_requests:
                    full_url = req.get('finalUrl', req.get('fullUrl', req.get('url', '')))
                    if full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ JS captured: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  Original URL: {req.get('originalUrl', req.get('url', 'N/A'))}")
                        self.logger.debug(f"  Final URL: {full_url}")
                        if req.get('headers'):
                            headers = req.get('headers', {})
                            if any('bogus' in str(k).lower() or 'gnarly' in str(k).lower() for k in headers.keys()):
                                self.logger.debug(f"  ✓ Auth headers found: {headers}")
                        if 'msToken' in full_url:
                            self.logger.debug(f"  ✓ Contains msToken!")
                        else:
                            self.logger.debug(f"  ⚠️ No msToken found in URL")

                # Check real-time requests (new captures during scroll)
                real_time_requests = driver.execute_script("return window.getRealTimeRequests ? window.getRealTimeRequests() : [];")
                for req in real_time_requests:
                    full_url = req.get('finalUrl', req.get('fullUrl', req.get('url', '')))
                    if full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ Real-time captured: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  URL: {full_url}")
                        if 'msToken' in full_url:
                            self.logger.debug(f"  ✓ Contains msToken in real-time capture!")

                # Check CDP network logs with buffer time
                cdp_requests = get_cdp_network_logs()
                for req in cdp_requests:
                    full_url = req.get('fullUrl', req.get('url', ''))
                    if full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ CDP captured: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  URL: {full_url}")
                        
                        # Enhanced token detection
                        if 'msToken' in full_url:
                            self.logger.debug(f"  ✓ Contains msToken in URL!")
                        if req.get('headers'):
                            headers = req.get('headers', {})
                            auth_headers = []
                            for h_name, h_value in headers.items():
                                if any(keyword in h_name.lower() for keyword in ['bogus', 'gnarly', 'token', 'auth']):
                                    auth_headers.append(f"{h_name}: {str(h_value)[:50]}...")
                            if auth_headers:
                                self.logger.debug(f"  ✓ Auth headers: {', '.join(auth_headers)}")

                # Add extra wait time after each scroll to capture delayed network events
                time.sleep(0.25)  # Additional buffer for network events
                
                # Secondary CDP check after delay
                delayed_cdp_requests = get_cdp_network_logs()
                for req in delayed_cdp_requests:
                    full_url = req.get('fullUrl', req.get('url', ''))
                    if full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ Delayed CDP captured: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  URL: {full_url}")

                # Check all browser logs for additional network information
                try:
                    browser_logs = driver.get_log('browser')
                    for log in browser_logs:
                        if '/api/comment/list/' in log.get('message', ''):
                            self.logger.debug(f"Browser log: {log['message']}")
                            # Try to extract URL from log message

                            url_match = re.search(r'https://[^\s"\']+/api/comment/list/[^\s"\']*', log['message'])
                            if url_match:
                                found_url = url_match.group(0)
                                if found_url not in seen_request_urls:
                                    seen_request_urls.add(found_url)
                                    collected_api_urls.append(found_url)
                                    self.logger.debug(f"✓ Browser log captured: {found_url}")
                                    if 'msToken' in found_url:
                                        self.logger.debug(f"  ✓ Contains msToken in browser log!")
                except Exception as e:
                    pass  # Browser logs may not always be available

                # Check performance API for any new requests
                xhr_requests = driver.execute_script("""
                    var requests = [];
                    if (window.performance && window.performance.getEntriesByType) {
                        var entries = window.performance.getEntriesByType('resource');
                        for (var i = 0; i < entries.length; i++) {
                            if (entries[i].name.includes('/api/comment/list/')) {
                                requests.push({
                                    url: entries[i].name,
                                    size: entries[i].transferSize,
                                    duration: entries[i].duration,
                                    type: entries[i].initiatorType
                                });
                            }
                        }
                    }
                    return requests;
                """)

                for request in xhr_requests:
                    if request['url'] not in seen_request_urls:
                        seen_request_urls.add(request['url'])
                        collected_api_urls.append(request['url'])
                        self.logger.debug(f"✓ Performance API captured: {request['url']}")
                        if 'msToken' in request['url']:
                            self.logger.debug(f"  ✓ Performance API URL contains msToken!")

                # Scroll down to load more comments
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(2.0)  # Increased wait time for network events to complete
                scroll_iteration += 1

                # Break if we haven't found new comments for max_same iterations
                if same_count >= max_same:
                    self.logger.info(f"✓ Reached end of comments after {scroll_iteration} scrolls")
                    break


            # Enhanced final check for any remaining requests with extended wait
            self.logger.info("Performing extended final check for API requests...")
            time.sleep(3)  # Extended wait for any delayed network events
            
            # Final JavaScript capture
            final_captured = driver.execute_script("return window.capturedCommentRequests || [];")
            for req in final_captured:
                full_url = req.get('fullUrl', req.get('url', ''))
                if full_url not in seen_request_urls:
                    seen_request_urls.add(full_url)
                    collected_api_urls.append(full_url)
                    self.logger.debug(f"✓ Final JS captured: {req.get('type', 'unknown').upper()}")
                    self.logger.debug(f"  URL: {full_url}")
                    if 'msToken' in full_url:
                        self.logger.debug(f"  ✓ Contains msToken!")
                    else:
                        self.logger.debug(f"  ⚠️ No msToken found in URL")
            
            # Final CDP capture with multiple attempts
            self.logger.info("Performing final CDP network log capture...")
            for attempt in range(3):  # Multiple attempts to catch delayed events
                time.sleep(1)  # Wait between attempts
                final_cdp_requests = get_cdp_network_logs()
                for req in final_cdp_requests:
                    full_url = req.get('fullUrl', req.get('url', ''))
                    if full_url not in seen_request_urls:
                        seen_request_urls.add(full_url)
                        collected_api_urls.append(full_url)
                        self.logger.debug(f"✓ Final CDP attempt {attempt + 1}: {req.get('type', 'unknown').upper()}")
                        self.logger.debug(f"  URL: {full_url}")
                        
                        # Enhanced authentication token analysis
                        if 'msToken' in full_url:
                            self.logger.debug(f"  ✓ Contains msToken in URL!")
                        if req.get('headers'):
                            headers = req.get('headers', {})
                            self.logger.debug(f"  Headers count: {len(headers)}")
                            for h_name, h_value in headers.items():
                                if any(keyword in h_name.lower() for keyword in ['bogus', 'gnarly', 'token', 'auth', 'x-']):
                                    self.logger.debug(f"    ✓ Auth header: {h_name} = {str(h_value)[:100]}...")
            
            # Clear browser logs to see fresh data in next run
            try:
                #driver.get_log('performance')  # This clears the log
                self.logger.debug("Cleared performance logs for next run")
            except Exception as e:
                self.logger.debug(f"Could not clear logs: {e}")
            
            # Process all collected API URLs using new tabs after collection is complete
            self.logger.info(f"\n=== PROCESSING COLLECTED API URLS ===")
            unique_urls = list(set(collected_api_urls))  # Remove duplicates for processing
            self.logger.info(f"Found {len(collected_api_urls)} total URLs ({len(unique_urls)} unique) to process")
            
            all_responses_data = []  # Store all responses for JSON file
            
            # Process each URL directly without using new tabs  
            self.logger.info(f"Processing {len(unique_urls)} unique API URLs...")
            for i, api_url in enumerate(unique_urls, 1):
                self.logger.debug(f"\nProcessing API URL {i}/{len(unique_urls)}")
                self.logger.debug(f"URL: {api_url}")
                
                try:
                    # Navigate directly to the API URL
                    self.logger.debug(f"  Navigating to URL...")
                    driver.get(api_url)
                    time.sleep(2)  # Wait for page to load
                    
                    # Extract JSON using the specific XPATH
                    try:
                        # Use the XPATH to extract the JSON content from <pre> tag
                        json_element = driver.find_element(By.XPATH, '/html/body/pre')
                        json_text = json_element.text
                        
                        # Parse the JSON
                        parsed_json = json.loads(json_text)
                        
                        # Store just the API content
                        comment_responses.append(parsed_json)
                        all_responses_data.append({
                            'url': api_url,
                            'json_data': parsed_json,
                            'timestamp': int(time.time() * 1000),
                            'processing_order': i
                        })
                        
                        self.logger.debug(f"✓ Successfully extracted JSON from {api_url}")
                        self.logger.debug(f"  JSON contains {len(json_text)} characters")
                        
                        # Check if this response contains comments
                        if 'comments' in parsed_json:
                            comment_count = len(parsed_json.get('comments', []))
                            self.logger.debug(f"  Found {comment_count} comments in this response")
                        elif 'comment_list' in parsed_json:
                            comment_count = len(parsed_json.get('comment_list', []))
                            self.logger.debug(f"  Found {comment_count} comments in this response")
                        else:
                            self.logger.debug(f"  Response structure: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else 'Non-dict response'}")
                            
                    except Exception as e:
                        self.logger.error(f"✗ Error extracting JSON from XPATH for {api_url}: {e}")
                        # Create error entry
                        error_response = {
                            'url': api_url,
                            'error': str(e),
                            'timestamp': int(time.time() * 1000),
                            'processing_order': i
                        }
                        all_responses_data.append(error_response)
                    
                    # Small delay between requests to avoid rate limiting
                    time.sleep(1)
                        
                except Exception as e:
                    self.logger.error(f"✗ Error processing {api_url}: {e}")
                    error_response = {
                        'url': api_url,
                        'error': str(e),
                        'timestamp': int(time.time() * 1000),
                        'processing_order': i
                    }
                    all_responses_data.append(error_response)
                            
            
            # Save all collected responses to files after processing all URLs
            self.logger.info(f"\n=== SAVING COLLECTED RESPONSES ===")
            
            # Save consolidated JSON file with all responses
            consolidated_filename = f"all_api_responses_{self.id}.json"
            with open(consolidated_filename, "w", encoding="utf-8") as f:
                json.dump(all_responses_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"✓ Saved all {len(all_responses_data)} API responses to {consolidated_filename}")
            
            # Save individual response files for backup
            for i, response_data in enumerate(all_responses_data, 1):
                if 'json_data' in response_data:  # Only save successful JSON responses
                    individual_filename = f"api_response_{i}_{self.id}.json"
                    with open(individual_filename, "w", encoding="utf-8") as f:
                        json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            # Count successful vs failed responses
            successful_responses = sum(1 for r in all_responses_data if 'json_data' in r)
            failed_responses = len(all_responses_data) - successful_responses
            
            self.logger.info(f"✓ Processing summary:")
            self.logger.info(f"  - Successful responses: {successful_responses}")
            self.logger.info(f"  - Failed responses: {failed_responses}")
            self.logger.info(f"  - Total URLs processed: {len(unique_urls)}")
            
            # Save all API responses to JSON file
            responses_filename = f"api_responses_{self.id}.json"
            with open(responses_filename, "w", encoding="utf-8") as f:
                json.dump(all_responses_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"\nSaved all API responses to {responses_filename}")
            
            # Save debug data with enhanced request information
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
                "detailed_requests": [
                    {
                        "url": req.get('fullUrl', req.get('url', '')),
                        "type": req.get('type', 'unknown'),
                        "method": req.get('method', 'unknown'),
                        "headers": req.get('headers', {}),
                        "has_msToken": 'msToken' in req.get('fullUrl', req.get('url', '')),
                        "timestamp": req.get('timestamp', 0)
                    }
                    for req in final_captured
                ]
            }
            
            debug_filename = f"comment_list_requests_{self.id}.json"
            with open(debug_filename, "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved debug data to {debug_filename}")
            
            # Show captured URLs summary
            if collected_api_urls:
                self.logger.info(f"\nCaptured /api/comment/list/ URLs ({len(collected_api_urls)} total, {len(unique_urls)} unique):")
                urls_with_mstoken = 0
                for i, url in enumerate(unique_urls, 1):
                    has_mstoken = 'msToken' in url
                    if has_mstoken:
                        urls_with_mstoken += 1
                    mstoken_indicator = " ✓ msToken" if has_mstoken else " ⚠️ No msToken"
                    self.logger.info(f"  {i}. {url[:100]}...{mstoken_indicator}")
                
                self.logger.info(f"\nSummary: {urls_with_mstoken}/{len(unique_urls)} URLs contain msToken")
                
                if urls_with_mstoken == 0:
                    self.logger.info("\n⚠️ WARNING: No URLs contain msToken!")
                    self.logger.info("This could mean:")
                    self.logger.info("- msToken is added after the initial request")
                    self.logger.info("- msToken is sent as a header instead of URL parameter")
                    self.logger.info("- TikTok is using a different authentication method")
                    self.logger.info("- The requests are being modified after capture")
                else:
                    self.logger.info(f"\n✓ SUCCESS: Found {urls_with_mstoken} URLs with authentication tokens!")
            else:
                self.logger.info("⚠️  No /api/comment/list/ requests found!")

        except Exception as e:
            self.logger.info(f"Error during network capture: {e}")
            traceback.print_exc()

        self.logger.info(f"\nCaptured {len(comment_responses)} comment response objects")
        # Delete API response files with pattern api_response_ID_VideoID.json

        self.logger.info("\n=== CLEANING UP API RESPONSE FILES ===")
        pattern = f"api_response_*_{self.id}.json"
        files_to_delete = glob.glob(pattern)
        
        # Also check for files in current directory with more flexible pattern
        if not files_to_delete:
            # Try different patterns that might exist
            patterns = [
            f"api_response_*_{self.id}.json",
            f"api_response_*{self.id}.json", 
            f"*api_response*{self.id}*.json"
            ]
            for pattern in patterns:
                found_files = glob.glob(pattern)
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
            self.logger.info(f"✓ Cleanup complete - deleted {len(files_to_delete)} files")
        else:
            self.logger.info("No API response files found to delete")
            
        return comment_responses

    def read_all_api_responses(self, **kwargs) -> list[dict]:
        """
        Read all saved API responses and extract comprehensive comment data.
        
        Returns:
            list: List of all comments with complete data from API responses
        """
        # Clean video ID to remove invalid filename characters
        clean_id = str(self.id).replace('?', '_').replace(':', '_').replace('<', '_').replace('>', '_').replace('|', '_').replace('"', '_').replace('*', '_').replace('/', '_').replace('\\', '_')
        consolidated_filename = f"all_api_responses_{clean_id}.json"
        
        try:
            # Read the consolidated API responses file
            with open(consolidated_filename, "r", encoding="utf-8") as f:
                api_responses = json.load(f)
            
            self.logger.info(f"✓ Loaded {len(api_responses)} API responses from {consolidated_filename}")
            
            all_comments = []
            total_comments_found = 0
            
            # Process each API response
            for response_idx, response_data in enumerate(api_responses):
                self.logger.info(f"\nProcessing API response {response_idx + 1}/{len(api_responses)}")
                
                # Skip responses that don't have json_data
                if 'json_data' not in response_data:
                    self.logger.info(f"  Skipping response {response_idx + 1}: No JSON data")
                    continue
                
                json_data = response_data['json_data']
                response_url = response_data.get('url', 'Unknown URL')
                
                # Look for comments in various possible keys
                comments = []
                if 'comments' in json_data:
                    comments = json_data['comments']
                    self.logger.info(f"  Found {len(comments)} comments in 'comments' key")
                elif 'comment_list' in json_data:
                    comments = json_data['comment_list']
                    self.logger.info(f"  Found {len(comments)} comments in 'comment_list' key")
                elif 'data' in json_data and isinstance(json_data['data'], list):
                    comments = json_data['data']
                    self.logger.info(f"  Found {len(comments)} comments in 'data' key")
                else:
                    self.logger.info(f"  No comments found in response {response_idx + 1}")
                    self.logger.info(f"  Available keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Non-dict response'}")
                    continue
                
                # Process each comment
                for comment_idx, comment_data in enumerate(comments):
                    try:
                        # Extract comprehensive comment details
                        detailed_comment = self.extract_comment_details(comment_data)
                        
                        # Add metadata about the source
                        detailed_comment.update({
                            'source_response_index': response_idx,
                            'source_comment_index': comment_idx,
                            'source_url': response_url,
                            'source_timestamp': response_data.get('timestamp', 0),
                            'processing_order': response_data.get('processing_order', response_idx + 1)
                        })
                        
                        all_comments.append(detailed_comment)
                        total_comments_found += 1
                        
                    except Exception as e:
                        self.logger.info(f"  Error processing comment {comment_idx + 1} in response {response_idx + 1}: {e}")
                        # Still add the raw comment with error info
                        error_comment = {
                            'error': str(e),
                            'raw_comment_data': comment_data,
                            'source_response_index': response_idx,
                            'source_comment_index': comment_idx,
                            'source_url': response_url
                        }
                        all_comments.append(error_comment)
                        total_comments_found += 1
            
            self.logger.info(f"\n✓ Successfully processed {total_comments_found} total comments from {len(api_responses)} API responses")
            
            # Save all extracted comments to a detailed file
            if all_comments:
                detailed_filename = f"all_comments_extracted_{self.id}.json"
                with open(detailed_filename, "w", encoding="utf-8") as f:
                    json.dump(all_comments, f, indent=2, ensure_ascii=False)
                self.logger.info(f"✓ Saved {len(all_comments)} detailed comments to {detailed_filename}")
                
                # Create a summary
                successful_comments = sum(1 for c in all_comments if 'error' not in c)
                failed_comments = len(all_comments) - successful_comments
                
                self.logger.info(f"\nComment extraction summary:")
                self.logger.info(f"  - Total comments: {len(all_comments)}")
                self.logger.info(f"  - Successfully parsed: {successful_comments}")
                self.logger.info(f"  - Parse errors: {failed_comments}")
                
                # Show sample comments
                self.logger.info(f"\nSample comments (first 3):")
                for i, comment in enumerate(all_comments[:3]):
                    if 'error' not in comment:
                        username = comment.get('username', 'Unknown')
                        text = comment.get('text', '')[:100] + '...' if len(comment.get('text', '')) > 100 else comment.get('text', '')
                        likes = comment.get('digg_count', 0)
                        self.logger.info(f"  {i+1}. @{username}: {text} ({likes} likes)")
                    else:
                        self.logger.info(f"  {i+1}. [Error parsing comment]: {comment.get('error', 'Unknown error')}")
            
            return all_comments
            
        except FileNotFoundError:
            self.logger.info(f"✗ API responses file not found: {consolidated_filename}")
            self.logger.info("Please run fetch_comments_from_network() first to collect API responses.")
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
        
        Returns:
            dict: Organized comments with replies nested under parent comments
        """
        all_comments = self.read_all_api_responses(**kwargs)
        
        if not all_comments:
            return {'comments': [], 'total': 0, 'organized': False}
        
        # Organize comments by parent/reply relationship
        comment_tree = {}
        top_level_comments = []
        
        for comment in all_comments:
            if 'error' in comment:
                continue
                
            comment_id = comment.get('comment_id')
            reply_id = comment.get('reply_id', '0')
            
            # Add replies list to comment
            comment['replies'] = []
            
            if reply_id == '0':
                # This is a top-level comment
                top_level_comments.append(comment)
                comment_tree[comment_id] = comment
            else:
                # This is a reply to another comment
                if reply_id in comment_tree:
                    comment_tree[reply_id]['replies'].append(comment)
                else:
                    # Parent comment not found, add to orphaned replies
                    if 'orphaned_replies' not in comment_tree:
                        comment_tree['orphaned_replies'] = []
                    comment_tree['orphaned_replies'].append(comment)
        
        # Sort top-level comments by creation time (newest first)
        top_level_comments.sort(key=lambda x: x.get('create_time', 0), reverse=True)
        
        # Sort replies within each comment
        for comment in top_level_comments:
            if comment['replies']:
                comment['replies'].sort(key=lambda x: x.get('create_time', 0))
        
        result = {
            'comments': top_level_comments,
            'total_comments': len(top_level_comments),
            'total_replies': sum(len(c['replies']) for c in top_level_comments),
            'total_all': len(all_comments),
            'organized': True,
            'orphaned_replies': comment_tree.get('orphaned_replies', [])
        }
        
        # Save organized comments
        organized_filename = f"comments_organized_{self.id}.json"
        with open(organized_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        self.logger.info(f"✓ Saved organized comments to {organized_filename}")
        
        self.logger.info(f"\nComment organization summary:")
        self.logger.info(f"  - Top-level comments: {result['total_comments']}")
        self.logger.info(f"  - Total replies: {result['total_replies']}")
        self.logger.info(f"  - Orphaned replies: {len(result['orphaned_replies'])}")
        self.logger.info(f"  - Total processed: {result['total_all']}")
        
        return result

    def extract_comment_details(self, comment_data: dict) -> dict:
        """
        Extract comprehensive comment details from TikTok API response.
        
        Args:
            comment_data: Single comment object from TikTok API
            
        Returns:
            dict: Comprehensive comment information
        """
        try:
            # Basic comment info
            comment_details = {
                'comment_id': comment_data.get('cid'),
                'text': comment_data.get('text', ''),
                'create_time': comment_data.get('create_time'),
                'digg_count': comment_data.get('digg_count', 0),  # likes
                'reply_comment_total': comment_data.get('reply_comment_total', 0),  # replies
                'is_author_digged': comment_data.get('is_author_digged', False),  # liked by video author
                'user_digged': comment_data.get('user_digged', 0),  # liked by current user
                'aweme_id': comment_data.get('aweme_id'),  # video ID
                'reply_id': comment_data.get('reply_id', '0'),  # parent comment ID if this is a reply
                'reply_to_reply_id': comment_data.get('reply_to_reply_id', '0'),  # nested reply ID
                'status': comment_data.get('status', 1),  # comment status
                'stick_position': comment_data.get('stick_position', 0),  # pinned comment
            }
            
            # User information
            user_info = comment_data.get('user', {})
            if user_info:
                comment_details.update({
                    'user_id': user_info.get('uid'),
                    'sec_uid': user_info.get('sec_uid'),
                    'username': user_info.get('unique_id'),
                    'nickname': user_info.get('nickname'),
                    'avatar_thumb': user_info.get('avatar_thumb', {}).get('url_list', []),
                    'avatar_medium': user_info.get('avatar_medium', {}).get('url_list', []),
                    'avatar_larger': user_info.get('avatar_larger', {}).get('url_list', []),
                    'signature': user_info.get('signature', ''),
                    'create_time_user': user_info.get('create_time'),
                    'verification_type': user_info.get('verification_type', 0),
                    'custom_verify': user_info.get('custom_verify', ''),
                    'unique_id_modify_time': user_info.get('unique_id_modify_time'),
                    'comment_setting': user_info.get('comment_setting', 0),
                    'commerce_user_level': user_info.get('commerce_user_level', 0),
                    'live_verify': user_info.get('live_verify', 0),
                    'authority_status': user_info.get('authority_status', 0),
                    'verified': user_info.get('verified', False),
                    'user_canceled': user_info.get('user_canceled', False),
                    'user_buried': user_info.get('user_buried', False),
                    'user_rate': user_info.get('user_rate', 0),
                })
            
            # Format timestamps
            if comment_details['create_time']:
                try:
                    comment_details['create_time_formatted'] = datetime.fromtimestamp(
                        int(comment_details['create_time'])
                    ).strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    comment_details['create_time_formatted'] = None
            
            # Additional fields that might be present
            optional_fields = [
                'label_list', 'reply_comment', 'no_show', 'trans_btn_style',
                'comment_language', 'text_extra', 'share_info', 'reply_comment_status',
                'comment_struct_v2', 'item_id', 'reply_style'
            ]
            
            for field in optional_fields:
                if field in comment_data:
                    comment_details[field] = comment_data[field]
            
            return comment_details
            
        except Exception as e:
            self.logger.info(f"Error extracting comment details: {e}")
            return {
                'error': str(e),
                'raw_data': comment_data
            }








    def safe_comments(self, **kwargs) -> Iterator[dict]:
        """
        Fetch comments and their replies by scraping the TikTok video page while logged in.

        This method scrolls to the end of the comment section, extracts comments, clicks the "Replies" button
        for each comment (if present), and extracts replies, associating them with their parent comment.

        Args:
            driver: Selenium WebDriver instance (required)

        Yields:
            dict: Extracted data for each comment, with replies as a list under 'replies'
        """

        driver = kwargs.get('driver', self.driver)
        if driver is None:
            raise TypeError("A Selenium WebDriver instance is required.")

        if not self.url:
            raise ValueError("Video URL is not set.")

        time.sleep(3)

        # Wait for the comment section to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]'))
            )
            self.logger.debug("Comment section found")
        except Exception:
            self.logger.debug("Comment section did not load, continuing anyway...")

        comment_list_xpath = '//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]'
        comment_xpath_prefix = comment_list_xpath + '/div'

        # Scroll to the end of the comment section (based on safe_comments logic)
        last_count = -1
        same_count = 0
        max_same = 5
        scroll_iteration = 0
        last_scroll_height = -1
        same_height_count = 0
        
        self.logger.info("Scrolling through comment section to capture API requests...")
        
        while True:
            # Get current scroll height of the comment section
            try:
                comment_section = driver.find_element(By.XPATH, comment_list_xpath)
                current_scroll_height = driver.execute_script(
                    "return arguments[0].scrollHeight;", comment_section
                )
            except:
                # Fallback to page scroll height
                current_scroll_height = driver.execute_script("return document.body.scrollHeight")
            
            # Count current comments for logging
            comments = driver.find_elements(By.XPATH, comment_xpath_prefix)
            count = len(comments)
            self.logger.debug(f"Scroll iteration {scroll_iteration + 1}: Found {count} comments, scroll height: {current_scroll_height}")
            
            # Check if comment count has changed
            if count == last_count:
                same_count += 1
            else:
                same_count = 0
            last_count = count
            
            if current_scroll_height == last_scroll_height:
                same_height_count += 1
            else:
                same_height_count = 0
            last_scroll_height = current_scroll_height

            # Scroll down to load more comments
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2.0)
            scroll_iteration += 1

            # Break if we haven't found new comments for max_same iterations
            if same_count >= max_same:
                self.logger.info(f"✓ Reached end of comments after {scroll_iteration} scrolls")
                break

        # Extract all comment elements
        comments = driver.find_elements(By.XPATH, comment_xpath_prefix)
        self.logger.info(f"Found {len(comments)} comments.")

        for idx, comment_el in enumerate(comments, start=1):
            try:
                data = {}

                # Username
                try:
                    username_el = comment_el.find_element(By.XPATH, f'.//a/p')
                    data['username'] = username_el.text.strip()
                except Exception:
                    data['username'] = None

                # User profile URL
                try:
                    nickname_el = comment_el.find_element(By.CLASS_NAME, 'link-a11y-focus')
                    data['user_profile_url'] = nickname_el.get_attribute('href')
                except Exception:
                    data['user_profile_url'] = None

                # User avatar
                try:
                    avatar_el = comment_el.find_element(By.CLASS_NAME, 'css-1zpj2q-ImgAvatar.e1e9er4e1')
                    data['avatar_url'] = avatar_el.get_attribute('src')
                except Exception:
                    data['avatar_url'] = None

                # Comment text
                try:
                    text_el = comment_el.find_element(By.XPATH, f'.//span/span')
                    data['text'] = text_el.get_attribute('innerText').strip()
                except Exception:
                    data['text'] = None

                # Comment time
                try:
                    time_el = comment_el.find_element(By.CLASS_NAME, 'TUXText.TUXText--tiktok-sans.TUXText--weight-normal')
                    data['time'] = time_el.text.strip()
                    data['time_now'] = date.today().strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    data['time'] = None

                # Like count
                try:
                    like_el = comment_el.find_element(By.XPATH, f'.//div[2]/div[2]/span')
                    data['like_count'] = like_el.text.strip()
                except Exception:
                    data['like_count'] = None

                # Get the username of the initial commentor (parent comment) BEFORE processing replies
                parent_username = data.get('username')

                # Reply count and replies
                replies = []
                try:
                    reply_btn_xpath = f'//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]/div[{idx}]/div[2]/div/div[2]/span'
                    reply_btn = driver.find_element(By.XPATH, reply_btn_xpath)
                    reply_text = reply_btn.text.strip()
                    match = re.search(r'\d+', reply_text)
                    data['reply_count'] = int(match.group()) if match else 0

                    if data['reply_count'] and "View" in reply_text:
                        # Click to expand replies
                        driver.execute_script("arguments[0].scrollIntoView();", reply_btn)
                        time.sleep(0.5)
                        try:
                            reply_btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", reply_btn)
                        time.sleep(1.5)

                        # After clicking, replies should appear under this comment
                        # Find all reply elements under this comment
                        # Based on the XPATHs provided, replies start from div[2] and go sequentially
                        replies_found = 0
                        reply_index = 2  # Start from div[2] as that's where replies begin
                        
                        while replies_found < data['reply_count']:
                            try:
                                # Try to find the reply element at the current index
                                reply_xpath = f'//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]/div[{idx}]/div[2]/div[{reply_index}]'
                                reply_el = driver.find_element(By.XPATH, reply_xpath)
                                
                                reply_data = {}
                                try:
                                    # Username
                                    try:
                                        reply_username_el = reply_el.find_element(By.XPATH, f'//*[@id="main-content-video_detail"]/div/div[2]/div[1]/div[2]/div[2]/div[{idx}]/div[2]/div[{reply_index}]/div[2]/div[1]/div[1]/div/a/p')
                                        reply_data['username'] = reply_username_el.text.strip()
                                    except Exception:
                                        reply_data['username'] = None

                                    # User profile URL
                                    try:
                                        reply_profile_el = reply_el.find_element(By.XPATH, './/a[contains(@class, "link-a11y-focus")]')
                                        reply_data['user_profile_url'] = reply_profile_el.get_attribute('href')
                                    except Exception:
                                        reply_data['user_profile_url'] = None

                                    # User avatar
                                    try:
                                        reply_avatar_el = reply_el.find_element(By.CLASS_NAME, 'css-1zpj2q-ImgAvatar.e1e9er4e1')
                                        reply_data['avatar_url'] = reply_avatar_el.get_attribute('src')
                                    except Exception:
                                        reply_data['avatar_url'] = None

                                    # Reply text
                                    try:
                                        reply_text_el = reply_el.find_element(By.XPATH, './/span/span')
                                        reply_data['text'] = reply_text_el.get_attribute('innerText').strip()
                                    except Exception:
                                        reply_data['text'] = None

                                    # Reply time
                                    try:
                                        reply_time_el = reply_el.find_element(By.CLASS_NAME, 'TUXText.TUXText--tiktok-sans.TUXText--weight-normal')
                                        reply_data['time'] = reply_time_el.text.strip()
                                    except Exception:
                                        reply_data['time'] = None

                                    # Like count
                                    try:
                                        reply_like_el = reply_el.find_element(By.XPATH, './/div[2]/div[2]/span')
                                        reply_data['like_count'] = reply_like_el.text.strip()
                                    except Exception:
                                        reply_data['like_count'] = None

                                    # Comment ID (if available)
                                    try:
                                        reply_data['comment_id'] = reply_el.get_attribute('data-id')
                                    except Exception:
                                        reply_data['comment_id'] = None

                                    # Any badges
                                    try:
                                        badge_els = reply_el.find_elements(By.XPATH, './/span[contains(@class, "badge")]')
                                        reply_data['badges'] = [b.text.strip() for b in badge_els if b.text.strip()]
                                    except Exception:
                                        reply_data['badges'] = []

                                    # Add replied_to field with the parent commentor's username
                                    reply_data['replied_to'] = parent_username

                                    # Try to extract the username being replied to (if present in the reply text)
                                    reply_text = reply_data.get('text')
                                    if reply_text and isinstance(reply_text, str):
                                        match = re.match(r'@(\w+)', reply_text)
                                        if match:
                                            reply_data['reply_to_username'] = match.group(1)
                                        else:
                                            reply_data['reply_to_username'] = parent_username
                                    else:
                                        reply_data['reply_to_username'] = parent_username

                                    reply_data['raw_html'] = reply_el.get_attribute('outerHTML')
                                    
                                    # Only add reply if it has meaningful content
                                    if reply_data.get('username') or reply_data.get('text'):
                                        replies.append(reply_data)
                                        replies_found += 1
                                    
                                except Exception as e:
                                    reply_data['error'] = f"Error extracting reply: {e}"
                                    reply_data['reply_index'] = reply_index
                                    replies.append(reply_data)
                                    replies_found += 1
                                
                                reply_index += 1
                                
                            except Exception:
                                # No more reply elements found at this index
                                reply_index += 1
                                # If we've tried too many indices beyond expected, break
                                if reply_index > data['reply_count'] + 5:
                                    break
                                continue
                        
                except Exception:
                    data['reply_count'] = 0

                # Comment ID (if available)
                try:
                    data['comment_id'] = comment_el.get_attribute('data-id')
                except Exception:
                    data['comment_id'] = None

                # Any badges (e.g., verified, creator)
                try:
                    badge_els = comment_el.find_elements(By.XPATH, './/span[contains(@class, "badge")]')
                    data['badges'] = [b.text.strip() for b in badge_els if b.text.strip()]
                except Exception:
                    data['badges'] = []

                # Raw HTML (optional, for debugging)
                data['raw_html'] = comment_el.get_attribute('outerHTML')

                # Attach replies to this comment
                data['replies'] = replies

                yield data
            except Exception as e:
                self.logger.info(f"Error extracting comment {idx}: {e}")
                continue



    def related_videos(
        self, count: int = 30, cursor: int = 0, **kwargs
    ) -> Iterator[Video]:
        """
        Returns related videos of a TikTok Video.

        Parameters:
            count (int): The amount of related videos you want returned.
            cursor (int): The the offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.

        Example Usage
        .. code-block:: python

            for related_video in video.related_videos():
                # do something
        """
        found = 0
        while found < count:
            params = {
                "itemID": self.id,
                "count": min(16, count - found),
            }

            # Use make_request from parent API
            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                try:
                    resp = self.parent.make_request(
                        url="https://www.tiktok.com/api/related/item_list/",
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
                        
                    # No pagination info typically provided for related videos
                    break
                    
                except Exception as e:
                    self.logger.info(f"Error fetching related videos: {e}")
                    break
            else:
                # Fallback implementation
                break

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"Video(id='{getattr(self, 'id', None)}')"


# Example usage function
def create_video_from_url(url: str, driver, **kwargs) -> Video:
    """
    Helper function to create a Video instance from a URL using Selenium.
    
    Args:
        url (str): TikTok video URL
        driver: Selenium WebDriver instance
        **kwargs: Additional arguments
        
    Returns:
        Video: Initialized Video instance
    """
    video = Video(url=url, driver=driver, **kwargs)
    video.info(driver=driver)
    return video


def create_video_from_id(video_id: str, driver, **kwargs) -> Video:
    """
    Helper function to create a Video instance from an ID using Selenium.
    
    Args:
        video_id (str): TikTok video ID
        driver: Selenium WebDriver instance
        **kwargs: Additional arguments
        
    Returns:
        Video: Initialized Video instance
    """
    video = Video(id=video_id, driver=driver, **kwargs)
    return video
