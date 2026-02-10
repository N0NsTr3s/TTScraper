"""
Batch Video Extraction Example

This example demonstrates how to process multiple TikTok videos efficiently
with error handling, progress tracking, and data aggregation.
Uses nodriver (async CDP).
"""

import asyncio
import logging
import sys
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

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
            logging.FileHandler('batch_extraction.log', encoding='utf-8')
        ]
    )
    return logging.getLogger("BatchExtraction")


class BatchVideoExtractor:
    """Class for batch video data extraction with error handling and progress tracking."""

    def __init__(self, tab):
        self.tab = tab
        self.logger = logging.getLogger("BatchExtraction")
        self.results = []
        self.errors = []
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }

    async def extract_single_video(self, video_url: str, delay: float = 2.0) -> Dict:
        """Extract data from a single video with error handling."""
        try:
            self.logger.info(f"Processing: {video_url}")

            video = Video(url=video_url, tab=self.tab)

            # Extract video information (async)
            video_data = await video.info()

            result = {
                'url': video_url,
                'extraction_timestamp': datetime.now().isoformat(),
                'success': True,
                'video_id': getattr(video, 'id', None),
                'stats': video.stats if hasattr(video, 'stats') and video.stats else None,
                'create_time': video.create_time.isoformat() if hasattr(video, 'create_time') and video.create_time else None,
                'raw_data': video_data
            }

            self.stats['successful'] += 1
            self.logger.info(f"Successfully processed: {video_url}")

            if delay > 0:
                await asyncio.sleep(delay)

            return result

        except Exception as e:
            error_result = {
                'url': video_url,
                'extraction_timestamp': datetime.now().isoformat(),
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

            self.stats['failed'] += 1
            self.errors.append(error_result)
            self.logger.error(f"Failed to process {video_url}: {e}")

            return error_result

    async def extract_batch(self, video_urls: List[str], delay: float = 2.0, save_progress: bool = True) -> Dict:
        """Extract data from multiple videos."""
        self.stats['start_time'] = datetime.now()
        total_videos = len(video_urls)

        self.logger.info(f"🚀 Starting batch extraction of {total_videos} videos")

        for i, video_url in enumerate(video_urls, 1):
            self.logger.info(f"📹 Processing video {i}/{total_videos}")

            result = await self.extract_single_video(video_url, delay)
            self.results.append(result)
            self.stats['total_processed'] += 1

            if save_progress and i % 5 == 0:
                self._save_progress(i, total_videos)

            progress = (i / total_videos) * 100
            self.logger.info(f"📊 Progress: {progress:.1f}% ({i}/{total_videos})")

        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']

        self.logger.info(f"✅ Batch extraction completed in {duration}")
        self.logger.info(f"📊 Results: {self.stats['successful']} successful, {self.stats['failed']} failed")

        return self._get_summary()

    def _save_progress(self, current: int, total: int):
        """Save current progress to file."""
        progress_data = {
            'timestamp': datetime.now().isoformat(),
            'progress': f"{current}/{total}",
            'stats': self.stats.copy(),
            'results_so_far': len(self.results),
            'errors_so_far': len(self.errors)
        }

        with open('batch_progress.json', 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)

    def _get_summary(self) -> Dict:
        """Get extraction summary."""
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        return {
            'extraction_summary': {
                'total_videos': len(self.results),
                'successful_extractions': self.stats['successful'],
                'failed_extractions': self.stats['failed'],
                'success_rate': (self.stats['successful'] / max(1, self.stats['total_processed'])) * 100,
                'duration_seconds': duration,
                'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
                'end_time': self.stats['end_time'].isoformat() if self.stats['end_time'] else None
            },
            'results': self.results,
            'errors': self.errors
        }

    def save_results(self, filename: Optional[str] = None) -> str:
        """Save only raw results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_extraction_results_{timestamp}.json"

        raw_results = {
            'results': self.results,
            'timestamp': datetime.now().isoformat(),
            'total_videos_processed': len(self.results)
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(raw_results, f, indent=2, ensure_ascii=False)

        self.logger.info(f"💾 Results saved to: {filename}")
        return filename

    def get_analytics(self) -> Dict:
        """Get analytics from extracted data."""
        if not self.results:
            return {'error': 'No data to analyze'}

        successful_results = [r for r in self.results if r.get('success', False)]

        if not successful_results:
            return {'error': 'No successful extractions to analyze'}

        analytics = {
            'total_videos_analyzed': len(successful_results),
            'engagement_stats': {
                'total_likes': 0,
                'total_shares': 0,
                'total_comments': 0,
                'total_views': 0,
                'total_collects': 0,
                'total_reposts': 0
            },
            'video_ids': []
        }

        for result in successful_results:
            if result.get('video_id'):
                analytics['video_ids'].append(result['video_id'])

            stats = result.get('stats', {})
            if stats:
                for key, analytics_key in [
                    ('diggCount', 'total_likes'),
                    ('shareCount', 'total_shares'),
                    ('commentCount', 'total_comments'),
                    ('playCount', 'total_views'),
                    ('collectCount', 'total_collects'),
                    ('repostCount', 'total_reposts'),
                ]:
                    val = stats.get(key, 0)
                    analytics['engagement_stats'][analytics_key] += int(val) if str(val).isdigit() else 0

        total_videos = len(successful_results)
        if total_videos > 0:
            analytics['average_engagement'] = {
                'avg_likes': analytics['engagement_stats']['total_likes'] // total_videos,
                'avg_shares': analytics['engagement_stats']['total_shares'] // total_videos,
                'avg_comments': analytics['engagement_stats']['total_comments'] // total_videos,
                'avg_views': analytics['engagement_stats']['total_views'] // total_videos,
                'avg_collects': analytics['engagement_stats']['total_collects'] // total_videos,
                'avg_reposts': analytics['engagement_stats']['total_reposts'] // total_videos,
            }

        return analytics


def load_urls_from_file(filepath: str) -> List[str]:
    """Load video URLs from a text file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and 'tiktok.com' in line]
        return urls
    except Exception as e:
        logging.error(f"Error loading URLs from file: {e}")
        return []


async def main():
    """Main example function."""
    logger = setup_logging()
    logger.info("🚀 Starting Batch Video Extraction Example")

    print("\n📹 TikTok Batch Video Extraction")
    print("=" * 40)

    print("Choose input method:")
    print("1. Enter URLs manually")
    print("2. Load URLs from file")

    choice = input("Enter choice (1-2): ").strip()

    video_urls = []

    if choice == "1":
        print("\nEnter TikTok video URLs (one per line, empty line to finish):")
        while True:
            url = input("URL: ").strip()
            if not url:
                break
            if 'tiktok.com' in url and '/video/' in url:
                video_urls.append(url)
            else:
                print("⚠️ Invalid TikTok URL format")

    elif choice == "2":
        filepath = input("Enter file path: ").strip()
        video_urls = load_urls_from_file(filepath)
        print(f"📄 Loaded {len(video_urls)} URLs from file")

    else:
        print("❌ Invalid choice")
        return

    if not video_urls:
        print("❌ No valid URLs provided")
        return

    try:
        delay = float(input("Delay between requests (seconds, default 2.0): ") or "2.0")
    except ValueError:
        delay = 2.0

    scraper = None
    try:
        # Initialize TTScraper
        logger.info("🔧 Initializing TTScraper...")
        scraper = TTScraper()
        tab = await scraper.start_browser()

        # Create batch extractor
        extractor = BatchVideoExtractor(tab)

        # Start batch extraction
        print(f"\n🚀 Starting batch extraction of {len(video_urls)} videos...")
        results = await extractor.extract_batch(video_urls, delay=delay)

        # Save results
        results_file = extractor.save_results()

        # Save analytics separately
        analytics = extractor.get_analytics()
        analytics_file = f"batch_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analytics_file, 'w', encoding='utf-8') as f:
            json.dump(analytics, f, indent=2, ensure_ascii=False)

        # Show raw data for each video
        print(f"\n📊 Raw Data for Processed Videos:")
        print("=" * 50)

        for i, result in enumerate(extractor.results, 1):
            print(f"\n--- Video {i} ---")
            print(f"URL: {result.get('url', 'N/A')}")
            print(f"Status: {'✅ Success' if result.get('success') else '❌ Failed'}")

            if result.get('success'):
                print(f"Video ID: {result.get('video_id', 'N/A')}")
                print("Raw Data Preview:")
                raw_data = result.get('raw_data', {})
                if raw_data:
                    raw_data_str = json.dumps(raw_data, indent=2, ensure_ascii=False)
                    if len(raw_data_str) > 500:
                        print(raw_data_str[:500] + "... (truncated in display)")
                    else:
                        print(raw_data_str)
                else:
                    print("No raw data available")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")

            print("-" * 50)

        print(f"\n💾 Complete raw data saved to: {results_file}")
        print(f"💾 Analytics saved separately to: {analytics_file}")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"❌ An error occurred: {e}")

    finally:
        if scraper:
            scraper.close()
            logger.info("🧹 Browser closed successfully")


if __name__ == "__main__":
    asyncio.run(main())
