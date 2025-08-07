"""
Logging configuration for TTScraper
"""
import logging
import sys
from typing import Optional
from datetime import datetime


class TTScraperLogger:
    """Enhanced logger for TTScraper with custom formatting."""
    
    def __init__(self, name: str = "TTScraper", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up console and file handlers."""
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Custom formatter with colors
        class ColoredFormatter(logging.Formatter):
            """Colored formatter for console output."""
            
            COLORS = {
                'DEBUG': '\033[36m',    # Cyan
                'INFO': '\033[32m',     # Green
                'WARNING': '\033[33m',  # Yellow
                'ERROR': '\033[31m',    # Red
                'CRITICAL': '\033[35m', # Magenta
                'RESET': '\033[0m'      # Reset
            }
            
            def format(self, record):
                color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
                reset = self.COLORS['RESET']
                
                # Format timestamp
                timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
                
                # Create colored message
                if record.levelname in ['INFO', 'DEBUG']:
                    # Simpler format for info/debug
                    return f"{color}[{timestamp}] {record.getMessage()}{reset}"
                else:
                    # More detailed format for warnings/errors
                    return f"{color}[{timestamp}] {record.levelname}: {record.getMessage()}{reset}"
        
        console_handler.setFormatter(ColoredFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler (optional)
        try:
            file_handler = logging.FileHandler('ttscraper.log', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except PermissionError:
            # Can't write to file, continue with console only
            pass
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger
    
    @classmethod
    def setup_module_logger(cls, module_name: str, level: int = logging.INFO) -> logging.Logger:
        """Set up a logger for a specific module."""
        logger_instance = cls(name=f"TTScraper.{module_name}", level=level)
        return logger_instance.get_logger()


# Global logger setup
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger instance."""
    if name is None:
        name = "TTScraper"
    elif not name.startswith("TTScraper"):
        name = f"TTScraper.{name}"
    
    return TTScraperLogger(name).get_logger()


# Progress indicator utilities
class ProgressIndicator:
    """Simple progress indicator for long-running operations."""
    
    def __init__(self, total: int, description: str = "Processing", logger: Optional[logging.Logger] = None):
        self.total = total
        self.current = 0
        self.description = description
        self.logger = logger or get_logger("Progress")
        self.start_time = datetime.now()
    
    def update(self, increment: int = 1, message: str = ""):
        """Update progress counter."""
        self.current += increment
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
        
        progress_msg = f"{self.description}: {self.current}/{self.total} ({percentage:.1f}%)"
        if message:
            progress_msg += f" - {message}"
        progress_msg += f" [Elapsed: {elapsed_str}]"
        
        self.logger.info(progress_msg)
    
    def finish(self, message: str = "Complete"):
        """Mark progress as finished."""
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]
        
        self.logger.info(f"{self.description}: {message} in {elapsed_str}")


# Decorator for logging function calls
def log_function_call(logger: Optional[logging.Logger] = None):
    """Decorator to log function calls with timing."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(func.__module__)
            start_time = datetime.now()
            
            func_logger.debug(f"Starting {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                elapsed = datetime.now() - start_time
                func_logger.debug(f"Completed {func.__name__} in {elapsed.total_seconds():.2f}s")
                return result
            except Exception as e:
                elapsed = datetime.now() - start_time
                func_logger.error(f"Failed {func.__name__} after {elapsed.total_seconds():.2f}s: {e}")
                raise
        
        return wrapper
    return decorator
