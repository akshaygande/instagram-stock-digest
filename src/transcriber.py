"""
Audio transcription using OpenAI Whisper (open-source, runs on CPU — no API cost).
Uses the 'tiny' model for speed on GitHub Actions free runners.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-load the model once and reuse across all transcriptions
_model = None


def _get_model():
    """Load and cache the Whisper tiny model."""
    global _model
    if _model is None:
        import whisper  # Imported lazily to avoid slow startup when not needed
        logger.info("🔊 Loading Whisper 'tiny' model (first-time load, ~40 MB)...")
        _model = whisper.load_model("tiny")
        logger.info("✅ Whisper model ready")
    return _model


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe a video/audio file and return the transcript text.
    Cleans up the temp file after transcription.
    """
    if not audio_path:
        return ""

    path = Path(audio_path)
    if not path.exists():
        logger.warning(f"Audio file not found: {audio_path}")
        return ""

    try:
        model = _get_model()
        file_size_kb = path.stat().st_size // 1024
        logger.info(f"  🎙️ Transcribing {path.name} ({file_size_kb} KB)...")

        result = model.transcribe(str(path), language=None, fp16=False)
        text = result["text"].strip()

        preview = text[:100] + "..." if len(text) > 100 else text
        logger.info(f"  ✅ Transcript: \"{preview}\"")
        return text

    except Exception as e:
        logger.error(f"  ❌ Transcription failed for {audio_path}: {e}")
        return ""
    finally:
        # Always clean up temp media files to save disk space
        try:
            path.unlink(missing_ok=True)
            logger.debug(f"  🗑️ Cleaned up {path.name}")
        except Exception:
            pass


def transcribe_posts(posts: list[dict]) -> list[dict]:
    """
    Add transcription text to all reel posts that have a downloaded video.
    Modifies the list in place and returns it.
    """
    reels = [p for p in posts if p.get("type") == "reel" and p.get("video_path")]
    logger.info(f"\n🎬 Transcribing {len(reels)} reel(s)...")

    for post in reels:
        post["transcription"] = transcribe_audio(post["video_path"])
        post["video_path"] = None  # Clear path reference after processing

    # Ensure all posts have a transcription key (empty string for non-reels)
    for post in posts:
        post.setdefault("transcription", "")

    return posts
