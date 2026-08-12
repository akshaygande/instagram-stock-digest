"""
Main orchestrator for the Instagram Stock Digest system.

Flow:
  1. Load config (pages list) and state (already-processed post IDs)
  2. Scrape all pages with Instaloader
  3. Transcribe any reels with Whisper
  4. Summarize everything with Gemini 1.5 Flash
  5. Send the digest to Telegram
  6. Save updated state back to disk (committed to repo by CI)
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from src.notifier import send_error_alert, send_message
from src.scraper import InstagramScraper
from src.summarizer import summarize
from src.transcriber import transcribe_posts

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

# ── File paths ────────────────────────────────────────────────────────────────
PAGES_FILE = "config/pages.txt"
STATE_FILE = "state/processed_posts.json"
SESSION_FILE = "state/ig_session"
MAX_TRACKED_IDS = 1000  # Cap to prevent unbounded state file growth


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_env(key: str) -> str:
    """Return a required environment variable, or exit with a clear error."""
    val = os.environ.get(key, "").strip()
    if not val:
        raise EnvironmentError(f"Required environment variable not set: {key}")
    return val


def load_pages() -> list[str]:
    """Load Instagram page usernames from config/pages.txt."""
    path = Path(PAGES_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"{PAGES_FILE} not found. "
            "Create it with one Instagram username per line."
        )

    pages = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("@").lower()
        if line and not line.startswith("#"):
            pages.append(line)

    if not pages:
        raise ValueError(f"{PAGES_FILE} exists but contains no usernames.")

    logger.info(f"📋 Loaded {len(pages)} pages: {', '.join('@' + p for p in pages)}")
    return pages


def load_state() -> dict:
    """Load the persisted set of already-processed post IDs."""
    path = Path(STATE_FILE)
    if not path.exists():
        return {"processed_ids": [], "last_run": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not read state file ({e}). Starting fresh.")
        return {"processed_ids": [], "last_run": None}


def save_state(state: dict):
    """Write the updated state back to disk."""
    # Trim old IDs to keep the file manageable
    ids = state.get("processed_ids", [])
    if len(ids) > MAX_TRACKED_IDS:
        ids = ids[-MAX_TRACKED_IDS:]
    state["processed_ids"] = ids
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    path = Path(STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"💾 State saved ({len(ids)} IDs tracked)")


def build_header(post_count: int, page_count: int) -> str:
    """Format the digest header block."""
    ist_offset = "+05:30"
    now_str = datetime.now().strftime("%d %b %Y")
    return (
        f"📊 *STOCK DIGEST — {now_str}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 {post_count} new post(s) from {page_count} page(s)\n\n"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("🚀  Instagram Stock Digest — Run Starting")
    logger.info("=" * 60)

    # 1. Load secrets ──────────────────────────────────────────────
    try:
        ig_user = get_env("INSTAGRAM_USERNAME")
        ig_pass = get_env("INSTAGRAM_PASSWORD")
        gemini_key = get_env("GEMINI_API_KEY")
        tg_token = get_env("TELEGRAM_BOT_TOKEN")
        tg_chat = get_env("TELEGRAM_CHAT_ID")
    except EnvironmentError as e:
        logger.critical(str(e))
        sys.exit(1)

    # 2. Load config & state ───────────────────────────────────────
    try:
        pages = load_pages()
        state = load_state()
        processed_ids = set(state.get("processed_ids", []))
        logger.info(f"📦 {len(processed_ids)} post IDs already processed")
    except Exception as e:
        logger.critical(f"Failed to load config/state: {e}")
        send_error_alert(tg_token, tg_chat, str(e))
        sys.exit(1)

    # 3. Scrape Instagram ──────────────────────────────────────────
    try:
        scraper = InstagramScraper(ig_user, ig_pass, SESSION_FILE)
        posts = scraper.scrape_all(pages, processed_ids, hours_back=24)
        logger.info(f"\n✅ Scraped {len(posts)} new posts in total")
    except Exception as e:
        msg = f"Scraping failed: {e}"
        logger.error(f"{msg}\n{traceback.format_exc()}")
        send_error_alert(tg_token, tg_chat, msg)
        sys.exit(1)

    # 4. Transcribe Reels ──────────────────────────────────────────
    if any(p["type"] == "reel" and p.get("video_path") for p in posts):
        try:
            posts = transcribe_posts(posts)
        except Exception as e:
            # Non-fatal: log and continue without transcriptions
            logger.error(f"Transcription step failed (non-fatal): {e}")
            for p in posts:
                p.setdefault("transcription", "")
    else:
        for p in posts:
            p.setdefault("transcription", "")
        logger.info("No reels to transcribe today.")

    # 5. Summarize with Gemini ─────────────────────────────────────
    try:
        summary = summarize(posts, gemini_key)
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        summary = "⚠️ AI summary could not be generated. Check GitHub Actions logs."

    # 6. Build & send Telegram message ─────────────────────────────
    header = build_header(len(posts), len(pages))
    full_message = header + summary

    logger.info(f"\n📨 Sending digest ({len(full_message)} chars) to Telegram...")
    ok = send_message(tg_token, tg_chat, full_message)
    if ok:
        logger.info("✅ Digest delivered successfully!")
    else:
        logger.error("❌ Telegram delivery failed")

    # 7. Persist updated state ─────────────────────────────────────
    new_ids = [p["id"] for p in posts]
    state["processed_ids"] = list(processed_ids) + new_ids
    save_state(state)

    logger.info("=" * 60)
    logger.info(f"🏁  Done. {len(posts)} post(s) processed and sent.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
