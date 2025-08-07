# TTScraper - Advanced TikTok Data Extraction Tool

A comprehensive, production-ready TikTok scraping library using Selenium WebDriver with advanced network monitoring, comment extraction, and batch processing capabilities.

Disclaimer: Before you ask, yes, this is made with AI, it has issues but it works (more or less). you may also find weird comments or code.

## 🚀 **Key Features**

- **Advanced Network Monitoring**: Chrome DevTools Protocol (CDP) integration for real-time API request capture
- **Multiple Comment Extraction Methods**: Network monitoring, traditional scrolling, and API response reading
- **Batch Processing**: Extract data from multiple videos with progress tracking and analytics
- **Memory-Efficient Processing**: Large JSON file handling with compression and streaming
- **Rate Limiting Protection**: Intelligent request throttling to prevent TikTok blocks
- **Windows Compatibility**: Fixed Unicode encoding issues for Windows systems

## 📁 **Project Structure**

```
TTScraper/
├── core/                    # Core infrastructure
│   ├── __init__.py         # Core module exports
│   ├── base.py             # Base classes and mixins
│   ├── utils.py            # Logging and utility functions
│   └── exceptions.py       # Custom exception classes
├── browser/                 # Browser automation
│   ├── __init__.py         # Browser module exports
│   └── network.py          # Network monitoring with CDP
├── config/                  # Configuration management
│   ├── __init__.py         # Config module exports
│   └── settings.py         # Settings and configuration classes
├── examples/               # Complete usage examples
│   ├── __init__.py         # Examples module
│   ├── README.md           # Examples documentation
│   ├── basic_setup.py      # Basic TTScraper setup
│   ├── extract_video_data.py      # Video data extraction
│   ├── extract_user_data.py       # User profile extraction
│   ├── extract_comments.py        # Comment extraction methods
│   ├── batch_video_extraction.py  # Batch processing
│   └── advanced_config.py         # Advanced configuration
├── TTScraper.py            # Main browser automation class
├── video.py                # Video data extraction and comments
├── user.py                 # User profile information
├── sound.py                # Sound/music information
├── hashtag.py              # Hashtag information
├── comment.py              # Comment data structures
├── tiktok.py              # Main API coordinator (legacy)
└── helpers.py              # Utility functions
```

## 🛠 **Installation**

### Prerequisites
```bash
pip install selenium undetected-chromedriver webdriver-manager requests
pip install colorama  # For colored logging output
```

### Chrome Browser
- Chrome browser must be installed on your system
- TTScraper works with existing Chrome profiles for better stealth

## 🚀 **Quick Start**

### Basic Video Data Extraction

```python
from TTScraper import TTScraper
from video import Video

# Initialize TTScraper with basic settings
scraper = TTScraper()
driver = scraper.start_driver()

try:
    # Extract video information
    video = Video(url="https://www.tiktok.com/@user/video/123456", driver=driver)
    video_info = video.info()
    
    print(f"Video ID: {video.id}")
    print(f"Stats: {video.stats}")
    print(f"Created: {video.create_time}")
    
finally:
    driver.quit()
```

### Context Manager Usage

```python
from TTScraper import TTScraper
from video import Video

with TTScraper().start_driver() as driver:
    video = Video(url="https://www.tiktok.com/@user/video/123456", driver=driver)
    video_info = video.info()
    # Driver automatically closes when context exits
```

## 🎯 **Core Classes**

### TTScraper (Main Browser Controller)

The main class for browser automation and session management.

```python
from TTScraper import TTScraper

# Basic initialization
scraper = TTScraper()

# Advanced initialization with all options
scraper = TTScraper(
    headless=True,              # Run in headless mode
    user_data_dir="/path/to/chrome/profile",  # Chrome profile path
    profile_directory="Default",  # Profile directory name
    proxy="http://proxy:port",   # Proxy settings
    window_size=(1920, 1080),   # Browser window size
    user_agent="custom-agent",   # Custom user agent
    disable_images=True,         # Disable image loading for speed
    disable_javascript=False,    # Control JavaScript execution
    page_load_strategy="eager",  # Page load strategy
    no_sandbox=True,            # Disable Chrome sandbox
    disable_dev_shm_usage=True, # Disable /dev/shm usage
    disable_gpu=True,           # Disable GPU acceleration
    disable_web_security=False, # Disable web security
    disable_features="",        # Chrome features to disable
    enable_logging=True,        # Enable Chrome logging
    log_level=0,               # Chrome log level
    prefs={},                  # Chrome preferences
    experimental_options={},   # Chrome experimental options
    arguments=[],              # Additional Chrome arguments
    binary_location="",        # Custom Chrome binary path
    debugger_address=""        # Chrome debugger address
)

driver = scraper.start_driver()
```

### Video Class (Advanced Data Extraction)

Extract comprehensive video data including comments using multiple methods.

```python
from video import Video

# Initialize video
video = Video(url="https://www.tiktok.com/@user/video/123456", driver=driver)

# Extract basic video information
video_info = video.info()
print(f"Video stats: {video.stats}")

# Extract comments using network monitoring (recommended)
comments = video.fetch_comments_from_network()
print(f"Found {len(comments)} comments")

# Read previously saved API responses
all_comments = video.read_all_api_responses()

# Get organized comments with replies
organized = video.get_comments_with_replies()
```

### User Class

```python
from user import User

user = User(username="tiktokuser", driver=driver)
user_info = user.info()
print(f"Followers: {user.follower_count}")
```

## 📊 **Examples Usage**

The `examples/` folder contains comprehensive demonstrations:

### 1. Basic Setup (`examples/basic_setup.py`)
```python
# Run the basic setup example
python examples/basic_setup.py
```
- TTScraper initialization
- Driver configuration
- Basic session management

### 2. Video Data Extraction (`examples/extract_video_data.py`)
```python
# Extract video data with JSON export
python examples/extract_video_data.py
```
- Complete video metadata extraction
- Statistics and engagement data
- JSON file export with timestamps

### 3. User Data Extraction (`examples/extract_user_data.py`)
```python
# Extract user profile data
python examples/extract_user_data.py
```
- User profile information
- Follower statistics
- Optional video collection

### 4. Comment Extraction (`examples/extract_comments.py`)
```python
# Extract comments using advanced methods
python examples/extract_comments.py
```
- Network monitoring for real-time capture
- Traditional scrolling method fallback
- Comment analysis and statistics

### 5. Batch Processing (`examples/batch_video_extraction.py`)
```python
# Process multiple videos efficiently
python examples/batch_video_extraction.py
```
- Bulk video processing
- Progress tracking and analytics
- Error handling and recovery
- JSON export of raw data

### 6. Advanced Configuration (`examples/advanced_config.py`)
```python
# Enterprise-level configuration
python examples/advanced_config.py
```
- Custom retry logic
- Session statistics
- Debug modes and comprehensive logging

## 🔧 **Advanced Features**

### Network Monitoring with CDP

TTScraper uses Chrome DevTools Protocol to capture real-time network requests:

```python
from browser.network import NetworkMonitor

# Initialize network monitoring
monitor = NetworkMonitor(driver)
monitor.enable_monitoring(patterns=['/api/comment/list/'])

# Capture comment API requests in real-time
captured_requests = monitor.get_captured_requests()
```

### Professional Logging System

```python
from core.utils import setup_logging, log_function_calls

# Setup colored logging with file rotation
logger = setup_logging(
    name="TTScraper",
    level="INFO",
    log_file="scraper.log",
    max_file_size=10*1024*1024,  # 10MB
    backup_count=5
)

# Decorator for automatic function logging
@log_function_calls
def extract_data():
    # Your extraction logic here
    pass
```

### Memory-Efficient JSON Processing

```python
from core.utils import MemoryEfficientJSONHandler

# Handle large JSON files efficiently
handler = MemoryEfficientJSONHandler(
    compression=True,
    chunk_size=1000
)

# Save with compression
handler.save_json(large_data, "output.json.gz")

# Load with streaming
for chunk in handler.stream_json("large_file.json"):
    process_chunk(chunk)
```

### Rate Limiting Protection

```python
from core.utils import RateLimiter

# Setup rate limiting
limiter = RateLimiter(
    requests_per_minute=30,
    requests_per_hour=1000
)

# Use in your extraction loop
for url in urls:
    limiter.wait_if_needed()
    extract_data(url)
```

## 🛡️ **Error Handling**

TTScraper includes comprehensive error handling:

```python
from core.exceptions import (
    TTScraperError,
    NetworkError, 
    RateLimitError,
    AuthenticationError
)
from core.utils import retry_on_failure

@retry_on_failure(max_attempts=3, delay=2.0)
def extract_with_retry():
    try:
        return video.fetch_comments_from_network()
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        raise
    except RateLimitError as e:
        logger.warning(f"Rate limited: {e}")
        raise
    except AuthenticationError as e:
        logger.error(f"Auth error: {e}")
        raise
```

## 📈 **Performance & Best Practices**

### Optimal Configuration

```python
# For maximum performance
scraper = TTScraper(
    headless=True,              # Faster execution
    disable_images=True,        # Reduce bandwidth
    page_load_strategy="eager", # Faster page loads
    disable_gpu=True,          # Reduce resource usage
    arguments=[
        "--no-first-run",
        "--disable-default-apps",
        "--disable-extensions"
    ]
)
```

### Rate Limiting Guidelines

- **Minimum delay**: 2 seconds between requests
- **Recommended**: 3-5 seconds for bulk operations
- **Use existing Chrome profiles** to reduce detection
- **Implement exponential backoff** for failed requests

### Memory Management

```python
# For large datasets
import gc

with TTScraper().start_driver() as driver:
    for batch in video_batches:
        process_batch(batch)
        gc.collect()  # Force garbage collection
```

## 🔍 **Data Extraction Methods**

### Video Data Structure

```json
{
  "video_id": "12345678909876",
  "stats": {
    "diggCount": "307600",      // Likes
    "shareCount": "16000",      // Shares  
    "commentCount": "5218",     // Comments
    "playCount": "2700000",     // Views
    "collectCount": "14884",    // Saves
    "repostCount": "0"          // Reposts
  },
  "create_time": "2025-08-04T21:08:48",
  "url": "https://www.tiktok.com/@user/video/123456",
  "raw_data": { /* Complete TikTok API response */ }
}
```

### Comment Data Structure

```json
{
  "text": "Amazing video!",
  "user_id": "123456789",
  "username": "commenter",
  "nickname": "Display Name", 
  "digg_count": 45,
  "create_time": 1691234567,
  "reply_comment_total": 3,
  "reply_comments": [ /* Reply objects */ ],
  "avatar_thumb": "https://...",
  "verified": false,
  "liked_by_creator": false
}
```

## 🚨 **Important Notes**

### Legal & Ethical Usage
- **Respect TikTok's Terms of Service**
- Only extract publicly available content
- Implement appropriate rate limiting
- Consider data privacy and user consent

### Technical Limitations
- TikTok actively detects and blocks automated access
- Some content requires authentication
- Regional restrictions may apply
- API endpoints may change without notice

### Windows Compatibility
TTScraper is fully compatible with Windows systems:
- Fixed Unicode encoding issues in logging
- Proper filename sanitization for Windows file systems
- Support for Windows Chrome profiles and paths

## 🐛 **Troubleshooting**

### Common Issues

**Browser Detection:**
```python
# Use existing Chrome profile to reduce detection
scraper = TTScraper(
    user_data_dir=r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data",
    profile_directory="Default"
)
```

**Rate Limiting:**
```python
# Implement proper delays
import time
time.sleep(3)  # Wait 3 seconds between requests
```

**Memory Issues:**
```python
# Process in smaller batches
batch_size = 10
for i in range(0, len(urls), batch_size):
    batch = urls[i:i+batch_size]
    process_batch(batch)
```

**Filename Issues on Windows:**
- TTScraper automatically sanitizes filenames
- Invalid characters (`?`, `*`, `<`, `>`, etc.) are replaced with underscores
- File paths are truncated if too long

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable verbose logging
scraper = TTScraper(enable_logging=True, log_level=0)
```

## 🤝 **Contributing**

Contributions welcome! Priority areas:

- **Enhanced anti-detection methods**
- **Mobile TikTok support**  
- **Additional data extraction endpoints**
- **Performance optimizations**
- **Cross-platform compatibility**


**⚠️ Disclaimer**: This tool is not affiliated with TikTok. Use responsibly and at your own risk. The authors are not responsible for any misuse or legal consequences resulting from the use of this software.

**🔒 Privacy**: Always respect user privacy and data protection laws when collecting data from social media platforms.

