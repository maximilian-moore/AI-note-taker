"""
PocketScribe backend — API + dashboard host.

Runs end-to-end with NO API keys (engines default to "mock"); flip
TRANSCRIBE_ENGINE / LLM_ENGINE to "cloud" in .env for real Whisper + Claude.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    FastAPI, Depends, Header, HTTPException, UploadFile, File, Form,
    BackgroundTasks, Request, Response, Body,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from .config import settings
from .db import init_db, session_scope
from .models import Recording, Note, Todo, Mode, SyncStatus, now
from . import storage, auth
from .pipeline import process_recording

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pocketscribe")

app = FastAPI(title="PocketScribe", version="0.1.0")

DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"

# Initialize the schema at import time so it's ready under uvicorn, gunicorn,
# and the test client alike (startup events don't fire without a lifespan ctx).
init_db()
log.info("PocketScribe up. transcribe=%s llm=%s", settings.transcribe_engine, settings.llm_engine)


# --- health ------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "transcribe_engine": settings.transcribe_engine,
        "llm_engine": settings.llm_engine,
        "cloud_ready": {
            "transcribe": bool(settings.openai_api_key),
            "llm": bool(settings.anthropic_api_key),
        },
    }


# =============================================================================
# DEVICE API (pairing-token auth)
# =============================================================================
@app.post("/ingest")
async def ingest(
    background: BackgroundTasks,
    chunk: UploadFile = File(...),
    device_id: str = Form(...),
    recording_uid: str = Form(...),
    mode: str = Form("quicknote"),
    seq: int = Form(0),
    final: bool = Form(False),
    audio_ext: str = Form("wav"),
    duration_s: int = Form(0),
    started_at: str | None = Form(None),
    checksum: str = Form(""),
    mock_transcript: str | None = Form(None),
    _: None = Depends(auth.require_device),
) -> dict:
    """Accept a chunked audio upload (FR-B1). Idempotent on (uid, seq).
    On the final chunk: reassemble, create the Recording, enqueue processing.
    """
    data = await chunk.read()
    storage.save_chunk(recording_uid, seq, data)

    if not final:
        return {"received": True, "recording_uid": recording_uid, "seq": seq, "final": False}

    audio = storage.assemble(recording_uid, ext=audio_ext)
    if mock_transcript:  # lets the simulator inject known text for mock STT
        audio.with_suffix(audio.suffix + ".mock.txt").write_text(mock_transcript, encoding="utf-8")

    try:
        started = datetime.fromisoformat(started_at) if started_at else now()
    except ValueError:
        started = now()

    with session_scope() as s:
        rec = s.exec(select(Recording).where(Recording.uid == recording_uid)).first()
        if rec is None:
            rec = Recording(uid=recording_uid)
        rec.device_id = device_id
        rec.mode = Mode(mode) if mode in Mode._value2member_map_ else Mode.quicknote
        rec.duration_s = duration_s
        rec.started_at = started
        rec.audio_path = str(audio)
        rec.checksum = checksum or None
        rec.status = SyncStatus.received
        s.add(rec)

    # (Audio is kept until processed; retention pruning per KEEP_AUDIO is a Phase 2 job.)
    storage.cleanup_chunks(recording_uid)
    background.add_task(process_recording, recording_uid)
    return {"received": True, "recording_uid": recording_uid, "final": True, "status": "processing"}


def _aware(dt: datetime | None) -> datetime | None:
    """Normalise to tz-aware UTC so naive+aware values can be compared/sorted."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


@app.get("/device/state")
def device_state(_: None = Depends(auth.require_device)) -> dict:
    """Payload the e-paper browses (FR-B5): counts, to-dos, notes, meetings."""
    limit = settings.device_list_limit
    with session_scope() as s:
        recs = s.exec(select(Recording).order_by(Recording.started_at.desc())).all()
        notes_by_rec = {n.recording_id: n for n in s.exec(select(Note)).all()}
        open_todos = s.exec(select(Todo).where(Todo.status == "open")).all()

        def entry(r: Recording) -> dict:
            n = notes_by_rec.get(r.id)
            return {
                "uid": r.uid,
                "title": n.title if n else None,
                "category": n.category if n else None,
                "date": _iso(r.started_at),
                "duration_s": r.duration_s,
                "status": r.status.value,
            }

        notes = [entry(r) for r in recs if r.mode == Mode.quicknote][:limit]
        meetings = [entry(r) for r in recs if r.mode == Mode.meeting][:limit]
        processing = sum(1 for r in recs if r.status in (SyncStatus.received, SyncStatus.processing))
        done = sum(1 for r in recs if r.status == SyncStatus.done)
        last = max((_aware(r.processed_at or r.started_at) for r in recs), default=None)

        return {
            "counts": {
                "processing": processing, "done": done,
                "open_todos": len(open_todos),
                "notes": sum(1 for r in recs if r.mode == Mode.quicknote),
                "meetings": sum(1 for r in recs if r.mode == Mode.meeting),
            },
            "open_todos": [{"id": t.id, "text": t.text, "due": t.due} for t in open_todos[:limit]],
            "notes": notes,
            "meetings": meetings,
            "last_sync_at": _iso(last),
            "backend_ok": True,
        }


@app.get("/device/notes/{uid}")
def device_note(uid: str, _: None = Depends(auth.require_device)) -> dict:
    """Full content of one item for on-device reading (FR-B9)."""
    with session_scope() as s:
        rec = s.exec(select(Recording).where(Recording.uid == uid)).first()
        if rec is None:
            raise HTTPException(status_code=404, detail="unknown recording")
        note = s.exec(select(Note).where(Note.recording_id == rec.id)).first()
        if note is None:
            return {"uid": uid, "status": rec.status.value, "ready": False}
        todos = s.exec(select(Todo).where(Todo.note_id == note.id)).all()
        return {
            "uid": uid, "ready": True, "status": rec.status.value, "mode": rec.mode.value,
            "title": note.title, "category": note.category,
            "cleaned_text": note.cleaned_text, "raw_transcript": note.raw_transcript,
            "summary": note.summary, "tags": note.tags.split(",") if note.tags else [],
            "todos": [{"id": t.id, "text": t.text, "status": t.status} for t in todos],
            "has_audio": bool(rec.audio_path and Path(rec.audio_path).exists()),
        }


@app.get("/device/recordings/{uid}/audio")
def device_audio(uid: str, _: None = Depends(auth.require_device)):
    """Stream original audio for on-device playback (FR-B10)."""
    return _audio_response(uid)


def _audio_response(uid: str):
    with session_scope() as s:
        rec = s.exec(select(Recording).where(Recording.uid == uid)).first()
        audio_path = rec.audio_path if rec else None
    if not audio_path or not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="no audio")
    return FileResponse(audio_path, media_type="audio/wav")


# =============================================================================
# DASHBOARD API (password/cookie auth)
# =============================================================================
@app.post("/api/login")
def login(response: Response, payload: dict = Body(...)) -> dict:
    if not auth.check_password(payload.get("password", "")):
        raise HTTPException(status_code=401, detail="wrong password")
    response.set_cookie(
        auth.COOKIE_NAME, auth.issue_session(),
        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30,
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/session")
def session_info(request: Request) -> dict:
    try:
        auth.require_dashboard(request)
        return {"authenticated": True}
    except HTTPException:
        return {"authenticated": False}


@app.get("/api/notes")
def api_notes(request: Request, q: str | None = None) -> list[dict]:
    auth.require_dashboard(request)
    with session_scope() as s:
        recs = {r.id: r for r in s.exec(select(Recording)).all()}
        notes = s.exec(select(Note).order_by(Note.created_at.desc())).all()
        out = []
        for n in notes:
            r = recs.get(n.recording_id)
            hay = f"{n.title} {n.category} {n.tags} {n.cleaned_text}".lower()
            if q and q.lower() not in hay:
                continue
            out.append({
                "id": n.id, "uid": n.uid, "title": n.title, "category": n.category,
                "tags": n.tags.split(",") if n.tags else [],
                "mode": r.mode.value if r else "quicknote",
                "date": _iso(r.started_at if r else n.created_at),
                "has_summary": bool(n.summary),
            })
        return out


@app.get("/api/notes/{note_id}")
def api_note(note_id: int, request: Request) -> dict:
    auth.require_dashboard(request)
    with session_scope() as s:
        n = s.get(Note, note_id)
        if n is None:
            raise HTTPException(status_code=404, detail="not found")
        r = s.get(Recording, n.recording_id)
        todos = s.exec(select(Todo).where(Todo.note_id == n.id)).all()
        return {
            "id": n.id, "uid": n.uid, "title": n.title, "category": n.category,
            "tags": n.tags.split(",") if n.tags else [],
            "cleaned_text": n.cleaned_text, "raw_transcript": n.raw_transcript,
            "summary": n.summary,
            "mode": r.mode.value if r else "quicknote",
            "language": r.language if r else None,
            "duration_s": r.duration_s if r else 0,
            "date": _iso(r.started_at if r else n.created_at),
            "has_audio": bool(r and r.audio_path and Path(r.audio_path).exists()),
            "todos": [{"id": t.id, "text": t.text, "owner": t.owner, "due": t.due, "status": t.status} for t in todos],
        }


@app.post("/api/notes/{note_id}/reprocess")
def api_reprocess(note_id: int, request: Request, background: BackgroundTasks) -> dict:
    auth.require_dashboard(request)
    with session_scope() as s:
        n = s.get(Note, note_id)
        if n is None:
            raise HTTPException(status_code=404, detail="not found")
        uid = n.uid
    background.add_task(process_recording, uid)
    return {"ok": True, "uid": uid}


@app.get("/api/todos")
def api_todos(request: Request, status: str = "open") -> list[dict]:
    auth.require_dashboard(request)
    with session_scope() as s:
        notes = {n.id: n for n in s.exec(select(Note)).all()}
        q = select(Todo)
        if status in ("open", "done"):
            q = q.where(Todo.status == status)
        todos = s.exec(q.order_by(Todo.created_at.desc())).all()
        return [{
            "id": t.id, "text": t.text, "owner": t.owner, "due": t.due, "status": t.status,
            "note_id": t.note_id,
            "note_title": notes[t.note_id].title if t.note_id in notes else "",
        } for t in todos]


@app.patch("/api/todos/{todo_id}")
def api_todo_update(todo_id: int, request: Request, payload: dict = Body(...)) -> dict:
    auth.require_dashboard(request)
    new_status = payload.get("status")
    if new_status not in ("open", "done"):
        raise HTTPException(status_code=400, detail="status must be open|done")
    with session_scope() as s:
        t = s.get(Todo, todo_id)
        if t is None:
            raise HTTPException(status_code=404, detail="not found")
        t.status = new_status
        t.updated_at = now()
        s.add(t)
    return {"ok": True, "id": todo_id, "status": new_status}


@app.get("/api/audio/{uid}")
def api_audio(uid: str, request: Request):
    auth.require_dashboard(request)
    return _audio_response(uid)


# --- serve the dashboard SPA (must be mounted last) --------------------------
if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
