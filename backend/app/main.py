"""
PocketScribe backend — API skeleton (Phase 0).

Endpoints are stubbed with the contract from PRD.md §6.6. Phase 1 fills in the
transcription + enrichment pipeline behind /ingest and the real queries behind
/device/state and the dashboard API.
"""
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from sqlmodel import SQLModel, create_engine

from .config import settings

app = FastAPI(title="PocketScribe", version="0.0.1")

# --- storage -----------------------------------------------------------------
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{settings.data_dir}/pocketscribe.db")


@app.on_event("startup")
def _init_db() -> None:
    SQLModel.metadata.create_all(engine)


# --- auth helpers ------------------------------------------------------------
def _require_device(token: str | None) -> None:
    if token != settings.device_pairing_token:
        raise HTTPException(status_code=401, detail="bad pairing token")


# --- health ------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"ok": True, "transcribe": settings.transcribe_engine, "llm": settings.llm_engine}


# --- device: ingest audio (FR-B1) -------------------------------------------
@app.post("/ingest")
async def ingest(
    chunk: UploadFile = File(...),
    device_id: str = Form(...),
    mode: str = Form("quicknote"),
    recording_uid: str = Form(...),     # stable id from the device manifest
    seq: int = Form(0),                 # chunk index
    final: bool = Form(False),          # last chunk of this recording?
    checksum: str = Form(""),
    x_device_token: str | None = Header(default=None),
) -> dict:
    """Accept a chunked audio upload. Idempotent on (recording_uid, seq).

    TODO(Phase 1): persist chunk to DATA_DIR, and on `final` reassemble,
    create a Recording row (status=pending), and enqueue processing
    (transcribe -> enrich -> store Note/Todos).
    """
    _require_device(x_device_token)
    return {"received": True, "recording_uid": recording_uid, "seq": seq, "final": final}


# --- device: state for the e-paper (FR-B5) ----------------------------------
@app.get("/device/state")
def device_state(x_device_token: str | None = Header(default=None)) -> dict:
    """What the e-paper browses: to-dos, recent notes, recent meetings, counts.

    TODO(Phase 1): query real data, compact/paged for the 200x200 screen.
    """
    _require_device(x_device_token)
    return {
        "counts": {"notes": 0, "meetings": 0, "open_todos": 0, "pending_uploads": 0},
        "open_todos": [],       # [{text, due}]
        "notes": [],            # [{title, category, date}]
        "meetings": [],         # [{title, date, duration_s}]
        "last_sync_at": None,
        "backend_ok": True,
    }


# --- dashboard API (FR-W*) ---------------------------------------------------
# TODO(Phase 1): /api/notes, /api/notes/{id}, /api/todos (+ check-off),
# search, re-run enrichment, and serve the dashboard SPA from /.
