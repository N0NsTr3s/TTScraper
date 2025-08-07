"""
Core base classes and utilities for TTScraper.
"""

from .base import (
    InvalidResponseException,
    RateLimitException, 
    AuthenticationException,
    BaseTikTokObject,
    BaseScrapingMixin,
    SessionManager
)

from .error_handling import (
    RetryConfig,
    retry_on_exception,
    TikTokScrapingError,
    NetworkError,
    RateLimitError,
    AuthenticationError,
    DataExtractionError,
    ErrorHandler,
    error_handler,
    safe_execute,
    validate_url,
    validate_user_identifier
)

from .logging_config import (
    TTScraperLogger,
    get_logger,
    ProgressIndicator,
    log_function_call
)

from .file_utils import (
    MemoryEfficientJSONHandler,
    FileManager,
    ChunkedProcessor,
    json_handler,
    file_manager
)

__all__ = [
    # Base classes
    'InvalidResponseException',
    'RateLimitException',
    'AuthenticationException', 
    'BaseTikTokObject',
    'BaseScrapingMixin',
    'SessionManager',
    
    # Error handling
    'RetryConfig',
    'retry_on_exception',
    'TikTokScrapingError',
    'NetworkError',
    'RateLimitError',
    'AuthenticationError',
    'DataExtractionError',
    'ErrorHandler',
    'error_handler',
    'safe_execute',
    'validate_url',
    'validate_user_identifier',
    
    # Logging
    'TTScraperLogger',
    'get_logger',
    'ProgressIndicator',
    'log_function_call',
    
    # File utilities
    'MemoryEfficientJSONHandler',
    'FileManager',
    'ChunkedProcessor',
    'json_handler',
    'file_manager'
]
