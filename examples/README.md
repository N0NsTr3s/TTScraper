# TTScraper Examples

This folder contains practical examples demonstrating how to use TTScraper for various TikTok data extraction tasks.

## ⚠️ First-Time Setup

Before extracting followers, following, or any authenticated data, you must log in:

```bash
python examples/login_setup.py
```

This opens Chrome, lets you log into TikTok manually, and saves your session to `browser_profiles/`. All future scripts will reuse this session.

## Examples Overview

### 🔐 Authentication
- **[login_setup.py](login_setup.py)** - One-time login to save your TikTok session

### 👤 User Data Extraction  
- **[extract_user_data.py](extract_user_data.py)** - Extract user profile, videos, reposts, followers, and following lists via CDP network capture

### 💬 Comment Extraction
- **[extract_comments.py](extract_comments.py)** - Extract comments from a video using CDP network monitoring
- **[organize_comments.py](organize_comments.py)** - Organize comments with replies in a hierarchical structure

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Log In (Required Once)**
   ```bash
   python examples/login_setup.py
   ```

3. **Extract User Data**
   ```bash
   python examples/extract_user_data.py
   ```

4. **Extract Video Comments**
   ```bash
   python examples/extract_comments.py
   ```

## Basic Usage

```python
import asyncio
from TTScraper import TTScraper
from user import User

async def main():
    scraper = TTScraper()
    tab = await scraper.start()
    
    # Extract user data
    user = User(username="tiktok", tab=tab)
    await user.info()
    
    # Fetch followers via CDP
    raw_followers = await user.fetch_followers(tab)
    followers = User.parse_user_list(raw_followers)
    
    await scraper.close()

asyncio.run(main())
```

## What Each Script Does

| Script | Description |
|--------|-------------|
| `login_setup.py` | Opens Chrome → you log in → session saved |
| `extract_user_data.py` | Menu-driven: profile, videos, reposts, followers, following |
| `extract_comments.py` | Scrolls video page, captures `/api/comment/list/` responses |
| `organize_comments.py` | Nests replies under parent comments |

## Output Files

Scripts save data to JSON files in the project root:

- `{username}_profile.json` - User profile info
- `{username}_videos.json` - Parsed video list
- `{username}_videos_raw.json` - Raw API responses
- `{username}_followers.json` - Parsed follower list
- `{username}_following.json` - Parsed following list
- `{video_id}_comments.json` - Comments with replies

## Troubleshooting

### "Not logged in" errors
Run `login_setup.py` again. Your session may have expired.

### No API data captured
- Scroll more — TikTok lazy-loads content
- Check your network connection
- Try refreshing the page (some scripts do this automatically)

### Element not found
TikTok frequently changes their DOM. The scraper uses multiple fallback selectors, but updates may be needed.

### Rate limiting
Add delays between requests. TikTok may temporarily block aggressive scraping.

## Project Structure

```
examples/
├── login_setup.py          # Save TikTok login session
├── extract_user_data.py    # User profile + lists extraction
├── extract_comments.py     # Video comment extraction
├── organize_comments.py    # Nest replies under comments
└── README.md               # This file
```

## Notes

- All scripts use the same browser profile (`browser_profiles/Profile 1`)
- CDP captures authenticated API responses — no token spoofing needed
- Element selection is language-independent (HTML structure, not text)
