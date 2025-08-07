"""
Comment Extraction Example

This example demonstrates how to extract comments from TikTok videos
using advanced network monitoring and organize them with replies.
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
            logging.FileHandler('comment_extraction.log', encoding='utf-8')

        ]
    )
    return logging.getLogger("CommentExtraction")


def extract_comments_network(video_url, driver):
    """
    Extract comments using network monitoring approach.
    
    Args:
        video_url (str): The TikTok video URL
        driver: Selenium WebDriver instance
        
    Returns:
        list: List of comment API responses
    """
    logger = logging.getLogger("CommentExtraction")
    
    try:
        logger.info(f"💬 Extracting comments using network monitoring: {video_url}")
        
        # Create Video instance
        video = Video(url=video_url, driver=driver)
        
        # Use network monitoring to capture comment API requests
        logger.info("🕸️ Starting network monitoring for comment extraction...")
        comment_responses = video.fetch_comments_from_network(driver=driver)
        
        logger.info(f"✅ Network monitoring completed. Captured {len(comment_responses)} API responses")
        
        if not comment_responses:
            logger.warning("⚠️ No comments found in network responses")
            return []
        return comment_responses
        
    except Exception as e:
        logger.error(f"❌ Error in network comment extraction: {e}")
        return []


def process_comment_responses(video_url, driver):
    """
    Process and organize comment responses from API.
    
    Args:
        video_url (str): The TikTok video URL
        driver: Selenium WebDriver instance
        
    Returns:
        dict: Organized comment data
    """
    logger = logging.getLogger("CommentExtraction")
    
    try:
        # Create Video instance
        video = Video(url=video_url, driver=driver)
        
        # Read and process all API responses
        logger.info("📖 Reading and processing API responses...")
        all_comments = video.read_all_api_responses(driver=driver)
        
        if not all_comments:
            logger.warning("⚠️ No comments found in API responses")
            return {'comments': [], 'total': 0, 'success': False}
        
        # Organize comments with replies
        logger.info("🗂️ Organizing comments with reply structure...")
        organized_comments = video.get_comments_with_replies(driver=driver)
        
        return organized_comments
        
    except Exception as e:
        logger.error(f"❌ Error processing comment responses: {e}")
        return {'comments': [], 'total': 0, 'success': False, 'error': str(e)}


def extract_traditional_comments(video_url, driver):
    """
    Extract comments using traditional scrolling method.
    
    Args:
        video_url (str): The TikTok video URL
        driver: Selenium WebDriver instance
        
    Returns:
        list: List of comment objects
    """
    logger = logging.getLogger("CommentExtraction")
    
    try:
        logger.info(f"📜 Extracting comments using traditional scrolling: {video_url}")
        
        # Create Video instance
        video = Video(url=video_url, driver=driver)
        
        # Use safe_comments method for traditional extraction
        comments = []
        try:
            comment_generator = video.safe_comments(driver=driver)
            for comment in comment_generator:
                comments.append(comment)
                
                # Limit to prevent infinite scrolling
                if len(comments) >= 100:
                    break
                    
        except Exception as comment_error:
            logger.warning(f"⚠️ Error in traditional comment extraction: {comment_error}")
        
        logger.info(f"✅ Traditional extraction completed. Found {len(comments)} comments")
        return comments
        
    except Exception as e:
        logger.error(f"❌ Error in traditional comment extraction: {e}")
        return []


def analyze_comments(comments_data):
    """
    Perform basic analysis on extracted comments.
    
    Args:
        comments_data (dict or list): Comment data to analyze
        
    Returns:
        dict: Analysis results
    """
    logger = logging.getLogger("CommentExtraction")
    
    try:
        # Handle different data structures
        if isinstance(comments_data, dict):
            if 'comments' in comments_data:
                comments = comments_data['comments']
            else:
                comments = []
        else:
            comments = comments_data
        
        if not comments:
            return {'total_comments': 0, 'analysis': 'No comments to analyze'}
        
        analysis = {
            'total_comments': len(comments),
            'comments_with_replies': 0,
            'total_replies': 0,
            'top_liked_comments': [],
            'recent_comments': [],
            'comment_lengths': [],
            'authors': set()
        }
        
        for comment in comments:
            # Handle different comment structures
            if isinstance(comment, dict):
                # Count replies
                replies = comment.get('replies', [])
                if replies:
                    analysis['comments_with_replies'] += 1
                    analysis['total_replies'] += len(replies)
                
                # Track comment text length
                text = comment.get('text', '')
                if text:
                    analysis['comment_lengths'].append(len(text))
                
                # Track authors
                author_info = comment.get('author_info', {}) or comment.get('user', {})
                if author_info:
                    author_name = author_info.get('username') or author_info.get('uniqueId')
                    if author_name:
                        analysis['authors'].add(author_name)
                
                # Top liked comments
                likes = comment.get('digg_count', 0) or comment.get('likes', 0)
                if likes:
                    analysis['top_liked_comments'].append({
                        'text': text[:100] + '...' if len(text) > 100 else text,
                        'likes': likes,
                        'author': author_info.get('username', 'Unknown') if author_info else 'Unknown'
                    })
        
        # Sort top liked comments
        analysis['top_liked_comments'].sort(key=lambda x: x['likes'], reverse=True)
        analysis['top_liked_comments'] = analysis['top_liked_comments'][:5]
        
        # Calculate averages
        if analysis['comment_lengths']:
            analysis['average_comment_length'] = sum(analysis['comment_lengths']) / len(analysis['comment_lengths'])
        
        analysis['unique_authors'] = len(analysis['authors'])
        analysis['authors'] = list(analysis['authors'])  # Convert set to list for JSON serialization
        
        logger.info(f"📊 Comment analysis completed:")
        logger.info(f"   Total comments: {analysis['total_comments']}")
        logger.info(f"   Comments with replies: {analysis['comments_with_replies']}")
        logger.info(f"   Total replies: {analysis['total_replies']}")
        logger.info(f"   Unique authors: {analysis['unique_authors']}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Error analyzing comments: {e}")
        return {'error': str(e)}


def save_comments_data(comments_data, video_url, method="network", filename=None):
    """
    Save comments data to JSON file.
    
    Args:
        comments_data: The comments data to save
        video_url (str): The source video URL
        method (str): Extraction method used
        filename (str): Optional custom filename
    """
    logger = logging.getLogger("CommentExtraction")
    
    if not filename:
        # Extract video ID from URL for filename
        video_id = video_url.split('/')[-1] if '/' in video_url else 'unknown'
        # Remove URL parameters and sanitize filename
        video_id = video_id.split('?')[0]  # Remove query parameters
        # Sanitize filename by removing invalid characters
        import re
        video_id = re.sub(r'[<>:"/\\|?*]', '_', video_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comments_{method}_{video_id}_{timestamp}.json"
    
    try:
        # Create comprehensive save data
        save_data = {
            'extraction_timestamp': datetime.now().isoformat(),
            'video_url': video_url,
            'extraction_method': method,
            'comments_data': comments_data,
            'total_comments': len(comments_data) if isinstance(comments_data, list) else 0,

        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Comments data saved to: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"❌ Error saving comments data: {e}")
        return None


def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("🚀 Starting Comment Extraction Example")
    
    # Get video URL from user
    print("\n💬 TikTok Comment Extraction")
    print("=" * 40)
    
    video_url = input("Enter TikTok video URL: ").strip()
    
    if not video_url:
        print("❌ No URL provided.")
        return
    
    # Validate URL
    if not ('tiktok.com' in video_url and '/video/' in video_url):
        print("❌ Invalid TikTok video URL format.")
        return
    
    # Choose extraction method
    print("\nChoose extraction method:")
    print("1. Network Monitoring (Recommended)")
    print("2. Traditional Scrolling")
    print("3. Both methods")
    
    method_choice = input("Enter choice (1-3): ").strip()
    
    driver = None
    try:
        # Initialize TTScraper
        logger.info("🔧 Initializing TTScraper...")
        scraper = TTScraper()
        driver = scraper.start_driver()
        
        results = {}
        
        # Network monitoring method
        if method_choice in ['1', '3']:
            logger.info("🕸️ Starting network monitoring extraction...")
            print("🕸️ Extracting comments using network monitoring...")
            
            # First capture network requests
            api_responses = extract_comments_network(video_url, driver)
            
            if api_responses:
                # Process the responses
                organized_comments = process_comment_responses(video_url, driver)
                results['network'] = organized_comments
                
                # Save network results
                network_file = save_comments_data(organized_comments, video_url, "network")
                if network_file:
                    print(f"✅ Network extraction saved to: {network_file}")
            else:
                print("⚠️ No comments captured via network monitoring")
        
        # Traditional scrolling method  
        if method_choice in ['2', '3']:
            logger.info("📜 Starting traditional scrolling extraction...")
            print("📜 Extracting comments using traditional scrolling...")
            try:
                    # Example video URL for testing
                    
                    print(f"Testing video: {video_url}")
                    import video
                    # Create video instance
                    TikTok_video = video.create_video_from_url(video_url, driver)
                    print(f"Video ID: {TikTok_video.id}")

                    # Fetch comments using the new navigation method
                    print("\nFetching comments via API navigation...")
                    comments = TikTok_video.safe_comments(driver=driver)
                    
                    # Convert generator to list to count and process
                    comment_list = list(comments)
                    total_comments = len(comment_list)
                    total_replies = sum(len(comment.get('replies', [])) for comment in comment_list)
                    total_interactions = total_comments + total_replies
                    
                    print(f"\n=== EXTRACTION SUMMARY ===")
                    print(f"Total main comments: {total_comments}")
                    print(f"Total replies: {total_replies}")
                    print(f"Total interactions: {total_interactions}")
                    print(f"Expected from UI: 113 (if this doesn't match, some comments/replies might not have loaded)")
                    
                    for idx, comment in enumerate(comment_list, 1):  # Display comments with index
                        print(f"\nComment {idx}:")
                        print(f"  Username: {comment.get('username', 'Unknown')}")
                        print(f"  User Profile URL: {comment.get('user_profile_url', 'Unknown')}")
                        print(f"  Avatar URL: {comment.get('avatar_url', 'No avatar')}")
                        print(f"  Text: {comment.get('text', 'No text')}")
                        print(f"  Time: {comment.get('time', 'Unknown')}")
                        print(f"  Like Count: {comment.get('like_count', 0)}")
                        print(f"  Reply Count: {comment.get('reply_count', 0)}")
                        print(f"  Comment ID: {comment.get('comment_id', 'Unknown')}")
                        #print(f"  Badges: {', '.join(comment.get('badges', [])) if comment.get('badges') else 'None'}")

                        # Display raw HTML for debugging (optional)
                        #print(f"  Raw HTML: {comment.get('raw_html', 'No raw HTML available')[:100]}...")  # Truncate for readability

                        # Display replies if available (note: safe_comments uses 'replies' key, not 'reply_comments')
                        replies = comment.get('replies', [])
                        if replies:
                            print(f"  Replies ({len(replies)}):")
                            for reply_idx, reply in enumerate(replies, 1):
                                print(f"    Reply {reply_idx}:")
                                print(f"      Username: {reply.get('username', 'Unknown')}")
                                print(f"      Text: {reply.get('text', 'No text')}")
                                print(f"      Like Count: {reply.get('like_count', 0)}")
                                print(f"      Time: {reply.get('time', 'Unknown')}")
                                print(f"      TikTok URL: {reply.get('user_profile_url', 'Unknown')}")
                                print(f"      Avatar URL: {reply.get('avatar_url', 'Unknown')}")
                                # Show whom this reply is replying to, if available
                                replied_to = reply.get('reply_to_username') or reply.get('replied_to', 'Unknown')
                                print(f"      Replied to: {replied_to}")
                        else:
                            print(f"  No replies found (expected: {comment.get('reply_count', 0)})")

            except Exception as e:
                print(f"Error occurred: {e}")
                import traceback
                traceback.print_exc()

        
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"❌ An error occurred: {e}")
    
    finally:
        # Clean up
        if driver:
            try:
                driver.quit()
                logger.info("🧹 Browser closed successfully")
            except:
                logger.warning("⚠️ Could not close browser cleanly")


if __name__ == "__main__":
    main()
