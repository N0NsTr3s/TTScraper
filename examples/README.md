# TTScraper Examples

This folder contains practical examples demonstrating how to use TTScraper for various TikTok data extraction tasks.

## Examples Overview

### 🎥 Video Data Extraction
- **[extract_video_data.py](extract_video_data.py)** - Extract comprehensive video information including metadata, stats, author details, and hashtags
- **[batch_video_extraction.py](batch_video_extraction.py)** - Process multiple videos efficiently with error handling and progress tracking

### 👤 User Data Extraction  
- **[extract_user_data.py](extract_user_data.py)** - Extract user profile information, follower counts, and bio data
- **[user_videos_extraction.py](user_videos_extraction.py)** - Get all videos from a user's profile with pagination

### 💬 Comment Extraction
- **[extract_comments.py](extract_comments.py)** - Extract comments from a video using network monitoring
- **[organize_comments.py](organize_comments.py)** - Organize comments with replies in a hierarchical structure
- **[comment_analytics.py](comment_analytics.py)** - Analyze comment patterns, sentiment, and engagement metrics

### 🔧 Configuration & Setup
- **[basic_setup.py](basic_setup.py)** - Basic TTScraper initialization and configuration
- **[advanced_config.py](advanced_config.py)** - Advanced configuration with enhanced error handling, retry logic, rate limiting, session statistics, and professional logging with file rotation

### 📊 Data Analysis
- **[video_analytics.py](video_analytics.py)** - Analyze video performance metrics and trends
- **[export_data.py](export_data.py)** - Export scraped data to various formats (CSV, Excel, JSON)

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install selenium undetected-chromedriver webdriver-manager
   ```

2. **Basic Usage**
   ```python
   from TTScraper import TTScraper
   
   # Initialize scraper
   scraper = TTScraper()
   driver = scraper.start_driver()
   
   # Extract video data
   from video import Video
   video = Video(url="https://www.tiktok.com/@username/video/1234567890", driver=driver)
   video_data = video.info()
   
   # Clean up
   driver.quit()
   ```

## Error Handling

All examples include comprehensive error handling and logging. Check the `core/` directory for:
- **Error handling utilities** - Retry logic and custom exceptions
- **Logging configuration** - Professional logging with colored output
- **Rate limiting** - Prevent API overuse and account blocks

## Best Practices

- Always use `driver.quit()` to clean up browser instances
- Implement rate limiting for large-scale scraping
- Handle TikTok's anti-bot measures with random delays
- Save data incrementally to prevent loss on interruption
- Use the logging system for debugging and monitoring

## Support

For additional help:
- Check the main `TTScraper.py` for all available parameters
- Review `core/` modules for infrastructure utilities
- Enable debug logging for detailed troubleshooting
