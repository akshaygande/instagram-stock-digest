"""
Telegram Bot notification module.
Sends the daily digest (and error alerts) via the Telegram Bot API.
No heavy libraries needed — just requests.
"""

import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_MSG_LEN = 4000  # Telegram hard limit is 4096; leave a safe buffer


def _api_url(token: str, method: str) -> str:
    return TELEGRAM_API_BASE.format(token=token, method=method)


def _split_message(text: str) -> list[str]:
    """Split a message into chunks that fit within Telegram's character limit."""
    if len(text) <= MAX_MSG_LEN:
        return [text]

    chunks = []
    while text:
        if len(text) <= MAX_MSG_LEN:
            chunks.append(text)
            break
        # Prefer splitting at a newline to avoid breaking mid-sentence
        split_at = text.rfind("\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = MAX_MSG_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


def _send_chunk(token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    """Send a single message chunk to Telegram. Returns True on success."""
    url = _api_url(token, "sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        if parse_mode and "can't parse" in str(response.text).lower():
            # Markdown parsing error — retry as plain text
            logger.warning("Markdown parse error, retrying as plain text...")
            return _send_chunk(token, chat_id, text, parse_mode="")
        logger.error(f"Telegram HTTP error: {e} | Response: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_message(token: str, chat_id: str, text: str) -> bool:
    """
    Send a (potentially long) message to a Telegram chat.
    Automatically splits into multiple messages if needed.
    Returns True if all chunks were sent successfully.
    """
    chunks = _split_message(text)
    all_success = True

    for i, chunk in enumerate(chunks):
        logger.info(f"📨 Sending Telegram message {i + 1}/{len(chunks)}...")
        ok = _send_chunk(token, chat_id, chunk)
        if ok:
            logger.info(f"  ✅ Chunk {i + 1} sent")
        else:
            logger.error(f"  ❌ Chunk {i + 1} failed")
            all_success = False

    return all_success


def send_error_alert(token: str, chat_id: str, error_msg: str):
    """Send a brief error alert so you're never silently left without a digest."""
    safe_error = error_msg[:400]  # Keep alert short
    text = (
        "⚠️ *Stock Digest — Run Failed*\n\n"
        f"```\n{safe_error}\n```\n\n"
        "_Check GitHub Actions logs for details. Will retry tomorrow._"
    )
    _send_chunk(token, chat_id, text)
    logger.info("⚠️ Error alert sent to Telegram")
