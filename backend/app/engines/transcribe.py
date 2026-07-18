"""Speech-to-text engines: cloud (OpenAI Whisper) + mock.

Pluggable per PRD.md §6.6 (FR-B2). Both return (text, language). The engine is
chosen by settings.transcribe_engine; "cloud" gracefully falls back to "mock"
if no API key is configured, so the stack always runs.
"""
from __future__ import annotations

import logging
import wave
from pathlib import Path

from ..config import settings

log = logging.getLogger("pocketscribe.transcribe")

_DEFAULT_MOCK = (
    "Okay, so this is a quick note. Um, I need to send the quarterly report to Sarah "
    "by Friday, and I should also follow up with the design team about the new logo. "
    "Ich muss noch die Rechnung bezahlen. That's it for now."
)


def _wav_seconds(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
            return int(frames / rate) if rate else 0
    except Exception:
        return 0


def _effective_engine() -> str:
    if settings.transcribe_engine == "cloud" and not settings.openai_api_key:
        log.warning("transcribe_engine=cloud but OPENAI_API_KEY is empty; using mock")
        return "mock"
    return settings.transcribe_engine


def transcribe(audio_path: Path, mock_text: str | None = None) -> tuple[str, str]:
    """Return (transcript_text, detected_language)."""
    engine = _effective_engine()
    if engine == "cloud":
        return _transcribe_cloud(audio_path)
    return _transcribe_mock(audio_path, mock_text)


def _transcribe_cloud(audio_path: Path) -> tuple[str, str]:
    from openai import OpenAI  # imported lazily so mock mode needs no dep

    client = OpenAI(api_key=settings.openai_api_key)
    with audio_path.open("rb") as f:
        resp = client.audio.transcriptions.create(
            model=settings.openai_transcribe_model,
            file=f,
            response_format="verbose_json",
        )
    text = getattr(resp, "text", "") or ""
    language = getattr(resp, "language", None) or (settings.language_hints[0] if settings.language_hints else "en")
    return text.strip(), language


def _transcribe_mock(audio_path: Path, mock_text: str | None) -> tuple[str, str]:
    # Prefer an injected transcript (sidecar written at ingest) so the
    # end-to-end demo shows *your* text flowing back to the device/dashboard.
    sidecar = audio_path.with_suffix(audio_path.suffix + ".mock.txt")
    if mock_text:
        text = mock_text
    elif sidecar.exists():
        text = sidecar.read_text(encoding="utf-8")
    else:
        secs = _wav_seconds(audio_path)
        text = _DEFAULT_MOCK + (f" (mock transcript of a {secs}s recording)" if secs else "")
    language = "de" if any(w in text.lower() for w in ("ich", "muss", "und", "nicht")) else "en"
    return text.strip(), language
