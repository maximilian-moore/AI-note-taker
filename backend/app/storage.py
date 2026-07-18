"""Filesystem storage: buffer upload chunks, reassemble into one audio file.

Contract (shared with firmware + tools/device_sim.py): the device records ONE
audio file per recording and uploads it as ordered byte-range chunks. Chunk 0
carries the file header (e.g. the 44-byte WAV header); every later chunk is a
raw continuation of the same file. Reassembly is therefore a verbatim
concatenation in sequence order — no per-chunk header handling — so the
reassembled file is byte-identical to what the device recorded.

Chunks are stored per-recording so an interrupted upload can resume by seq.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import settings

_DATA = Path(settings.data_dir)
_INCOMING = _DATA / "incoming"
_AUDIO = _DATA / "audio"

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
    """Concatenate stored chunks verbatim in seq order; return the audio path."""
    _AUDIO.mkdir(parents=True, exist_ok=True)
    out = _AUDIO / f"{_safe(uid)}.{ext}"
    parts = sorted(chunk_dir(uid).glob("*.part"))
    with out.open("wb") as w:
        for part in parts:
            w.write(part.read_bytes())
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
