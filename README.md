# TTScraper - Advanced TikTok Data Extraction Tool

A comprehensive TikTok scraping library using **nodriver** (async CDP) with real-time network monitoring, comment/reply extraction, and user data scraping.

> **Disclaimer**: This project is made with AI assistance. It has issues but it works (more or less). You may find weird comments or code.

## 🚀 **Key Features**

- **CDP Network Capture**: Intercepts TikTok's authenticated API requests — no token spoofing needed
- **Comment Extraction**: Fetch comments + replies via `/api/comment/list/` and `/api/comment/list/reply/`
- **User Data Extraction**: Videos, reposts, followers, and following lists
- **Persistent Login**: Log in once, reuse your session across all scripts
- **Rate Limiting**: Built-in request throttling to avoid blocks
- **Language-Independent**: Element selection uses HTML structure, not text labels

## 📁 **Project Structure**

```
TTScraper/
├── TTScraper.py            # Main browser automation class
├── video.py                # Video info + comment extraction (CDP)
├── user.py                 # User profile, videos, reposts, followers, following
├── sound.py                # Sound/music information
├── hashtag.py              # Hashtag information
├── comment.py              # Comment data structures
├── helpers.py              # Utility functions
├── browser/
│   ├── driver.py           # Enhanced driver with config support
│   └── network.py          # CDP network monitoring
├── config/
│   └── settings.py         # Configuration classes
├── core/
│   ├── base.py             # Base classes
│   ├── logging_config.py   # Logging setup
│   └── rate_limiting.py    # Rate limiter
├── examples/
│   ├── login_setup.py      # ⭐ First-time login (run this first!)
│   ├── extract_user_data.py    # User profile + lists extraction
│   ├── extract_comments.py     # Comment + reply extraction
│   ├── extract_video_data.py   # Video metadata extraction
│   └── batch_video_extraction.py
└── browser_profiles/       # Chrome profile data (auto-created)
```

## 🛠 **Installation**

### Prerequisites
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install nodriver requests colorama
```

### Chrome Browser
Chrome must be installed. nodriver manages it automatically via CDP.

---

## ⭐ **First-Time Setup: Login**

**Before extracting followers, following, or other authenticated data, you must log into TikTok.**

Run the login script once:

```bash
python examples/login_setup.py
```

This opens Chrome on TikTok's login page. Log in manually, then press Enter in the terminal. Your session is saved to `browser_profiles/` and reused by all other scripts.

> **Note**: You only need to do this once. Cookies persist across runs.

---

## 🚀 **Quick Start**

### Extract User Data (Videos, Followers, Following)

```bash
python examples/extract_user_data.py
```

You'll be prompted for:
1. TikTok username
2. What to extract (profile, videos, reposts, following, followers)

Results are saved to JSON files.

### Extract Video Comments + Replies

```bash
python examples/extract_comments.py
```

Enter a video URL. The script captures comments via CDP, expands replies, and saves structured output.

---

## 🎯 **Core Classes**

### TTScraper (Browser Controller)

```python
import asyncio
from TTScraper import TTScraper

async def main():
    scraper = TTScraper()
    tab = await scraper.start_browser()
    
    # ... do work ...
    
    scraper.close()

asyncio.run(main())
```

### Video (Comments + Info)

```python
from video import Video

video = Video(url="https://www.tiktok.com/@user/video/123", tab=tab)

# Get video metadata
await video.info()

# Fetch comments + replies via CDP
raw_comments = await video.fetch_comments(tab=tab)
parsed = Video.parse_comments(raw_comments)
```

### User (Profile + Lists)

```python
from user import User

user = User(username="tiktokuser", tab=tab)

# Get profile info
await user.info()

# Fetch videos via CDP (/api/post/item_list/)
raw_videos = await user.fetch_videos(tab=tab)
parsed_videos = User.parse_videos(raw_videos)

# Fetch reposts via CDP (/api/repost/item_list/)
raw_reposts = await user.fetch_reposts(tab=tab)

# Fetch following list (/api/user/list/ scene=21)
raw_following = await user.fetch_following(tab=tab)
parsed_following = User.parse_user_list(raw_following)

# Fetch followers list (/api/user/list/ scene=67)
raw_followers = await user.fetch_followers(tab=tab)
parsed_followers = User.parse_user_list(raw_followers)
```

---

## 📊 **Data Structures**

### Parsed Comment

```json
{
  "comment_id": "7574851587252718870",
  "text": "Great video!",
  "username": "user123",
  "nickname": "User Name",
  "user_id": "6789",
  "digg_count": 42,
  "reply_count": 3,
  "create_time": 1691234567,
  "is_author_liked": false,
  "replies": [ /* nested reply objects */ ]
}
```

### Parsed User (from following/followers list)

```json
{
  "user_id": "123456",
  "username": "cooluser",
  "nickname": "Cool User",
  "sec_uid": "MS4w...",
  "verified": true,
  "signature": "Bio text here",
  "follower_count": 50000,
  "following_count": 200,
  "video_count": 85
}
```

### Parsed Video

```json
{
  "video_id": "7574851587252718870",
  "description": "Check this out! #fyp",
  "create_time": 1691234567,
  "play_count": 1500000,
  "digg_count": 85000,
  "comment_count": 1200,
  "share_count": 3400,
  "duration": 45,
  "hashtags": [{"name": "fyp"}]
}
```

---

## 🔧 **Configuration**

### Browser Profile Location

By default, Chrome profile data is stored in `browser_profiles/` inside the project folder. This is set in `config/settings.py`:

```python
@dataclass
class BrowserConfig:
    user_data_dir: Optional[str] = None  # Defaults to <project>/browser_profiles
    profile_directory: str = "Profile 1"
    headless: bool = False
```

### Custom Configuration

```python
scraper = TTScraper(
    headless=True,
    user_data_dir=r"C:\MyProfiles",
    profile_directory="TikTok",
    no_sandbox=True,
)
```

---

## 🛡️ **Troubleshooting**

### "Not logged in" or empty followers/following

Run `login_setup.py` and log into your TikTok account. Session cookies are saved automatically.

### CDP not capturing API calls

- Make sure the modal/tab is actually opening (check the browser window)
- Try refreshing the page manually
- For reposts: the script will retry up to 3 times with page refresh

### Rate limiting / blocks

- Increase delays between requests
- Use a logged-in session
- Don't run multiple scrapers simultaneously

### Debug logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## ⚠️ **Important Notes**

- **Legal**: Respect TikTok's Terms of Service. Only extract public content.
- **Privacy**: Respect data privacy laws (GDPR, etc.)
- **Detection**: TikTok actively blocks automated access. Use delays and real profiles.
- **Changes**: TikTok's API endpoints may change without notice.

---

**🔒 Disclaimer**: This tool is not affiliated with TikTok. Use responsibly and at your own risk.

