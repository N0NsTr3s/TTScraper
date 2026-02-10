"""
TikTok Login Setup

Opens Chrome and navigates to TikTok's login page so you can
sign in manually.  Once logged in, cookies are saved to the
browser profile directory and will persist across future runs.

Press Enter in the terminal when you're done logging in to close
the browser cleanly.
"""

import asyncio
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from TTScraper import TTScraper


async def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║       TikTok Account Login Setup             ║")
    print("╚══════════════════════════════════════════════╝\n")

    scraper = TTScraper()
    tab = await scraper.start_browser(url="https://www.tiktok.com/login")

    print("Chrome is open on the TikTok login page.")
    print("Log into your account, then come back here.\n")
    print("Press Enter when you're done...")

    # Keep the event loop alive while the user logs in.
    # We run the blocking input() in a thread so the browser stays responsive.
    await asyncio.get_event_loop().run_in_executor(None, input)

    # Quick check: see if we landed on a logged-in page
    try:
        current_url = await tab.evaluate("window.location.href")
        print(f"\nCurrent page: {current_url}")

        is_logged_in = await tab.evaluate(
            "!!document.cookie.match(/sessionid|sid_tt/)"
        )
        if is_logged_in:
            print("✅ Login detected — session cookies are saved.")
        else:
            print("⚠️  Could not confirm login. If you logged in, "
                  "cookies should still be saved in the browser profile.")
    except Exception:
        pass

    scraper.close()
    print("\nBrowser closed. Your session is stored in the browser profile.")
    print("Future scraper runs will reuse this session automatically.\n")


if __name__ == "__main__":
    asyncio.run(main())
