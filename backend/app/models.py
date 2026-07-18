"""Database models (see PRD.md §8)."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Mode(str, Enum):
    quicknote = "quicknote"
    meeting = "meeting"


class SyncStatus(str, Enum):
    pending = "pending"        # audio received, not yet processed
    processing = "processing"
    done = "done"
    failed = "failed"


class Recording(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str
    mode: Mode = Mode.quicknote
    started_at: datetime = Field(default_factory=_now)
    duration_s: int = 0
    audio_path: str = ""
    language: Optional[str] = None
    sync_status: SyncStatus = SyncStatus.pending
    checksum: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recording_id: int = Field(foreign_key="recording.id")
    title: str = ""
    category: str = ""              # primary tag shown on the device
    cleaned_text: str = ""
    raw_transcript: str = ""
    summary: str = ""               # meetings only
    tags: str = ""                  # comma-separated
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    note_id: int = Field(foreign_key="note.id")
    text: str
    owner: Optional[str] = None
    due: Optional[str] = None
    status: str = "open"            # open | done
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
