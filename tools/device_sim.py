#!/usr/bin/env python3
"""
PocketScribe device simulator.

Mimics exactly what the firmware does over HTTP, so you can test the full
cloud flow (record -> chunked upload -> sync -> transcript back -> dashboard)
from any PC before the hardware arrives. Zero dependencies (stdlib only).

This file also doubles as the reference for the firmware's HTTP contract.

Examples:
  # upload a WAV as a quick note (mock mode: inject the "spoken" text)
  python device_sim.py record --wav note.wav \\
      --text "Um, remember to email Sarah the report by Friday." \\
      --url http://localhost:8080 --token change-me

  # upload a meeting recording
  python device_sim.py record --wav meeting.wav --mode meeting --url ... --token ...

  # if you have no WAV handy, generate 3s of silence to exercise the pipeline
  python device_sim.py record --gen 3 --text "test note, call the plumber" --url ... --token ...

  # inspect what the device screen would show
  python device_sim.py state --url ... --token ...
  python device_sim.py read <uid> --url ... --token ...
"""
import argparse
import io
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid
import wave

CHUNK_BYTES = 32 * 1024  # matches firmware AUDIO upload chunking granularity


# --- tiny multipart/urllib helpers (no external deps) ------------------------
def _multipart(fields: dict, file_field: str, filename: str, filedata: bytes):
    boundary = "----pocketscribe" + uuid.uuid4().hex
    nl = b"\r\n"
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(b"--" + boundary.encode() + nl)
        body.write(f'Content-Disposition: form-data; name="{k}"'.encode() + nl + nl)
        body.write(str(v).encode() + nl)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body.write(b"--" + boundary.encode() + nl)
    body.write(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode() + nl)
    body.write(f"Content-Type: {ctype}".encode() + nl + nl)
    body.write(filedata + nl)
    body.write(b"--" + boundary.encode() + b"--" + nl)
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def _req(method, url, token, data=None, ctype=None):
    headers = {"X-Device-Token": token}
    if ctype:
        headers["Content-Type"] = ctype
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")}


def _gen_wav(seconds: int, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)
    return buf.getvalue()


def _wav_seconds(data: bytes) -> int:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return int(w.getnframes() / w.getframerate())
    except Exception:
        return 0


# --- commands ----------------------------------------------------------------
def cmd_record(args):
    if args.wav:
        audio = open(args.wav, "rb").read()
    else:
        audio = _gen_wav(args.gen)
        print(f"[sim] generated {args.gen}s of silence ({len(audio)} bytes)")

    uid = args.uid or ("sim-" + uuid.uuid4().hex[:10])
    duration = _wav_seconds(audio)
    chunks = [audio[i:i + CHUNK_BYTES] for i in range(0, len(audio), CHUNK_BYTES)] or [b""]
    print(f"[sim] uploading uid={uid} mode={args.mode} in {len(chunks)} chunk(s)…")

    for seq, chunk in enumerate(chunks):
        final = seq == len(chunks) - 1
        fields = {
            "device_id": args.device_id, "recording_uid": uid, "mode": args.mode,
            "seq": seq, "final": str(final).lower(), "audio_ext": "wav",
            "duration_s": duration,
        }
        if final and args.text:
            fields["mock_transcript"] = args.text
        body, ctype = _multipart(fields, "chunk", f"{uid}.{seq}.wav", chunk)
        status, resp = _req("POST", args.url + "/ingest", args.token, body, ctype)
        if status != 200:
            print(f"[sim] chunk {seq} FAILED (HTTP {status}): {resp}")
            sys.exit(1)
        print(f"[sim]   chunk {seq}{' (final)' if final else ''} -> {resp}")

    print("[sim] === Sync now (double-press) === pulling state…")
    time.sleep(1.0)  # give the backend a moment to process
    _print_state(args)
    print(f"\n[sim] reading the note back onto the 'device screen':")
    _print_note(args, uid)


def cmd_state(args):
    _print_state(args)


def cmd_read(args):
    _print_note(args, args.uid)


def _print_state(args):
    status, st = _req("GET", args.url + "/device/state", args.token)
    if status != 200:
        print(f"[sim] state failed (HTTP {status}): {st}")
        return
    c = st["counts"]
    print(f"  ┌ PocketScribe ───────────────")
    print(f"  │ notes:{c['notes']}  meetings:{c['meetings']}  open to-dos:{c['open_todos']}")
    print(f"  │ processing:{c['processing']}  done:{c['done']}")
    print(f"  │ last sync: {st['last_sync_at'] or '—'}")
    if st["open_todos"]:
        print(f"  ├ TO-DOS")
        for t in st["open_todos"]:
            print(f"  │  • {t['text']}")
    if st["notes"]:
        print(f"  ├ NOTES")
        for n in st["notes"]:
            print(f"  │  {n['title'] or '(processing…)'}  [{n['category'] or '-'}]  {n['status']}")
    if st["meetings"]:
        print(f"  ├ MEETINGS")
        for m in st["meetings"]:
            print(f"  │  {m['title'] or '(processing…)'}  {m['duration_s']}s  {m['status']}")
    print(f"  └─────────────────────────────")


def _print_note(args, uid):
    status, n = _req("GET", args.url + f"/device/notes/{uid}", args.token)
    if status != 200:
        print(f"[sim] read failed (HTTP {status}): {n}")
        return
    if not n.get("ready"):
        print(f"  (not processed yet: {n.get('status')})")
        return
    print(f"  TITLE: {n['title']}   [{n['category']}]")
    if n.get("summary"):
        print(f"  SUMMARY: {n['summary']}")
    print(f"  CLEANED: {n['cleaned_text']}")
    print(f"  TRANSCRIPT: {n['raw_transcript']}")
    if n["todos"]:
        print("  TO-DOS:")
        for t in n["todos"]:
            print(f"    [{'x' if t['status']=='done' else ' '}] {t['text']}")
    print(f"  AUDIO: {'available for playback' if n['has_audio'] else 'not stored'}")


def main():
    p = argparse.ArgumentParser(description="PocketScribe device simulator")
    p.add_argument("--url", default=os.environ.get("PS_URL", "http://localhost:8080"))
    p.add_argument("--token", default=os.environ.get("PS_TOKEN", "change-me"))
    p.add_argument("--device-id", default="sim-device")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="record (or upload) + sync a note")
    r.add_argument("--wav", help="path to a 16kHz mono WAV to upload")
    r.add_argument("--gen", type=int, default=2, help="generate N seconds of silence if no --wav")
    r.add_argument("--text", help="inject spoken text (used by backend mock STT)")
    r.add_argument("--mode", choices=["quicknote", "meeting"], default="quicknote")
    r.add_argument("--uid", help="override recording uid")
    r.set_defaults(func=cmd_record)

    s = sub.add_parser("state", help="show what the device screen would display")
    s.set_defaults(func=cmd_state)

    rd = sub.add_parser("read", help="read one note back onto the device screen")
    rd.add_argument("uid")
    rd.set_defaults(func=cmd_read)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
