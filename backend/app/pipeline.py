"""Processing pipeline: transcribe -> enrich -> persist Note/Todos (PRD §9)."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import select

from .db import session_scope
from .models import Recording, Note, Todo, SyncStatus, now
from .engines import transcribe as stt
from .engines import enrich as llm

log = logging.getLogger("pocketscribe.pipeline")


def process_recording(uid: str) -> None:
    """Run the full pipeline for one recording. Safe to retry."""
    with session_scope() as s:
        rec = s.exec(select(Recording).where(Recording.uid == uid)).first()
        if rec is None:
            log.error("process: no recording %s", uid)
            return
        rec.status = SyncStatus.processing
        rec.error = None
        s.add(rec)
        audio_path = Path(rec.audio_path)
        mode = rec.mode.value

    try:
        transcript, language = stt.transcribe(audio_path)
        result = llm.enrich(transcript, mode, language)
    except Exception as e:
        log.exception("processing failed for %s: %s", uid, e)
        with session_scope() as s:
            rec = s.exec(select(Recording).where(Recording.uid == uid)).first()
            if rec:
                rec.status = SyncStatus.failed
                rec.error = str(e)[:500]
                s.add(rec)
        return

    with session_scope() as s:
        rec = s.exec(select(Recording).where(Recording.uid == uid)).first()
        if rec is None:
            return
        rec.language = language
        rec.status = SyncStatus.done
        rec.processed_at = now()
        s.add(rec)

        # replace any prior note/todos for idempotent re-processing
        old = s.exec(select(Note).where(Note.recording_id == rec.id)).all()
        for n in old:
            for td in s.exec(select(Todo).where(Todo.note_id == n.id)).all():
                s.delete(td)
            s.delete(n)
        s.flush()

        note = Note(
            recording_id=rec.id, uid=rec.uid,
            title=result["title"], category=result["category"],
            cleaned_text=result["cleaned_text"], raw_transcript=transcript,
            summary=result["summary"], tags=",".join(result["tags"]),
        )
        s.add(note)
        s.flush()
        for t in result["todos"]:
            s.add(Todo(note_id=note.id, text=t["text"], owner=t.get("owner"), due=t.get("due")))
    log.info("processed %s: %d todos", uid, len(result["todos"]))
