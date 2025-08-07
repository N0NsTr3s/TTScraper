"""
Rate limiting and request throttling for TTScraper
"""
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging


class RateLimiter:
    """
    Rate limiter to prevent overwhelming TikTok servers.
    
    Implements both per-domain and global rate limiting with exponential backoff
    for rate limit violations.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 1000,
        cooldown_on_rate_limit: int = 300,  # 5 minutes
        logger: Optional[logging.Logger] = None
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.cooldown_on_rate_limit = cooldown_on_rate_limit
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Track requests per domain
        self.request_history: Dict[str, list] = {}
        self.rate_limit_until: Dict[str, datetime] = {}
        self.lock = threading.Lock()
    
    def can_make_request(self, domain: str = "tiktok.com") -> bool:
        """
        Check if a request can be made without violating rate limits.
        
        Args:
            domain: Domain to check rate limits for
            
        Returns:
            True if request can be made, False otherwise
        """
        with self.lock:
            now = datetime.now()
            
            # Check if we're in cooldown period
            if domain in self.rate_limit_until:
                if now < self.rate_limit_until[domain]:
                    remaining = (self.rate_limit_until[domain] - now).total_seconds()
                    self.logger.warning(f"Rate limited for {domain}. {remaining:.0f}s remaining")
                    return False
                else:
                    # Cooldown period is over
                    del self.rate_limit_until[domain]
            
            # Initialize request history for domain if needed
            if domain not in self.request_history:
                self.request_history[domain] = []
            
            # Clean old requests from history
            cutoff_minute = now - timedelta(minutes=1)
            cutoff_hour = now - timedelta(hours=1)
            
            self.request_history[domain] = [
                req_time for req_time in self.request_history[domain]
                if req_time > cutoff_hour
            ]
            
            # Count recent requests
            recent_minute = sum(
                1 for req_time in self.request_history[domain]
                if req_time > cutoff_minute
            )
            recent_hour = len(self.request_history[domain])
            
            # Check limits
            if recent_minute >= self.requests_per_minute:
                self.logger.warning(f"Per-minute rate limit exceeded for {domain}")
                return False
            
            if recent_hour >= self.requests_per_hour:
                self.logger.warning(f"Per-hour rate limit exceeded for {domain}")
                return False
            
            return True
    
    def record_request(self, domain: str = "tiktok.com") -> None:
        """
        Record that a request was made.
        
        Args:
            domain: Domain the request was made to
        """
        with self.lock:
            now = datetime.now()
            
            if domain not in self.request_history:
                self.request_history[domain] = []
            
            self.request_history[domain].append(now)
    
    def record_rate_limit(self, domain: str = "tiktok.com", custom_cooldown: Optional[int] = None) -> None:
        """
        Record that we hit a rate limit and enter cooldown.
        
        Args:
            domain: Domain that rate limited us
            custom_cooldown: Custom cooldown period in seconds
        """
        with self.lock:
            cooldown = custom_cooldown or self.cooldown_on_rate_limit
            self.rate_limit_until[domain] = datetime.now() + timedelta(seconds=cooldown)
            
            self.logger.warning(f"Rate limited by {domain}. Entering {cooldown}s cooldown.")
    
    def wait_if_needed(self, domain: str = "tiktok.com") -> float:
        """
        Wait if necessary to respect rate limits.
        
        Args:
            domain: Domain to check
            
        Returns:
            Time waited in seconds
        """
        start_time = time.time()
        
        while not self.can_make_request(domain):
            time.sleep(1)
        
        waited = time.time() - start_time
        if waited > 0:
            self.logger.info(f"Waited {waited:.1f}s for rate limiting")
        
        return waited
    
    def get_stats(self, domain: str = "tiktok.com") -> Dict[str, Any]:
        """Get rate limiting statistics."""
        with self.lock:
            now = datetime.now()
            cutoff_minute = now - timedelta(minutes=1)
            cutoff_hour = now - timedelta(hours=1)
            
            if domain not in self.request_history:
                return {
                    "requests_last_minute": 0,
                    "requests_last_hour": 0,
                    "rate_limited": False,
                    "cooldown_remaining": 0
                }
            
            recent_minute = sum(
                1 for req_time in self.request_history[domain]
                if req_time > cutoff_minute
            )
            recent_hour = sum(
                1 for req_time in self.request_history[domain]
                if req_time > cutoff_hour
            )
            
            rate_limited = domain in self.rate_limit_until and now < self.rate_limit_until[domain]
            cooldown_remaining = 0
            
            if rate_limited:
                cooldown_remaining = (self.rate_limit_until[domain] - now).total_seconds()
            
            return {
                "requests_last_minute": recent_minute,
                "requests_last_hour": recent_hour,
                "rate_limited": rate_limited,
                "cooldown_remaining": cooldown_remaining,
                "limit_per_minute": self.requests_per_minute,
                "limit_per_hour": self.requests_per_hour
            }


class RequestThrottler:
    """
    Simple request throttler with minimum delay between requests.
    """
    
    def __init__(self, min_delay: float = 1.0, logger: Optional[logging.Logger] = None):
        self.min_delay = min_delay
        self.last_request_time: Optional[float] = None
        self.lock = threading.Lock()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    def throttle(self) -> float:
        """
        Throttle requests by waiting if necessary.
        
        Returns:
            Time waited in seconds
        """
        with self.lock:
            now = time.time()
            
            if self.last_request_time is not None:
                elapsed = now - self.last_request_time
                if elapsed < self.min_delay:
                    wait_time = self.min_delay - elapsed
                    self.logger.debug(f"Throttling request: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                    self.last_request_time = time.time()
                    return wait_time
            
            self.last_request_time = now
            return 0.0


# Global rate limiter instance
global_rate_limiter = RateLimiter()
global_throttler = RequestThrottler(min_delay=2.0)  # 2 second minimum between requests
