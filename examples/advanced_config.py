"""
Advanced Configuration Example

This example demonstrates advanced TTScraper configuration with
custom settings, error handling, and optimization techniques.
"""

import logging
import sys
import os
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TTScraper import TTScraper
from video import Video
from user import User


def setup_advanced_logging(log_level=logging.INFO):
    """Setup advanced logging with file rotation and custom formatting."""
    import logging.handlers
    
    # Create logger
    logger = logging.getLogger("AdvancedTTScraper")
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)8s | %(funcName)s:%(lineno)d | %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler with colored output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        'advanced_ttscraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        'ttscraper_errors.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    return logger


class AdvancedTTScraper:
    """Advanced TTScraper wrapper with enhanced configuration and error handling."""
    
    def __init__(self, config=None):
        self.logger = setup_advanced_logging()
        self.config = self._load_config(config)
        self.driver = None
        self.session_stats = {
            'start_time': datetime.now(),
            'requests_made': 0,
            'errors_encountered': 0,
            'videos_processed': 0,
            'users_processed': 0
        }
    
    def _load_config(self, config):
        """Load configuration with defaults."""
        default_config = {
            'browser': {
                'headless': False,
                'window_size': '1920,1080',
                'user_agent': None,
                'disable_images': True,
                'disable_css': True,
                'disable_plugins': True,
                'enable_javascript': True,
                'page_load_timeout': 30,
                'implicit_wait': 10
            },
            'scraping': {
                'request_delay': 2.0,
                'max_retries': 3,
                'retry_delay': 5.0,
                'rate_limit_per_minute': 30,
                'enable_network_monitoring': True,
                'save_raw_data': True
            },
            'output': {
                'save_json': True,
                'save_csv': False,
                'output_directory': './output',
                'filename_pattern': '{type}_{id}_{timestamp}',
                'compress_files': False
            },
            'debug': {
                'enable_debug_mode': False,
                'save_page_source': False,
                'save_screenshots': False,
                'verbose_logging': False
            }
        }
        
        if config:
            # Merge user config with defaults
            for section, settings in config.items():
                if section in default_config:
                    default_config[section].update(settings)
                else:
                    default_config[section] = settings
        
        return default_config
    
    def initialize_driver(self):
        """Initialize driver with advanced configuration."""
        self.logger.info("🔧 Initializing advanced TTScraper driver...")
        
        try:
            # Prepare Chrome arguments
            chrome_args = []
            
            browser_config = self.config['browser']
            
            if browser_config['disable_images']:
                chrome_args.append('--disable-images')
            
            if browser_config['disable_css']:
                chrome_args.append('--disable-css')
            
            if browser_config['disable_plugins']:
                chrome_args.append('--disable-plugins')
            
            chrome_args.extend([
                f"--window-size={browser_config['window_size']}",
                '--no-first-run',
                '--disable-default-apps',
                '--disable-popup-blocking',
                '--disable-extensions-file-access-check',
                '--disable-extensions-except',
                '--disable-component-extensions-with-background-pages'
            ])
            
            if self.config['debug']['enable_debug_mode']:
                chrome_args.extend([
                    '--enable-logging',
                    '--log-level=0',
                    '--v=1'
                ])
            
            # Initialize TTScraper
            scraper = TTScraper(args=chrome_args)
            
            # Start driver
            self.driver = scraper.start_driver(
                headless=browser_config['headless'],
                enable_cdp_events=self.config['scraping']['enable_network_monitoring'],
                debug=self.config['debug']['enable_debug_mode'],
                log_level=0 if self.config['debug']['verbose_logging'] else 1
            )
            
            # Set timeouts
            self.driver.implicitly_wait(browser_config['implicit_wait'])
            self.driver.set_page_load_timeout(browser_config['page_load_timeout'])
            
            # Set custom user agent if specified
            if browser_config['user_agent']:
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    'userAgent': browser_config['user_agent']
                })
            
            self.logger.info("✅ Driver initialized successfully")
            
            # Test driver functionality
            self._test_driver()
            
            return self.driver
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize driver: {e}")
            raise
    
    def _test_driver(self):
        """Test driver functionality."""
        try:
            if not self.driver:
                self.logger.warning("⚠️ Driver not initialized, skipping test")
                return
                
            self.logger.debug("🧪 Testing driver functionality...")
            
            # Test basic navigation
            start_time = time.time()
            self.driver.get("https://www.tiktok.com")
            load_time = time.time() - start_time
            
            self.logger.info(f"✅ Driver test passed - Page loaded in {load_time:.2f}s")
            
            # Save screenshot if debug mode is enabled
            if self.config['debug']['save_screenshots']:
                screenshot_path = f"debug_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_path)
                self.logger.debug(f"📸 Debug screenshot saved: {screenshot_path}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Driver test failed: {e}")
    
    def extract_video_with_retry(self, video_url, max_retries=None):
        """Extract video data with retry logic."""
        if max_retries is None:
            max_retries = self.config['scraping']['max_retries']
        
        retry_delay = self.config['scraping']['retry_delay']
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"🎥 Extracting video (attempt {attempt + 1}/{max_retries + 1}): {video_url}")
                
                # Apply rate limiting
                self._apply_rate_limiting()
                
                # Create video instance
                video = Video(url=video_url, driver=self.driver)
                
                # Extract data
                video_data = video.info()
                
                # Update stats
                self.session_stats['videos_processed'] += 1
                self.session_stats['requests_made'] += 1
                
                # Save raw data if enabled
                if self.config['scraping']['save_raw_data']:
                    self._save_raw_data(video_data, 'video', video.id)
                
                self.logger.info(f"✅ Video extracted successfully: {video_url}")
                return {
                    'success': True,
                    'data': video_data,
                    'video': video,
                    'attempts': attempt + 1
                }
                
            except Exception as e:
                self.session_stats['errors_encountered'] += 1
                self.logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries:
                    self.logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"❌ All {max_retries + 1} attempts failed for: {video_url}")
                    return {
                        'success': False,
                        'error': str(e),
                        'attempts': max_retries + 1
                    }
    
    def extract_user_with_retry(self, username, max_retries=None):
        """Extract user data with retry logic."""
        if max_retries is None:
            max_retries = self.config['scraping']['max_retries']
        
        retry_delay = self.config['scraping']['retry_delay']
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"👤 Extracting user (attempt {attempt + 1}/{max_retries + 1}): @{username}")
                
                # Apply rate limiting
                self._apply_rate_limiting()
                
                # Create user instance
                user = User(username=username, driver=self.driver)
                
                # Extract data
                user_data = user.info()
                
                # Update stats
                self.session_stats['users_processed'] += 1
                self.session_stats['requests_made'] += 1
                
                # Save raw data if enabled
                if self.config['scraping']['save_raw_data']:
                    self._save_raw_data(user_data, 'user', username)
                
                self.logger.info(f"✅ User extracted successfully: @{username}")
                return {
                    'success': True,
                    'data': user_data,
                    'user': user,
                    'attempts': attempt + 1
                }
                
            except Exception as e:
                self.session_stats['errors_encountered'] += 1
                self.logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries:
                    self.logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"❌ All {max_retries + 1} attempts failed for: @{username}")
                    return {
                        'success': False,
                        'error': str(e),
                        'attempts': max_retries + 1
                    }
    
    def _apply_rate_limiting(self):
        """Apply rate limiting to prevent overwhelming TikTok servers."""
        delay = self.config['scraping']['request_delay']
        if delay > 0:
            time.sleep(delay)
    
    def _save_raw_data(self, data, data_type, identifier):
        """Save raw data to file."""
        try:
            output_dir = self.config['output']['output_directory']
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_pattern = self.config['output']['filename_pattern']
            
            filename = filename_pattern.format(
                type=data_type,
                id=identifier,
                timestamp=timestamp
            ) + '.json'
            
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"💾 Raw data saved: {filepath}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save raw data: {e}")
    
    def get_session_stats(self):
        """Get current session statistics."""
        current_time = datetime.now()
        duration = current_time - self.session_stats['start_time']
        
        return {
            'session_duration': str(duration),
            'start_time': self.session_stats['start_time'].isoformat(),
            'current_time': current_time.isoformat(),
            'requests_made': self.session_stats['requests_made'],
            'errors_encountered': self.session_stats['errors_encountered'],
            'videos_processed': self.session_stats['videos_processed'],
            'users_processed': self.session_stats['users_processed'],
            'success_rate': (
                (self.session_stats['requests_made'] - self.session_stats['errors_encountered']) 
                / max(1, self.session_stats['requests_made'])
            ) * 100
        }
    
    def cleanup(self):
        """Clean up resources and save session data."""
        try:
            # Save session statistics
            stats = self.get_session_stats()
            stats_file = f"session_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"📊 Session stats saved: {stats_file}")
            
            # Close driver
            if self.driver:
                self.driver.quit()
                self.logger.info("🧹 Browser closed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")


def main():
    """Main example function."""
    print("\n🔧 TTScraper Advanced Configuration Example")
    print("=" * 50)
    
    # Define custom configuration
    custom_config = {
        'browser': {
            'headless': False,
            'window_size': '1366,768',
            'disable_images': True,
            'page_load_timeout': 45,
            'implicit_wait': 15
        },
        'scraping': {
            'request_delay': 3.0,
            'max_retries': 5,
            'retry_delay': 10.0,
            'enable_network_monitoring': True,
            'save_raw_data': True
        },
        'output': {
            'output_directory': './advanced_output',
            'filename_pattern': 'advanced_{type}_{id}_{timestamp}',
            'save_json': True
        },
        'debug': {
            'enable_debug_mode': True,
            'save_screenshots': True,
            'verbose_logging': True
        }
    }
    
    # Initialize advanced scraper
    scraper = AdvancedTTScraper(config=custom_config)
    
    try:
        # Initialize driver
        driver = scraper.initialize_driver()
        
        # Example: Extract video with retry
        video_url = input("Enter TikTok video URL (or press Enter for demo): ").strip()
        if video_url and 'tiktok.com' in video_url:
            result = scraper.extract_video_with_retry(video_url)
            
            if result and result.get('success'):
                print(f"✅ Video extracted successfully in {result['attempts']} attempt(s)")
                
                # Show video info
                video = result['video']
                print(f"   Video ID: {getattr(video, 'id', 'N/A')}")
                if video.author:
                    print(f"   Author: @{getattr(video.author, 'username', 'N/A')}")
                if video.stats:
                    print(f"   Likes: {video.stats.get('diggCount', 'N/A'):,}")
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                print(f"❌ Failed to extract video: {error_msg}")
        
        # Example: Extract user with retry  
        username = input("Enter TikTok username (or press Enter to skip): ").strip()
        if username:
            result = scraper.extract_user_with_retry(username.lstrip('@'))
            
            if result and result.get('success'):
                print(f"✅ User extracted successfully in {result['attempts']} attempt(s)")
                
                # Show user info
                user = result['user']
                print(f"   Username: @{getattr(user, 'username', 'N/A')}")
                print(f"   Followers: {getattr(user, 'follower_count', 'N/A'):,}")
                print(f"   Videos: {getattr(user, 'video_count', 'N/A'):,}")
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                print(f"❌ Failed to extract user: {error_msg}")
        
        # Show session statistics
        stats = scraper.get_session_stats()
        print(f"\n📊 Session Statistics:")
        print(f"   Duration: {stats['session_duration']}")
        print(f"   Requests Made: {stats['requests_made']}")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        print(f"   Videos Processed: {stats['videos_processed']}")
        print(f"   Users Processed: {stats['users_processed']}")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    
    finally:
        # Cleanup
        scraper.cleanup()


if __name__ == "__main__":
    main()
