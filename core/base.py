"""
Base classes and common exceptions for TTScraper
"""
from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

if TYPE_CHECKING:
    from ..tiktok import TikTokApi


class InvalidResponseException(Exception):
    """Exception raised when TikTok returns an invalid response."""
    def __init__(self, response_text: str, message: str, error_code: Optional[str] = None):
        self.response_text = response_text
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class RateLimitException(Exception):
    """Exception raised when rate limited by TikTok."""
    def __init__(self, message: str = "Rate limited by TikTok", retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message)


class AuthenticationException(Exception):
    """Exception raised when authentication is required or fails."""
    pass


class BaseTikTokObject(ABC):
    """
    Base class for all TikTok objects (Video, User, Sound, etc.)
    
    Provides common functionality and interface for all TikTok data objects.
    """
    
    parent: ClassVar[TikTokApi]
    
    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs):
        self.as_dict: Dict[str, Any] = data or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if data is not None:
            self._extract_from_data()
    
    @abstractmethod
    def _extract_from_data(self) -> None:
        """Extract object properties from raw data dictionary."""
        pass
    
    def __repr__(self) -> str:
        """Return string representation of the object."""
        class_name = self.__class__.__name__
        id_attr = getattr(self, 'id', None) or getattr(self, 'username', None)
        return f"{class_name}(id='{id_attr}')"
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return self.__repr__()
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the raw data dictionary."""
        return self.as_dict.copy()
    
    def refresh(self, **kwargs) -> None:
        """Refresh the object data by making a new request."""
        # To be implemented by subclasses if needed
        pass


class BaseScrapingMixin:
    """Mixin class providing common scraping utilities."""
    
    @staticmethod
    def _safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get a value from a dictionary."""
        try:
            return data.get(key, default)
        except (TypeError, AttributeError):
            return default
    
    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _safe_str(value: Any, default: str = "") -> str:
        """Safely convert value to string."""
        try:
            return str(value) if value is not None else default
        except (TypeError, ValueError):
            return default


class SessionManager:
    """Manages browser sessions and their lifecycle using nodriver."""
    
    def __init__(self, config=None):
        from ..config.settings import DEFAULT_CONFIG
        self.config = config or DEFAULT_CONFIG
        self.scraper = None
        self.tab = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def start_session(self, **kwargs):
        """Start a new browser session (async)."""
        if self.tab is not None:
            self.logger.warning("Session already active, closing existing session")
            self.close_session()
        
        # Import here to avoid circular imports
        from ..browser.driver import EnhancedTTScraper
        
        self.scraper = EnhancedTTScraper(self.config)
        self.tab = await self.scraper.start_driver(**kwargs)
        return self.tab
    
    def close_session(self):
        """Close the current session."""
        if self.scraper:
            self.scraper.close_driver()
            self.scraper = None
            self.tab = None
            self.logger.info("Session closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return await self.start_session()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close_session()
