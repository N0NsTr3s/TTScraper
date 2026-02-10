"""
Enhanced network monitoring and request interception for TikTok scraping (nodriver-based).
"""
import json
import time
import logging
import asyncio
from typing import Dict, List, Optional, Callable, Any

import nodriver as uc
import nodriver.cdp.network as cdp_net


class NetworkMonitor:
    """
    Centralized network monitoring for TikTok API requests.

    Uses nodriver's native CDP support for monitoring, JavaScript injection,
    and request/response capture with proper authentication token handling.
    """

    def __init__(self, tab: uc.Tab, config=None, rate_limiter=None):
        self.tab = tab
        self.config = config
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(f"TTScraper.{self.__class__.__name__}")

        # Storage for captured requests
        self.captured_requests: List[Dict[str, Any]] = []
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.seen_urls: set = set()

        # Event handlers
        self.request_handlers: List[Callable] = []
        self.response_handlers: List[Callable] = []

        # URL patterns to monitor
        self.patterns: List[str] = []

    async def enable_monitoring(self, patterns: Optional[List[str]] = None) -> None:
        """
        Enable comprehensive network monitoring.

        Args:
            patterns: URL patterns to monitor (default: ['/api/comment/list/'])
        """
        if patterns is None:
            patterns = ["/api/comment/list/"]

        self.patterns = patterns

        # Enable CDP network domain
        await self._enable_cdp()

        # Inject JavaScript monitoring
        await self._inject_monitoring_script()

        self.logger.info(f"Network monitoring enabled for patterns: {patterns}")

    async def _enable_cdp(self) -> None:
        """Enable Chrome DevTools Protocol monitoring via nodriver."""
        try:
            await self.tab.send(
                cdp_net.enable(
                    max_total_buffer_size=10_000_000,    # 10 MB
                    max_resource_buffer_size=5_000_000,  # 5 MB
                    max_post_data_size=65536,             # 64 KB
                )
            )
            import nodriver.cdp.runtime as runtime
            await self.tab.send(runtime.enable())
            self.logger.debug("CDP network monitoring enabled")
        except Exception as e:
            self.logger.warning(f"Could not enable CDP: {e}")

    async def _inject_monitoring_script(self) -> None:
        """Inject JavaScript for request monitoring."""
        script = """
        (function() {
            // Initialize storage
            window.ttScraperRequests = window.ttScraperRequests || [];
            window.ttScraperRealTime = window.ttScraperRealTime || [];

            const patterns = %s;

            // Enhanced fetch override
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                const originalUrl = args[0];
                const options = args[1] || {};

                const promise = originalFetch.apply(this, args);

                // Check if URL matches our patterns
                const shouldCapture = patterns.some(pattern => originalUrl.includes(pattern));

                if (shouldCapture) {
                    promise.then(response => {
                        const requestData = {
                            type: 'fetch',
                            originalUrl: originalUrl,
                            finalUrl: response.url,
                            method: options.method || 'GET',
                            headers: options.headers || {},
                            status: response.status,
                            timestamp: Date.now(),
                            redirected: response.redirected
                        };

                        window.ttScraperRequests.push(requestData);
                        window.ttScraperRealTime.push(requestData);

                        console.log('TTScraper captured fetch:', requestData.finalUrl);
                    }).catch(error => {
                        console.log('TTScraper fetch error:', error);
                    });
                }

                return promise;
            };

            // Enhanced XMLHttpRequest override
            const originalXHROpen = XMLHttpRequest.prototype.open;
            const originalXHRSend = XMLHttpRequest.prototype.send;

            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                this._ttScraperMethod = method;
                this._ttScraperUrl = url;
                this._ttScraperHeaders = {};
                this._ttScraperRequestId = Math.random().toString(36).substr(2, 9);

                const shouldCapture = patterns.some(pattern => url.includes(pattern));
                this._ttScraperShouldCapture = shouldCapture;

                if (shouldCapture) {
                    console.log('TTScraper XHR open:', method, url);
                }

                return originalXHROpen.apply(this, [method, url, ...args]);
            };

            XMLHttpRequest.prototype.send = function(body) {
                if (this._ttScraperShouldCapture) {
                    this.addEventListener('readystatechange', () => {
                        if (this.readyState === 4) {
                            const requestData = {
                                type: 'xhr',
                                originalUrl: this._ttScraperUrl,
                                finalUrl: this.responseURL || this._ttScraperUrl,
                                method: this._ttScraperMethod,
                                headers: this._ttScraperHeaders,
                                status: this.status,
                                timestamp: Date.now(),
                                requestId: this._ttScraperRequestId
                            };

                            window.ttScraperRequests.push(requestData);
                            window.ttScraperRealTime.push(requestData);

                            console.log('TTScraper captured XHR:', requestData.finalUrl);
                        }
                    });
                }

                return originalXHRSend.apply(this, arguments);
            };

            // Helper functions
            window.getTTScraperRequests = function() {
                return window.ttScraperRequests.slice();
            };

            window.getTTScraperRealTime = function() {
                const requests = window.ttScraperRealTime.slice();
                window.ttScraperRealTime = []; // Clear after reading
                return requests;
            };

            window.clearTTScraperRequests = function() {
                window.ttScraperRequests = [];
                window.ttScraperRealTime = [];
            };

            console.log('TTScraper network monitoring active for patterns:', patterns);
            return true;
        })();
        """ % json.dumps(self.patterns)

        try:
            result = await self.tab.evaluate(script)
            self.logger.debug(f"Monitoring script injected: {result}")
        except Exception as e:
            self.logger.error(f"Failed to inject monitoring script: {e}")

    async def get_captured_requests(self, clear_after_read: bool = False) -> List[Dict[str, Any]]:
        """Get all captured requests from JavaScript monitoring."""
        try:
            requests = await self.tab.evaluate(
                "window.getTTScraperRequests ? window.getTTScraperRequests() : []"
            )

            if clear_after_read:
                await self.tab.evaluate(
                    "window.clearTTScraperRequests ? window.clearTTScraperRequests() : null;"
                )

            return requests or []
        except Exception as e:
            self.logger.error(f"Error getting captured requests: {e}")
            return []

    async def get_real_time_requests(self) -> List[Dict[str, Any]]:
        """Get new requests since last call (clears buffer automatically)."""
        try:
            result = await self.tab.evaluate(
                "window.getTTScraperRealTime ? window.getTTScraperRealTime() : []"
            )
            return result or []
        except Exception as e:
            self.logger.error(f"Error getting real-time requests: {e}")
            return []

    async def get_all_requests(self) -> List[Dict[str, Any]]:
        """Get all requests from all monitoring sources."""
        all_requests: List[Dict[str, Any]] = []

        # Get JavaScript-captured requests
        js_requests = await self.get_captured_requests()
        all_requests.extend(js_requests)

        # Remove duplicates based on URL and timestamp
        seen: set = set()
        unique_requests: List[Dict[str, Any]] = []

        for req in all_requests:
            key = (req.get("finalUrl", req.get("url", "")), req.get("timestamp", 0))
            if key not in seen:
                seen.add(key)
                unique_requests.append(req)

        return unique_requests

    async def wait_for_requests(
        self, timeout: float = 5.0, check_interval: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Wait for new requests to be captured.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check for new requests

        Returns:
            List of new requests found during the wait period
        """
        start_time = time.time()
        initial_count = len(await self.get_captured_requests())

        while time.time() - start_time < timeout:
            current_requests = await self.get_captured_requests()
            if len(current_requests) > initial_count:
                return current_requests[initial_count:]

            await asyncio.sleep(check_interval)

        return []

    async def clear_all_requests(self) -> None:
        """Clear all captured request data."""
        try:
            await self.tab.evaluate(
                "window.clearTTScraperRequests ? window.clearTTScraperRequests() : null;"
            )
            self.captured_requests.clear()
            self.pending_requests.clear()
            self.seen_urls.clear()
            self.logger.debug("All request data cleared")
        except Exception as e:
            self.logger.error(f"Error clearing requests: {e}")
