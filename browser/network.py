"""
Enhanced network monitoring and request interception for TikTok scraping
"""
import json
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from selenium.webdriver.chrome.webdriver import WebDriver


class NetworkMonitor:
    """
    Centralized network monitoring for TikTok API requests.
    
    Handles Chrome DevTools Protocol (CDP) monitoring, JavaScript injection,
    and request/response capture with proper authentication token handling.
    """
    
    def __init__(self, driver: WebDriver, config=None, rate_limiter=None):
        self.driver = driver
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
        
    def enable_monitoring(self, patterns: Optional[List[str]] = None):
        """
        Enable comprehensive network monitoring.
        
        Args:
            patterns: URL patterns to monitor (default: ['/api/comment/list/'])
        """
        if patterns is None:
            patterns = ['/api/comment/list/']
        
        self.patterns = patterns
        
        # Enable CDP
        self._enable_cdp()
        
        # Inject JavaScript monitoring
        self._inject_monitoring_script()
        
        self.logger.info(f"Network monitoring enabled for patterns: {patterns}")
    
    def _enable_cdp(self):
        """Enable Chrome DevTools Protocol monitoring."""
        try:
            self.driver.execute_cdp_cmd('Network.enable', {
                'maxTotalBufferSize': 10000000,  # 10MB
                'maxResourceBufferSize': 5000000,  # 5MB
                'maxPostDataSize': 65536  # 64KB
            })
            self.driver.execute_cdp_cmd('Runtime.enable', {})
            self.logger.debug("CDP network monitoring enabled")
        except Exception as e:
            self.logger.warning(f"Could not enable CDP: {e}")
    
    def _inject_monitoring_script(self):
        """Inject JavaScript for request monitoring."""
        script = """
        (function() {
            // Initialize storage
            window.ttScraperRequests = window.ttScraperRequests || [];
            window.ttScraperRealTime = window.ttScraperRealTime || [];
            
            const patterns = arguments[0];
            
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
        """
        
        try:
            result = self.driver.execute_script(script, self.patterns)
            self.logger.debug(f"Monitoring script injected: {result}")
        except Exception as e:
            self.logger.error(f"Failed to inject monitoring script: {e}")
    
    def get_captured_requests(self, clear_after_read: bool = False) -> List[Dict[str, Any]]:
        """Get all captured requests from JavaScript monitoring."""
        try:
            requests = self.driver.execute_script("return window.getTTScraperRequests ? window.getTTScraperRequests() : [];")
            
            if clear_after_read:
                self.driver.execute_script("window.clearTTScraperRequests ? window.clearTTScraperRequests() : null;")
            
            return requests or []
        except Exception as e:
            self.logger.error(f"Error getting captured requests: {e}")
            return []
    
    def get_real_time_requests(self) -> List[Dict[str, Any]]:
        """Get new requests since last call (clears buffer automatically)."""
        try:
            return self.driver.execute_script("return window.getTTScraperRealTime ? window.getTTScraperRealTime() : [];") or []
        except Exception as e:
            self.logger.error(f"Error getting real-time requests: {e}")
            return []
    
    def get_cdp_requests(self) -> List[Dict[str, Any]]:
        """Get requests from Chrome DevTools Protocol logs."""
        try:
            logs = self.driver.get_log('driver')
            cdp_requests = []
            
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    log_message = message.get('message', {})
                    method = log_message.get('method', '')
                    
                    if method == 'Network.requestWillBeSent':
                        params = log_message.get('params', {})
                        request = params.get('request', {})
                        url = request.get('url', '')
                        
                        # Check if URL matches our patterns
                        if any(pattern in url for pattern in self.patterns):
                            request_data = {
                                'type': 'cdp_request',
                                'url': url,
                                'method': request.get('method', 'GET'),
                                'headers': request.get('headers', {}),
                                'timestamp': log['timestamp'],
                                'requestId': params.get('requestId', ''),
                                'initiator': params.get('initiator', {})
                            }
                            cdp_requests.append(request_data)
                            
                except (json.JSONDecodeError, KeyError):
                    continue
            
            return cdp_requests
        except Exception as e:
            self.logger.error(f"Error getting CDP requests: {e}")
            return []
    
    def get_all_requests(self) -> List[Dict[str, Any]]:
        """Get all requests from all monitoring sources."""
        all_requests = []
        
        # Get JavaScript-captured requests
        js_requests = self.get_captured_requests()
        all_requests.extend(js_requests)
        
        # Get CDP requests
        cdp_requests = self.get_cdp_requests()
        all_requests.extend(cdp_requests)
        
        # Remove duplicates based on URL and timestamp
        seen = set()
        unique_requests = []
        
        for req in all_requests:
            key = (req.get('finalUrl', req.get('url', '')), req.get('timestamp', 0))
            if key not in seen:
                seen.add(key)
                unique_requests.append(req)
        
        return unique_requests
    
    def wait_for_requests(self, timeout: float = 5.0, check_interval: float = 0.5) -> List[Dict[str, Any]]:
        """
        Wait for new requests to be captured.
        
        Args:
            timeout: Maximum time to wait in seconds
            check_interval: How often to check for new requests
            
        Returns:
            List of new requests found during the wait period
        """
        start_time = time.time()
        initial_count = len(self.get_captured_requests())
        
        while time.time() - start_time < timeout:
            current_requests = self.get_captured_requests()
            if len(current_requests) > initial_count:
                return current_requests[initial_count:]
            
            time.sleep(check_interval)
        
        return []
    
    def clear_all_requests(self):
        """Clear all captured request data."""
        try:
            self.driver.execute_script("window.clearTTScraperRequests ? window.clearTTScraperRequests() : null;")
            self.captured_requests.clear()
            self.pending_requests.clear()
            self.seen_urls.clear()
            self.logger.debug("All request data cleared")
        except Exception as e:
            self.logger.error(f"Error clearing requests: {e}")
