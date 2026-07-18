"""End-to-end backend test (mock engines, no keys). Run: python test_e2e.py"""
import io
import os
import tempfile
import wave

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ps-test-"))
os.environ.setdefault("DEVICE_PAIRING_TOKEN", "test-token")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-pass")
os.environ.setdefault("TRANSCRIBE_ENGINE", "mock")
os.environ.setdefault("LLM_ENGINE", "mock")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
DEV = {"x-device-token": "test-token"}


def make_wav(seconds=1, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)
    return buf.getvalue()


def check(cond, msg):
    print(("PASS" if cond else "FAIL"), "-", msg)
    assert cond, msg


def main():
    r = client.get("/health")
    check(r.status_code == 200 and r.json()["ok"], "health ok")

    # auth is enforced
    check(client.get("/device/state").status_code == 401, "device auth enforced")

    # ingest a two-chunk meeting recording with an injected transcript
    uid = "rec-abc-123"
    transcript = ("Um, in today's meeting we decided to ship on Friday. "
                  "I need to send the report to Sarah. Ich muss die Rechnung bezahlen.")
    wav = make_wav(2)
    half = len(wav) // 2
    r1 = client.post("/ingest", headers=DEV,
                     data={"device_id": "dev1", "recording_uid": uid, "mode": "meeting",
                           "seq": 0, "final": "false", "audio_ext": "wav"},
                     files={"chunk": ("c0.wav", wav[:half], "audio/wav")})
    check(r1.status_code == 200 and not r1.json()["final"], "chunk 0 accepted")
    r2 = client.post("/ingest", headers=DEV,
                     data={"device_id": "dev1", "recording_uid": uid, "mode": "meeting",
                           "seq": 1, "final": "true", "audio_ext": "wav",
                           "duration_s": 2, "mock_transcript": transcript},
                     files={"chunk": ("c1.wav", wav[half:], "audio/wav")})
    check(r2.status_code == 200 and r2.json()["final"], "final chunk -> processing")

    # device state reflects the processed recording
    st = client.get("/device/state", headers=DEV).json()
    check(st["counts"]["meetings"] == 1, "one meeting counted")
    check(st["counts"]["done"] == 1, "recording processed (done)")
    check(st["counts"]["open_todos"] >= 2, f"todos extracted ({st['counts']['open_todos']})")
    check(st["last_sync_at"] is not None, "last_sync_at set")

    # device reads the note back
    note = client.get(f"/device/notes/{uid}", headers=DEV).json()
    check(note["ready"] and note["title"], "note ready with title")
    check("um" not in note["cleaned_text"].lower().split(), "filler removed from cleaned text")
    check(note["raw_transcript"].startswith("Um,"), "raw transcript preserved")
    check(note["summary"], "meeting summary present")
    check(note["has_audio"], "audio available for playback")

    # device audio streams
    ra = client.get(f"/device/recordings/{uid}/audio", headers=DEV)
    check(ra.status_code == 200 and ra.headers["content-type"] == "audio/wav", "audio streams")

    # dashboard: login gate
    check(client.get("/api/notes").status_code == 401, "dashboard auth enforced")
    check(client.post("/api/login", json={"password": "wrong"}).status_code == 401, "bad pw rejected")
    lr = client.post("/api/login", json={"password": "test-pass"})
    check(lr.status_code == 200, "login ok")

    notes = client.get("/api/notes").json()
    check(len(notes) == 1, "dashboard lists the note")
    nid = notes[0]["id"]
    detail = client.get(f"/api/notes/{nid}").json()
    check(detail["summary"] and detail["todos"], "dashboard note detail complete")

    # search
    check(len(client.get("/api/notes", params={"q": "report"}).json()) == 1, "search hits")
    check(len(client.get("/api/notes", params={"q": "zzzznope"}).json()) == 0, "search misses")

    # todos: list + check off
    todos = client.get("/api/todos").json()
    check(len(todos) >= 2, "todos listed")
    tid = todos[0]["id"]
    check(client.patch(f"/api/todos/{tid}", json={"status": "done"}).status_code == 200, "todo checked off")
    check(len(client.get("/api/todos", params={"status": "open"}).json()) == len(todos) - 1, "open count drops")

    # reprocess is idempotent (no duplicate notes)
    client.post(f"/api/notes/{nid}/reprocess")
    check(len(client.get("/api/notes").json()) == 1, "reprocess does not duplicate")

    print("\nALL BACKEND E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
