"""
Video Data Extraction Example

This example demonstrates how to extract comprehensive video information
from TikTok videos including metadata, stats, author details, and hashtags.
"""

import logging
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TTScraper import TTScraper
from video import Video


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('video_extraction.log', encoding='utf-8')
        ]
    )
    return logging.getLogger("VideoExtraction")


def extract_video_data(video_url, driver):
    """
    Extract comprehensive data from a TikTok video.
    
    Args:
        video_url (str): The TikTok video URL
        driver: Selenium WebDriver instance
        
    Returns:
        dict: Comprehensive video data
    """
    logger = logging.getLogger("VideoExtraction")
    
    try:
        logger.info(f"Extracting data from video: {video_url}")
        
        # Create Video instance
        video = Video(url=video_url, driver=driver)
        
        # Extract video information
        logger.info("Extracting video metadata...")
        video_data = video.info()
        
        # Organize the extracted data
        organized_data = {
            'extraction_timestamp': datetime.now().isoformat(),
            'video_url': video_url,
            'video_info': {
            'id': video.id,
            'create_time': video.create_time.isoformat() if video.create_time else None,
            'stats': video.stats,
            'as_dict': video.as_dict
            },
            'author_info': {
            'username': getattr(video.author, 'uniqueId', None) if video.author else None,
            'nickname': getattr(video.author, 'nickname', None) if video.author else None,
            'follower_count': getattr(video.author, 'follower_count', None) if video.author else None,
            'following_count': getattr(video.author, 'following_count', None) if video.author else None,
            'verified': getattr(video.author, 'verified', None) if video.author else None,
            'signature': getattr(video.author, 'signature', None) if video.author else None,
            'avatar_url': getattr(video.author, 'avatar_url', None) if video.author else None,
            'full_author_data': video.author.as_dict if video.author and hasattr(video.author, 'as_dict') else None
            },
            'sound_info': {
            'title': getattr(video.sound, 'title', None) if video.sound else None,
            'author': getattr(video.sound, 'author', None) if video.sound else None,
            'duration': getattr(video.sound, 'duration', None) if video.sound else None,
            'play_url': getattr(video.sound, 'play_url', None) if video.sound else None,
            'full_sound_data': video.sound.as_dict if video.sound and hasattr(video.sound, 'as_dict') else None
            },
            'challenges': [
            {
                'hashtag_id': challenge.get('id'),
                'hashtag_name': challenge.get('title')
            }
            for challenge in video.as_dict.get('challenges', [])
            ] if hasattr(video, 'as_dict') and video.as_dict else [],
            'engagement_metrics': video.stats if video.stats else None,
            'raw_data': video_data
        }
        
        # Log summary information
        logger.info("Video data extraction completed!")
        logger.info(f"   Video ID: {organized_data['video_info']['id']}")
        
        if organized_data['author_info']['username']:
            logger.info(f"   Author: @{organized_data['author_info']['username']}")
        
        if organized_data['engagement_metrics']:
            stats = organized_data['engagement_metrics']
            # Safely format numbers, handling both strings and integers
            for stat_name, log_name in [
                ('diggCount', 'Likes'),
                ('commentCount', 'Comments'), 
                ('shareCount', 'Shares'),
                ('playCount', 'Views'),
                ('challenges', 'Hashtags')
            ]:
                value = stats.get(stat_name, 'N/A')
                if value != 'N/A':
                    try:
                        # Try to convert to int for formatting
                        value = int(value) if value is not None else 0
                        logger.info(f"   {log_name}: {value:,}")
                    except (ValueError, TypeError):
                        # If conversion fails, just display as string
                        logger.info(f"   {log_name}: {value}")
                else:
                    logger.info(f"   {log_name}: {value}")
        
        
        return organized_data
        
    except Exception as e:
        logger.error(f"Error extracting video data: {e}")
        return {
            'extraction_timestamp': datetime.now().isoformat(),
            'video_url': video_url,
            'error': str(e),
            'success': False
        }


def save_video_data(video_data, filename=None):
    """
    Save video data to JSON file.
    
    Args:
        video_data (dict): The video data to save
        filename (str): Optional custom filename
    """
    logger = logging.getLogger("VideoExtraction")
    
    if not filename:
        video_id = video_data.get('video_info', {}).get('id', 'unknown')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_data_{video_id}_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(video_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Video data saved to: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error saving video data: {e}")
        return None


def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("Starting Video Data Extraction Example")
    
    # Example video URLs for testing
    example_urls = [
        "https://www.tiktok.com/@username/video/1234567890123456789",
        # Add more URLs as needed
    ]
    
    # Get video URL from user
    print("\nTikTok Video Data Extraction")
    print("=" * 40)
    
    video_url = input("Enter TikTok video URL: ").strip()
    
    if not video_url:
        print("No URL provided. Using example URL for demonstration.")
        video_url = example_urls[0]
    
    # Validate URL
    if not ('tiktok.com' in video_url and '/video/' in video_url):
        print("Invalid TikTok video URL format.")
        return
    
    driver = None
    try:
        # Initialize TTScraper
        logger.info("Initializing TTScraper...")
        scraper = TTScraper()
        driver = scraper.start_driver()
        
        # Extract video data
        video_data = extract_video_data(video_url, driver)
        
        # Save data to file
        if video_data.get('success', True):  # Default to True if key doesn't exist
            filename = save_video_data(video_data)
            
            if filename:
                print(f"\nSuccess! Video data extracted and saved to: {filename}")
                
                # Show summary
                print("\nExtraction Summary:")
                print(f"   Video ID: {video_data.get('video_info', {}).get('id', 'N/A')}")
                
                author = video_data.get('author', {})
                if author.get('nickname'):
                    print(f"   Author: @{author['nickname']} ({author.get('nickname', 'N/A')})")
                
                stats = video_data.get('engagement_metrics', {})
                if stats:
                    # Safely format numbers, handling both strings and integers
                    likes = stats.get('diggCount', 0)
                    comments = stats.get('commentCount', 0)
                    
                    # Convert to int if it's a string that represents a number
                    try:
                        likes = int(likes) if likes is not None else 0
                        comments = int(comments) if comments is not None else 0
                        print(f"   Engagement: {likes:,} likes, {comments:,} comments")
                    except (ValueError, TypeError):
                        # If conversion fails, just display as strings
                        print(f"   Engagement: {likes} likes, {comments} comments")

                hashtags = video_data.get('raw_data', {}).get('challenges', [])
                if hashtags:
                    hashtag_list = [f"#{h['title']}" for h in hashtags if h.get('title', {})]
                    print(f"   Top Hashtags: {', '.join(hashtag_list[:5])}")
            else:
                print("Failed to save video data")
        else:
            print(f"Failed to extract video data: {video_data.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"An error occurred: {e}")
    
    finally:
        # Clean up
        if driver:
            try:
                driver.quit()
                logger.info("Browser closed successfully")
            except:
                logger.warning("Could not close browser cleanly")


if __name__ == "__main__":
    main()
