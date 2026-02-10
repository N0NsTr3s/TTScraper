"""
User Data Extraction Example

This example demonstrates how to extract comprehensive user information
from TikTok user profiles using nodriver (async CDP), including:
  - Profile info (bio, stats, avatar)
  - Videos list via /api/post/item_list/
  - Reposts via /api/repost/item_list/
  - Following list via /api/user/list/ (scene=21)
  - Followers list via /api/user/list/ (scene=67)

All extraction uses CDP network interception — TikTok's own authenticated
requests are captured, so no manual fetch() or token spoofing is needed.
"""

import asyncio
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


async def extract_user_profile(username, tab):
    """
    Extract profile data from a TikTok user page (hydration data).

    Returns:
        dict: Organized profile data.
    """
    logger = logging.getLogger("UserExtraction")
    try:
        clean_username = username.lstrip('@')
        logger.info(f"Extracting profile for @{clean_username}")

        user = User(username=clean_username, tab=tab)
        user_data = await user.info()

        profile = {
            'id': getattr(user, 'id', None),
            'sec_uid': getattr(user, 'sec_uid', None),
            'username': getattr(user, 'username', None),
            'display_name': getattr(user, 'nickname', None),
            'bio': getattr(user, 'signature', None),
            'verified': getattr(user, 'verified', None),
            'follower_count': getattr(user, 'follower_count', 0),
            'following_count': getattr(user, 'following_count', 0),
            'video_count': getattr(user, 'video_count', 0),
            'heart_count': getattr(user, 'heart_count', 0),
            'friends_count': getattr(user, 'friends_count', 0),
            'digg_count': getattr(user, 'digg_count', 0),
            'avatar_url': getattr(user, 'avatar_url', None),
        }

        logger.info(f"Profile extracted for @{clean_username}")
        return user, profile

    except Exception as e:
        logger.error(f"Error extracting profile: {e}")
        return None, {'error': str(e)}


async def extract_user_videos(user, tab, max_pages=50):
    """Fetch and parse the user's video list via CDP capture."""
    logger = logging.getLogger("UserExtraction")
    try:
        logger.info("Fetching videos via CDP...")
        raw = await user.fetch_videos(tab=tab, max_pages=max_pages)
        parsed = User.parse_videos(raw)
        logger.info(f"Extracted {len(parsed)} videos")
        return raw, parsed
    except Exception as e:
        logger.error(f"Error fetching videos: {e}")
        return [], []


async def extract_user_reposts(user, tab, max_pages=50):
    """Fetch and parse the user's repost list via CDP capture."""
    logger = logging.getLogger("UserExtraction")
    try:
        logger.info("Fetching reposts via CDP...")
        raw = await user.fetch_reposts(tab=tab, max_pages=max_pages)
        parsed = User.parse_reposts(raw)
        logger.info(f"Extracted {len(parsed)} reposts")
        return raw, parsed
    except Exception as e:
        logger.error(f"Error fetching reposts: {e}")
        return [], []


async def extract_user_following(user, tab, max_pages=50):
    """Fetch and parse the user's following list via CDP capture."""
    logger = logging.getLogger("UserExtraction")
    try:
        logger.info("Fetching following list via CDP...")
        raw = await user.fetch_following(tab=tab, max_pages=max_pages)
        parsed = User.parse_user_list(raw)
        logger.info(f"Extracted {len(parsed)} following")
        return raw, parsed
    except Exception as e:
        logger.error(f"Error fetching following: {e}")
        return [], []


async def extract_user_followers(user, tab, max_pages=50):
    """Fetch and parse the user's followers list via CDP capture."""
    logger = logging.getLogger("UserExtraction")
    try:
        logger.info("Fetching followers list via CDP...")
        raw = await user.fetch_followers(tab=tab, max_pages=max_pages)
        parsed = User.parse_user_list(raw)
        logger.info(f"Extracted {len(parsed)} followers")
        return raw, parsed
    except Exception as e:
        logger.error(f"Error fetching followers: {e}")
        return [], []


def display_profile(profile):
    """Display profile info to console."""
    print(f"\n{'=' * 50}")
    print(f"  Profile: @{profile.get('username', 'N/A')}")
    print(f"{'=' * 50}")
    if profile.get('display_name'):
        print(f"  Display Name : {profile['display_name']}")
    if profile.get('verified'):
        print(f"  Verified     : ✓")
    if profile.get('bio'):
        bio = profile['bio'][:100] + ('...' if len(profile.get('bio', '')) > 100 else '')
        print(f"  Bio          : {bio}")
    print(f"  Followers    : {profile.get('follower_count', 0):,}")
    print(f"  Following    : {profile.get('following_count', 0):,}")
    print(f"  Videos       : {profile.get('video_count', 0):,}")
    print(f"  Total Likes  : {profile.get('heart_count', 0):,}")
    print()


def display_videos(parsed_videos, limit=10):
    """Display video list to console."""
    if not parsed_videos:
        print("  No videos found.\n")
        return

    print(f"\n{'─' * 50}")
    print(f"  Videos ({len(parsed_videos)} total, showing first {min(limit, len(parsed_videos))})")
    print(f"{'─' * 50}")

    for i, v in enumerate(parsed_videos[:limit]):
        desc = v['description'][:60] + ('...' if len(v['description']) > 60 else '')
        print(f"  {i+1}. {desc or '(no description)'}")
        print(f"     📅 {v['create_time_formatted']}  "
              f"▶ {v['play_count']:,}  ❤ {v['digg_count']:,}  "
              f"💬 {v['comment_count']:,}  🔗 {v['share_count']:,}")
        if v.get('is_pinned'):
            print(f"     📌 Pinned")
        if v.get('hashtags'):
            tags = ' '.join(f"#{t['name']}" for t in v['hashtags'][:5])
            print(f"     {tags}")
        print()


def display_reposts(parsed_reposts, limit=10):
    """Display repost list to console."""
    if not parsed_reposts:
        print("  No reposts found.\n")
        return

    print(f"\n{'─' * 50}")
    print(f"  Reposts ({len(parsed_reposts)} total, showing first {min(limit, len(parsed_reposts))})")
    print(f"{'─' * 50}")

    for i, v in enumerate(parsed_reposts[:limit]):
        desc = v['description'][:60] + ('...' if len(v['description']) > 60 else '')
        print(f"  {i+1}. {desc or '(no description)'}")
        print(f"     by @{v['author_username']}  "
              f"▶ {v['play_count']:,}  ❤ {v['digg_count']:,}")
        print()


def display_user_list(parsed_users, list_type="following", limit=20):
    """Display a following/followers list to console."""
    if not parsed_users:
        print(f"  No {list_type} found.\n")
        return

    print(f"\n{'─' * 50}")
    print(f"  {list_type.capitalize()} ({len(parsed_users)} total, "
          f"showing first {min(limit, len(parsed_users))})")
    print(f"{'─' * 50}")

    for i, u in enumerate(parsed_users[:limit]):
        verified = " ✓" if u.get('verified') else ""
        nickname = u.get('nickname') or u.get('username')
        print(f"  {i+1}. @{u['username']}{verified}  ({nickname})")
        if u.get('signature'):
            bio = u['signature'][:50] + ('...' if len(u.get('signature', '')) > 50 else '')
            print(f"     {bio}")
        print(f"     👥 {u.get('follower_count', 0):,} followers  "
              f"🎬 {u.get('video_count', 0):,} videos")
        print()


def build_structured_output(profile, parsed_videos, parsed_reposts,
                            parsed_following, parsed_followers):
    """Build a structured JSON output for saving."""
    return {
        'extraction_timestamp': datetime.now().isoformat(),
        'profile': profile,
        'videos': {
            'count': len(parsed_videos),
            'items': parsed_videos,
        },
        'reposts': {
            'count': len(parsed_reposts),
            'items': parsed_reposts,
        },
        'following': {
            'count': len(parsed_following),
            'items': parsed_following,
        },
        'followers': {
            'count': len(parsed_followers),
            'items': parsed_followers,
        },
    }


def print_summary(profile, parsed_videos, parsed_reposts,
                   parsed_following, parsed_followers):
    """Print extraction summary."""
    print(f"\n{'=' * 50}")
    print(f"  Extraction Summary for @{profile.get('username', 'N/A')}")
    print(f"{'=' * 50}")
    print(f"  Videos    : {len(parsed_videos)} extracted")
    print(f"  Reposts   : {len(parsed_reposts)} extracted")
    print(f"  Following : {len(parsed_following)} extracted")
    print(f"  Followers : {len(parsed_followers)} extracted")
    print()


async def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("Starting User Data Extraction")

    print("\nTikTok User Data Extraction (CDP Network Capture)")
    print("=" * 50)

    username = input("Enter TikTok username (with or without @): ").strip()
    if not username:
        print("No username provided.")
        return

    clean_username = username.lstrip('@')

    # Ask what to extract
    print(f"\nWhat to extract for @{clean_username}?")
    print("  1. Profile info only")
    print("  2. Profile + Videos")
    print("  3. Profile + Videos + Reposts")
    print("  4. Profile + Following + Followers")
    print("  5. Everything (Profile + Videos + Reposts + Following + Followers)")

    choice = input("\nChoice (1-5, default 5): ").strip() or "5"

    do_videos = choice in ("2", "3", "5")
    do_reposts = choice in ("3", "5")
    do_following = choice in ("4", "5")
    do_followers = choice in ("4", "5")

    scraper = None
    try:
        logger.info("Initializing TTScraper...")
        scraper = TTScraper()
        tab = await scraper.start_browser()

        # ── 1. Extract profile ──────────────────────────────────────
        user, profile = await extract_user_profile(clean_username, tab)
        if user is None:
            print(f"Failed to extract profile: {profile.get('error', 'Unknown')}")
            return

        display_profile(profile)

        # ── 2. Extract videos ───────────────────────────────────────
        raw_videos, parsed_videos = [], []
        if do_videos:
            raw_videos, parsed_videos = await extract_user_videos(user, tab)
            display_videos(parsed_videos)

        # ── 3. Extract reposts ──────────────────────────────────────
        raw_reposts, parsed_reposts = [], []
        if do_reposts:
            raw_reposts, parsed_reposts = await extract_user_reposts(user, tab)
            display_reposts(parsed_reposts)

        # ── 4. Extract following ────────────────────────────────────
        raw_following, parsed_following = [], []
        if do_following:
            raw_following, parsed_following = await extract_user_following(user, tab)
            display_user_list(parsed_following, "following")

        # ── 5. Extract followers ────────────────────────────────────
        raw_followers, parsed_followers = [], []
        if do_followers:
            raw_followers, parsed_followers = await extract_user_followers(user, tab)
            display_user_list(parsed_followers, "followers")

        # ── Summary ─────────────────────────────────────────────────
        print_summary(profile, parsed_videos, parsed_reposts,
                      parsed_following, parsed_followers)

        # ── Save to file ────────────────────────────────────────────
        structured = build_structured_output(
            profile, parsed_videos, parsed_reposts,
            parsed_following, parsed_followers
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_data_{clean_username}_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(structured, f, indent=2, ensure_ascii=False, default=str)

        print(f"✅ Data saved to: {filename}")

        # Also save raw API responses
        raw_filename = f"user_data_{clean_username}_{timestamp}_raw.json"
        raw_data = {
            'videos_raw': raw_videos,
            'reposts_raw': raw_reposts,
            'following_raw': raw_following,
            'followers_raw': raw_followers,
        }
        with open(raw_filename, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"✅ Raw API data saved to: {raw_filename}")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"An error occurred: {e}")

    finally:
        if scraper:
            scraper.close()
            logger.info("Browser closed successfully")


if __name__ == "__main__":
    asyncio.run(main())
