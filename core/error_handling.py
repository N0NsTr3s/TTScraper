"""
Retry and error handling utilities for TTScraper
"""
import time
import logging
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
import requests
from selenium.common.exceptions import WebDriverException, TimeoutException


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_exceptions = retryable_exceptions or [
            requests.RequestException,
            requests.Timeout,
            requests.ConnectionError,
            WebDriverException,
            TimeoutException,
            ConnectionError,
            OSError
        ]


def retry_on_exception(
    config: Optional[RetryConfig] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Decorator to retry function calls on specific exceptions.
    
    Args:
        config: Retry configuration
        logger: Logger for retry attempts
    """
    if config is None:
        config = RetryConfig()
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except tuple(config.retryable_exceptions) as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"Function {func.__name__} failed after {config.max_retries + 1} attempts")
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.backoff_factor ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                    raise e
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class TikTokScrapingError(Exception):
    """Base exception for TikTok scraping errors."""
    pass


class NetworkError(TikTokScrapingError):
    """Network-related scraping error."""
    pass


class RateLimitError(TikTokScrapingError):
    """Rate limiting error."""
    
    def __init__(self, message: str = "Rate limited", retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(TikTokScrapingError):
    """Authentication required or failed."""
    pass


class DataExtractionError(TikTokScrapingError):
    """Error extracting data from TikTok response."""
    pass


class ErrorHandler:
    """Centralized error handling for TTScraper operations."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    def handle_request_error(self, error: Exception, url: str = "") -> None:
        """Handle HTTP request errors."""
        if isinstance(error, requests.exceptions.Timeout):
            raise NetworkError(f"Request timeout for URL: {url}")
        elif isinstance(error, requests.exceptions.ConnectionError):
            raise NetworkError(f"Connection error for URL: {url}")
        elif isinstance(error, requests.exceptions.HTTPError):
            status_code = getattr(error.response, 'status_code', 'unknown')
            if status_code == 429:
                raise RateLimitError(f"Rate limited (429) for URL: {url}")
            elif status_code == 403:
                raise AuthenticationError(f"Access forbidden (403) for URL: {url}")
            else:
                raise NetworkError(f"HTTP error {status_code} for URL: {url}")
        else:
            raise NetworkError(f"Network error for URL: {url}: {str(error)}")
    
    def handle_selenium_error(self, error: Exception, context: str = "") -> None:
        """Handle Selenium WebDriver errors."""
        if isinstance(error, TimeoutException):
            raise TikTokScrapingError(f"Selenium timeout: {context}")
        elif isinstance(error, WebDriverException):
            raise TikTokScrapingError(f"WebDriver error: {context}: {str(error)}")
        else:
            raise TikTokScrapingError(f"Selenium error: {context}: {str(error)}")
    
    def handle_data_extraction_error(self, error: Exception, data_type: str = "") -> None:
        """Handle data extraction errors."""
        raise DataExtractionError(f"Failed to extract {data_type}: {str(error)}")


# Global error handler instance
error_handler = ErrorHandler()


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    error_context: str = "",
    logger: Optional[logging.Logger] = None,
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Function arguments
        default_return: Default value to return on error
        error_context: Context description for error logging
        logger: Logger instance
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in {error_context or func.__name__}: {e}")
        return default_return


def validate_url(url: str) -> bool:
    """Validate if URL is a valid TikTok URL."""
    if not url or not isinstance(url, str):
        return False
    
    valid_patterns = [
        r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
        r'https?://(?:vm|vt)\.tiktok\.com/[\w-]+',
        r'https?://(?:www\.)?tiktok\.com/t/[\w-]+',
    ]
    
    import re
    return any(re.match(pattern, url) for pattern in valid_patterns)


def validate_user_identifier(identifier: str, identifier_type: str = "username") -> bool:
    """Validate user identifier (username, user_id, etc.)."""
    if not identifier or not isinstance(identifier, str):
        return False
    
    if identifier_type == "username":
        # Username validation (no @ symbol, alphanumeric + underscore/dots)
        import re
        return re.match(r'^[a-zA-Z0-9._-]+$', identifier) is not None
    elif identifier_type == "user_id":
        # User ID should be numeric
        return identifier.isdigit()
    
    return True  # For other types, basic non-empty check
