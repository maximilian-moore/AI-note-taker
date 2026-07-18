"""Filesystem storage: buffer upload chunks, reassemble into one audio file.

Chunks are stored per-recording so an interrupted upload can resume. On the
final chunk we concatenate in sequence order into DATA_DIR/audio/<uid>.<ext>.

WAV chunks get special handling: only the first chunk keeps its 44-byte header,
so the reassembled file is a single valid WAV. Any other container (e.g. raw or
opus) is treated as an opaque byte stream and simply concatenated.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import settings

_DATA = Path(settings.data_dir)
_INCOMING = _DATA / "incoming"
_AUDIO = _DATA / "audio"
_WAV_HEADER_BYTES = 44

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe(uid: str) -> str:
    """Prevent path traversal from a device-supplied uid."""
    cleaned = _SAFE.sub("_", uid)
    return cleaned or "unknown"


def chunk_dir(uid: str) -> Path:
    d = _INCOMING / _safe(uid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_chunk(uid: str, seq: int, data: bytes) -> None:
    (chunk_dir(uid) / f"{int(seq):06d}.part").write_bytes(data)


def has_chunk(uid: str, seq: int) -> bool:
    return (chunk_dir(uid) / f"{int(seq):06d}.part").exists()


def assemble(uid: str, ext: str = "wav") -> Path:
    """Concatenate stored chunks in order; return the final audio path."""
    _AUDIO.mkdir(parents=True, exist_ok=True)
    out = _AUDIO / f"{_safe(uid)}.{ext}"
    parts = sorted(chunk_dir(uid).glob("*.part"))
    is_wav = ext.lower() == "wav"
    with out.open("wb") as w:
        for i, part in enumerate(parts):
            raw = part.read_bytes()
            if is_wav and i > 0 and len(raw) > _WAV_HEADER_BYTES:
                raw = raw[_WAV_HEADER_BYTES:]  # strip duplicate WAV header
            w.write(raw)
    return out


def audio_path(uid: str, ext: str = "wav") -> Path:
    return _AUDIO / f"{_safe(uid)}.{ext}"


def cleanup_chunks(uid: str) -> None:
    d = chunk_dir(uid)
    for p in d.glob("*.part"):
        p.unlink(missing_ok=True)
    try:
        d.rmdir()
    except OSError:
        pass
