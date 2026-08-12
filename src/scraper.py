"""
Instagram scraper using Instaloader.
Fetches posts and reels from specified pages within the last 24 hours.
"""

import os
import time
import random
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

import instaloader

logger = logging.getLogger(__name__)


class InstagramScraper:
    """Scrapes Instagram public pages for recent posts and reels."""

    def __init__(self, username: str, password: str, session_file: str = "state/ig_session"):
        self.username = username
        self.password = password
        self.session_file = session_file
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
        )
        self._login()

    def _login(self):
        """Log in using saved session, or fresh credentials if no session exists."""
        session_path = Path(self.session_file)

        if session_path.exists():
            try:
                self.loader.load_session_from_file(self.username, str(session_path))
                logger.info(f"✅ Loaded saved session for @{self.username}")
                return
            except Exception as e:
                logger.warning(f"Session load failed ({e}), doing fresh login...")

        logger.info(f"🔐 Logging in as @{self.username}...")
        self.loader.login(self.username, self.password)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self.loader.save_session_to_file(str(session_path))
        logger.info("✅ Logged in and session saved")

    def _download_video(self, video_url: str, shortcode: str) -> str | None:
        """Download a reel video to a temp file. Returns path or None on failure."""
        temp_dir = Path("tmp_media")
        temp_dir.mkdir(exist_ok=True)
        video_path = temp_dir / f"{shortcode}.mp4"

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )
            }
            with requests.get(video_url, headers=headers, stream=True, timeout=45) as r:
                r.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            size_kb = video_path.stat().st_size // 1024
            logger.info(f"  📥 Downloaded reel {shortcode} ({size_kb} KB)")
            return str(video_path)
        except Exception as e:
            logger.error(f"  ❌ Failed to download reel {shortcode}: {e}")
            return None

    def scrape_page(self, page_username: str, hours_back: int = 24) -> list[dict]:
        """Fetch new posts/reels from a single public page within the last N hours."""
        posts = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        try:
            profile = instaloader.Profile.from_username(
                self.loader.context, page_username
            )
            logger.info(f"  📄 @{page_username}: {profile.followers:,} followers")

            for post in profile.get_posts():
                # Posts arrive newest-first; break when we pass the time cutoff
                if post.date_utc < cutoff:
                    break

                is_reel = post.is_video
                video_path = None

                if is_reel:
                    try:
                        video_path = self._download_video(post.video_url, post.shortcode)
                    except Exception as e:
                        logger.warning(f"  ⚠️ Could not get video URL for {post.shortcode}: {e}")

                posts.append({
                    "id": post.shortcode,
                    "page": page_username,
                    "timestamp": post.date_utc.isoformat(),
                    "type": "reel" if is_reel else "post",
                    "caption": post.caption or "",
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "video_path": video_path,
                })

        except instaloader.exceptions.ProfileNotExistsException:
            logger.error(f"  ❌ @{page_username} — profile not found")
        except instaloader.exceptions.ConnectionException as e:
            logger.error(f"  ❌ Connection error for @{page_username}: {e}")
        except instaloader.exceptions.TooManyRequestsException:
            logger.error(f"  ❌ Rate-limited by Instagram while scraping @{page_username}")
        except Exception as e:
            logger.error(f"  ❌ Unexpected error scraping @{page_username}: {e}")

        return posts

    def scrape_all(self, pages: list[str], processed_ids: set, hours_back: int = 24) -> list[dict]:
        """Scrape all pages, skipping already-seen post IDs."""
        all_posts = []

        for idx, page in enumerate(pages):
            logger.info(f"\n[{idx + 1}/{len(pages)}] Scraping @{page}...")
            posts = self.scrape_page(page, hours_back)
            new = [p for p in posts if p["id"] not in processed_ids]
            skipped = len(posts) - len(new)
            all_posts.extend(new)
            logger.info(f"  → {len(new)} new | {skipped} already seen")

            if idx < len(pages) - 1:
                delay = random.uniform(4.0, 9.0)
                logger.info(f"  ⏳ Waiting {delay:.1f}s before next page...")
                time.sleep(delay)

        return all_posts
