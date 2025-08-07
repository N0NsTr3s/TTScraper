"""
User Data Extraction Example

This example demonstrates how to extract comprehensive user information
from TikTok user profiles including follower counts, bio data, and profile statistics.
"""

import logging
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TTScraper import TTScraper
from user import User


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('user_extraction.log', encoding='utf-8')
        ]
    )
    return logging.getLogger("UserExtraction")


def extract_user_data(username, driver):
    """
    Extract comprehensive data from a TikTok user profile.
    
    Args:
        username (str): The TikTok username (with or without @)
        driver: Selenium WebDriver instance
        
    Returns:
        dict: Comprehensive user data
    """
    logger = logging.getLogger("UserExtraction")
    
    try:
        # Clean username (remove @ if present)
        clean_username = username.lstrip('@')
        logger.info(f"Extracting data for user: @{clean_username}")
        
        # Create User instance
        user = User(username=clean_username, driver=driver)
        
        # Extract user information
        logger.info("Extracting user profile data...")
        user_data = user.info()
        
        # Organize the extracted data
        organized_data = {
            'extraction_timestamp': datetime.now().isoformat(),
            'username': clean_username,
            'profile_url': f"https://www.tiktok.com/@{clean_username}",
            'profile_info': {
                'id': getattr(user, 'id', None),
                'sec_uid': getattr(user, 'sec_uid', None),
                'username': getattr(user, 'username', None),
                'display_name': getattr(user, 'display_name', None),
                'bio': getattr(user, 'signature', None),
                'verified': getattr(user, 'verified', None),
                'follower_count': getattr(user, 'follower_count', None),
                'following_count': getattr(user, 'following_count', None),
                'video_count': getattr(user, 'video_count', None),
                'heart_count': getattr(user, 'heart_count', None),
                'avatar_url': getattr(user, 'avatar_url', None)
            },
            'raw_data': user_data if hasattr(user, 'as_dict') else None,
            'as_dict': getattr(user, 'as_dict', None)
        }
        
        # Log summary information
        logger.info("User data extraction completed!")
        logger.info(f"   Username: @{organized_data['username']}")
        
        profile = organized_data['profile_info']
        if profile.get('display_name'):
            logger.info(f"   Display Name: {profile['display_name']}")
        
        if profile.get('verified'):
            logger.info(f"   Verified Account")
        
        if profile.get('follower_count'):
            logger.info(f"   Followers: {profile['follower_count']:,}")
        
        if profile.get('following_count'):
            logger.info(f"   Following: {profile['following_count']:,}")
        
        if profile.get('video_count'):
            logger.info(f"   Videos: {profile['video_count']:,}")
        
        if profile.get('heart_count'):
            logger.info(f"   Total Likes: {profile['heart_count']:,}")
        
        if profile.get('bio'):
            logger.info(f"   Bio: {profile['bio'][:100]}...")
        
        return organized_data
        
    except Exception as e:
        logger.error(f"Error extracting user data: {e}")
        return {
            'extraction_timestamp': datetime.now().isoformat(),
            'username': username,
            'error': str(e),
            'success': False
        }


def extract_user_videos(username, driver, count=20):
    """
    Extract videos from a user's profile.
    
    Args:
        username (str): The TikTok username
        driver: Selenium WebDriver instance
        count (int): Number of videos to extract
        
    Returns:
        list: List of video data
    """
    logger = logging.getLogger("UserExtraction")
    
    try:
        logger.info(f"Extracting {count} videos from @{username}")
        
        # Create User instance
        user = User(username=username.lstrip('@'), driver=driver)
        
        # Get user videos (assuming this method exists)
        videos = []
        try:
            video_generator = user.videos(count=count)
            for video in video_generator:
                video_data = {
                    'id': getattr(video, 'id', None),
                    'url': getattr(video, 'url', None),
                    'create_time': getattr(video, 'create_time', None),
                    'stats': getattr(video, 'stats', None),
                    'as_dict': getattr(video, 'as_dict', None)
                }
                videos.append(video_data)
                
                if len(videos) >= count:
                    break
                    
        except Exception as video_error:
            logger.warning(f"Error extracting videos: {video_error}")
        
        logger.info(f"Extracted {len(videos)} videos from @{username}")
        return videos
        
    except Exception as e:
        logger.error(f"Error extracting user videos: {e}")
        return []


def save_user_data(user_data, filename=None):
    """
    Save user data to JSON file.
    
    Args:
        user_data (dict): The user data to save
        filename (str): Optional custom filename
    """
    logger = logging.getLogger("UserExtraction")
    
    if not filename:
        username = user_data.get('username', 'unknown')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_data_{username}_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"User data saved to: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return None


def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("Starting User Data Extraction Example")
    
    # Get username from user
    print("\nTikTok User Data Extraction")
    print("=" * 40)
    
    username = input("Enter TikTok username (with or without @): ").strip()
    
    if not username:
        print("No username provided.")
        return
    
    # Clean username
    clean_username = username.lstrip('@')
    
    # Ask for video extraction
    extract_videos = input("Extract user videos? (y/n): ").strip().lower() == 'y'
    video_count = 10
    
    if extract_videos:
        try:
            video_count = int(input("How many videos to extract? (default 10): ") or "10")
        except ValueError:
            video_count = 10
    
    driver = None
    try:
        # Initialize TTScraper
        logger.info("Initializing TTScraper...")
        scraper = TTScraper()
        driver = scraper.start_driver()
        
        # Extract user data
        user_data = extract_user_data(clean_username, driver)
        
        # Extract videos if requested
        if extract_videos and user_data.get('success', True):
            logger.info(f"Extracting {video_count} videos...")
            videos = extract_user_videos(clean_username, driver, video_count)
            user_data['videos'] = videos
            user_data['video_extraction'] = {
                'requested_count': video_count,
                'extracted_count': len(videos),
                'extraction_timestamp': datetime.now().isoformat()
            }
        
        # Save data to file
        if user_data.get('success', True):
            filename = save_user_data(user_data)
            
            if filename:
                print(f"\nSuccess! User data extracted and saved to: {filename}")
                
                # Show summary
                print("\nExtraction Summary:")
                print(f"   Username: @{user_data.get('username', 'N/A')}")
                
                profile = user_data.get('profile_info', {})
                if profile.get('display_name'):
                    print(f"   Display Name: {profile['display_name']}")
                
                if profile.get('verified'):
                    print(f"   Verified Account")
                
                if profile.get('follower_count'):
                    print(f"   Followers: {profile['follower_count']:,}")
                
                if profile.get('video_count'):
                    print(f"   Total Videos: {profile['video_count']:,}")
                
                if extract_videos:
                    extracted = user_data.get('video_extraction', {}).get('extracted_count', 0)
                    print(f"   Videos Extracted: {extracted}")
            else:
                print("Failed to save user data")
        else:
            print(f"Failed to extract user data: {user_data.get('error', 'Unknown error')}")
    
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
