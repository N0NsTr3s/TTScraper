"""
Comment Extraction Example

Extracts all comments **and replies** (with user details) from a TikTok video
using TikTok's comment APIs captured via CDP network interception.

Phase 1 – captures ``/api/comment/list/``  (top-level comments)
Phase 2 – captures ``/api/comment/list/reply/`` (reply threads)

Uses nodriver (async CDP).
"""

import asyncio
import logging
import sys
import os
import json
import re
import traceback
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TTScraper import TTScraper
from video import Video


# ── Logging ──────────────────────────────────────────────────────────

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('comment_extraction.log', encoding='utf-8')
        ]
    )
    return logging.getLogger("CommentExtraction")


# ── Extraction ───────────────────────────────────────────────────────

async def extract_comments_api(video_url, tab, fetch_replies=True):
    """
    Extract comments + replies via CDP network capture of TikTok's
    ``/api/comment/list/`` and ``/api/comment/list/reply/`` endpoints.

    Returns ``(raw_comments, parsed_comments)`` where *parsed_comments*
    is a flat list containing both top-level comments and replies
    (replies have ``is_reply=True`` and ``parent_comment_id`` set).
    """
    logger = logging.getLogger("CommentExtraction")

    try:
        logger.info(f"💬 Extracting comments via CDP capture: {video_url}")
        video = Video(url=video_url, tab=tab)

        # fetch_comments now handles both phases internally
        raw_comments = await video.fetch_comments(
            tab=tab,
            fetch_replies=fetch_replies,
        )

        if not raw_comments:
            logger.warning("⚠️  No comments returned from API")
            return [], []

        logger.info(f"✅ Fetched {len(raw_comments)} raw items (comments + replies)")

        # Parse into clean flat records with user details
        parsed = video.parse_comments(raw_comments)
        logger.info(f"✅ Parsed {len(parsed)} records")

        return raw_comments, parsed

    except Exception as e:
        logger.error(f"❌ Error in comment extraction: {e}", exc_info=True)
        return [], []


# ── Structuring helpers ──────────────────────────────────────────────

def group_comments_with_replies(parsed_comments):
    """
    Group a flat list of parsed records into a list of top-level comment
    dicts, each with a ``replies`` sub-list containing its child replies.

    Returns ``(grouped, orphan_replies)`` where *orphan_replies* are
    replies whose parent comment was not found (e.g. deleted/hidden).
    """
    top_level = []
    replies = []

    for c in parsed_comments:
        if c.get("is_reply"):
            replies.append(c)
        else:
            top_level.append(c)

    # Index top-level comments by comment_id
    by_id = {c["comment_id"]: c for c in top_level}

    # Attach a mutable replies list to each top-level comment
    for c in top_level:
        c["replies"] = []

    orphan_replies = []
    for r in replies:
        parent_id = r.get("parent_comment_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["replies"].append(r)
        else:
            orphan_replies.append(r)

    return top_level, orphan_replies


# ── Display helpers ──────────────────────────────────────────────────

def display_parsed_comments(parsed_comments):
    """Pretty-print parsed comments with nested replies."""
    grouped, orphans = group_comments_with_replies(parsed_comments)

    comment_num = 0
    for c in grouped:
        comment_num += 1
        label = f" [{c['label_text']}]" if c.get("label_text") else ""
        print(f"\n{'─' * 50}")
        print(f"Comment {comment_num}:")
        print(f"  User:      @{c.get('username') or '?'}{label} ({c.get('nickname') or '?'})")
        print(f"  Profile:   {c.get('user_profile_url') or 'N/A'}")
        print(f"  Text:      {c.get('text') or '(no text)'}")
        print(f"  Time:      {c.get('create_time_formatted') or 'N/A'}")
        print(f"  Likes:     {c.get('digg_count', 0):,}")
        print(f"  Replies:   {c.get('reply_count', 0)}")
        if c.get("has_images"):
            print(f"  Images:    {len(c.get('image_urls', []))} attached")

        for ri, r in enumerate(c.get("replies", []), 1):
            rlabel = f" [{r['label_text']}]" if r.get("label_text") else ""
            print(f"\n  ↳ Reply {ri}:")
            print(f"    User:    @{r.get('username') or '?'}{rlabel} ({r.get('nickname') or '?'})")
            print(f"    Profile: {r.get('user_profile_url') or 'N/A'}")
            print(f"    Text:    {r.get('text') or '(no text)'}")
            print(f"    Time:    {r.get('create_time_formatted') or 'N/A'}")
            print(f"    Likes:   {r.get('digg_count', 0):,}")
            if r.get("has_images"):
                print(f"    Images:  {len(r.get('image_urls', []))} attached")

    if orphans:
        print(f"\n{'─' * 50}")
        print(f"⚠️  {len(orphans)} orphan replies (parent comment not found):")
        for r in orphans:
            rlabel = f" [{r['label_text']}]" if r.get("label_text") else ""
            print(f"  ↳ @{r.get('username') or '?'}{rlabel}: {(r.get('text') or '')[:80]}")


def print_summary(parsed_comments):
    """Print aggregate statistics for parsed comments."""
    top_level = [c for c in parsed_comments if not c.get("is_reply")]
    replies = [c for c in parsed_comments if c.get("is_reply")]

    total_likes = sum(c.get("digg_count", 0) for c in parsed_comments)
    unique_users = {c.get("username") for c in parsed_comments if c.get("username")}

    # Top liked across all (comments + replies)
    top = sorted(parsed_comments, key=lambda x: x.get("digg_count", 0), reverse=True)[:5]

    print(f"\n{'=' * 60}")
    print("📊 Summary")
    print(f"   Top-level comments: {len(top_level)}")
    print(f"   Replies:            {len(replies)}")
    print(f"   Total items:        {len(parsed_comments)}")
    print(f"   Unique authors:     {len(unique_users)}")
    print(f"   Total likes:        {total_likes:,}")

    if top and top[0].get("digg_count", 0) > 0:
        print("\n   🏆 Top liked:")
        for tc in top:
            if tc.get("digg_count", 0) == 0:
                break
            kind = "↳" if tc.get("is_reply") else "💬"
            label = f" [{tc['label_text']}]" if tc.get("label_text") else ""
            text_preview = (tc["text"][:55] + "...") if len(tc.get("text", "")) > 55 else tc.get("text", "")
            print(f"      {tc['digg_count']:>5,} ❤️  {kind} @{tc.get('username', '?')}{label}: {text_preview}")


# ── File I/O ─────────────────────────────────────────────────────────

def save_json(data, filename):
    """Write *data* to a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.getLogger("CommentExtraction").info(f"💾 Saved → {filename}")


def make_output_filename(video_url, label):
    """Build a safe output filename from the video URL and a label."""
    video_id = video_url.rstrip('/').split('/')[-1].split('?')[0]
    video_id = re.sub(r'[<>:"/\\|?*]', '_', video_id) or 'unknown'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"comments_{label}_{video_id}_{timestamp}.json"


def build_structured_output(video_url, parsed_comments):
    """
    Build a nested JSON structure with replies grouped under their
    parent comments, suitable for export.
    """
    grouped, orphans = group_comments_with_replies(parsed_comments)

    top_level = [c for c in parsed_comments if not c.get("is_reply")]
    replies = [c for c in parsed_comments if c.get("is_reply")]

    return {
        "video_url": video_url,
        "extracted_at": datetime.now().isoformat(),
        "extraction_method": "cdp_network_capture",
        "stats": {
            "total_comments": len(top_level),
            "total_replies": len(replies),
            "total_items": len(parsed_comments),
            "orphan_replies": len(orphans),
        },
        "comments": grouped,          # each comment has a "replies" sub-list
        "orphan_replies": orphans,     # replies whose parent wasn't captured
    }


# ── Main ─────────────────────────────────────────────────────────────

async def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("🚀 Starting Comment Extraction Example")

    print("\n💬 TikTok Comment + Reply Extraction")
    print("=" * 50)

    video_url = input("Enter TikTok video URL: ").strip()

    if not video_url:
        print("❌ No URL provided.")
        return

    if not ('tiktok.com' in video_url and '/video/' in video_url):
        print("❌ Invalid TikTok video URL format.")
        return

    print("\nInclude replies? (Y/n): ", end="")
    reply_choice = input().strip().lower()
    fetch_replies = reply_choice != 'n'

    scraper = None
    try:
        # ── Launch browser ───────────────────────────────────────
        logger.info("🔧 Initializing TTScraper...")
        scraper = TTScraper()
        tab = await scraper.start_browser()

        # ── Extract comments + replies ───────────────────────────
        print("\n🔗 Fetching comments" + (" + replies" if fetch_replies else "") + "...")
        raw_comments, parsed_comments = await extract_comments_api(
            video_url, tab, fetch_replies=fetch_replies
        )

        if parsed_comments:
            display_parsed_comments(parsed_comments)
            print_summary(parsed_comments)

            # Save structured (nested) output
            structured = build_structured_output(video_url, parsed_comments)
            parsed_file = make_output_filename(video_url, "structured")
            save_json(structured, parsed_file)
            print(f"\n💾 Structured output saved to: {parsed_file}")

            # Save raw API payloads for debugging
            raw_file = make_output_filename(video_url, "raw")
            save_json(raw_comments, raw_file)
            print(f"💾 Raw API data saved to:      {raw_file}")
        else:
            print("⚠️  No comments captured")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        traceback.print_exc()

    finally:
        if scraper:
            scraper.close()
            logger.info("🧹 Browser closed")


if __name__ == "__main__":
    asyncio.run(main())
