"""
Summarize scraped Instagram content using Google Gemini 1.5 Flash (free API tier).
Free tier: 1,500 requests/day | 1M tokens/day — more than enough for daily digests.

Uses the new google-genai SDK (google.generativeai is deprecated as of 2025).
"""

import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ── Gemini model config ───────────────────────────────────────────────────────
MODEL_NAME = "gemini-1.5-flash"
MAX_CAPTION_LEN = 600   # Truncate very long captions to save tokens
MAX_TRANSCRIPT_LEN = 600

# ── Prompt ─────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a sharp, concise stock market analyst assistant focused on the Indian stock market (NSE/BSE). 
Your job is to distill Instagram research content into a clean, actionable morning digest for a retail investor.
Be brutally concise — no fluff, no padding. If a post is vague, skip it. Only include what's genuinely useful.
"""

USER_PROMPT_TEMPLATE = """Below is content scraped from Instagram stock research pages in the last 24 hours.
Analyze it and generate a structured stock digest. Ignore promotional/irrelevant content.

=== RAW CONTENT ===
{content}
===================

Generate a digest with ONLY these sections (skip a section entirely if there's nothing relevant for it):

📈 *STOCKS & INDICES MENTIONED*
• [TICKER] — key insight from the post (@source_page)

📰 *KEY NEWS & EVENTS*
• Important market news, earnings, policy, macro data

💡 *ANALYST VIEWS*
• Specific bullish/bearish calls, price targets, setups (cite @page)

⚠️ *RISKS & WARNINGS*
• Stocks/sectors to be cautious about with reason

🎯 *ACTIONABLE LEVELS*
• Specific entry zones, targets, stop-losses mentioned

Keep each bullet to 1-2 lines max. Do NOT make up information not in the content.
End with one line: *Sentiment: BULLISH / BEARISH / NEUTRAL* — [one sentence reason]
"""


def build_content_string(posts: list[dict]) -> str:
    """Format all posts into a single structured string for the prompt."""
    parts = []

    for post in posts:
        caption = (post.get("caption") or "").strip()
        transcript = (post.get("transcription") or "").strip()

        # Skip if there's genuinely no content
        if not caption and not transcript:
            continue

        # Truncate to avoid token bloat
        if len(caption) > MAX_CAPTION_LEN:
            caption = caption[:MAX_CAPTION_LEN] + "..."
        if len(transcript) > MAX_TRANSCRIPT_LEN:
            transcript = transcript[:MAX_TRANSCRIPT_LEN] + "..."

        lines = [
            f"--- @{post['page']} | {post['type'].upper()} | {post['timestamp'][:10]} ---"
        ]
        if caption:
            lines.append(f"Caption: {caption}")
        if transcript:
            lines.append(f"Reel Audio: {transcript}")

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def summarize(posts: list[dict], api_key: str) -> str:
    """
    Send all scraped content to Gemini and return the formatted digest.
    Returns a 'no content' message if there are no new posts.
    """
    client = genai.Client(api_key=api_key)

    content = build_content_string(posts)

    if not content.strip():
        return (
            "📭 *No new posts found today.*\n\n"
            "All tracked pages either posted nothing new in the last 24 hours, "
            "or only posted content with no captions/audio."
        )

    logger.info(f"🤖 Sending {len(posts)} posts to Gemini ({len(content):,} chars)...")

    try:
        prompt = USER_PROMPT_TEMPLATE.format(content=content)
        response = client.models.generate_content(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
            contents=prompt,
        )
        summary = response.text.strip()
        logger.info(f"✅ Gemini summary generated ({len(summary)} chars)")
        return summary
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"Gemini summarization failed: {e}") from e
