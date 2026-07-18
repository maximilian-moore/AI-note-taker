"""Database models (see PRD.md §8)."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


class Mode(str, Enum):
    quicknote = "quicknote"
    meeting = "meeting"


class SyncStatus(str, Enum):
    received = "received"      # audio reassembled, not yet processed
    processing = "processing"  # transcription/enrichment running
    done = "done"              # transcript + results available
    failed = "failed"          # processing errored (retryable)


class Recording(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    uid: str = Field(index=True, unique=True)   # device-generated stable id
    device_id: str = ""
    mode: Mode = Mode.quicknote
    started_at: datetime = Field(default_factory=now)
    duration_s: int = 0
    audio_path: str = ""
    language: Optional[str] = None
    status: SyncStatus = SyncStatus.received
    error: Optional[str] = None
    checksum: Optional[str] = None
    created_at: datetime = Field(default_factory=now)
    processed_at: Optional[datetime] = None


class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recording_id: int = Field(foreign_key="recording.id", index=True)
    uid: str = Field(index=True)          # mirrors recording.uid for device lookups
    title: str = ""
    category: str = ""                    # primary tag shown on the device
    cleaned_text: str = ""
    raw_transcript: str = ""
    summary: str = ""                     # meetings only
    tags: str = ""                        # comma-separated
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    note_id: int = Field(foreign_key="note.id", index=True)
    text: str
    owner: Optional[str] = None
    due: Optional[str] = None
    status: str = "open"                  # open | done
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
