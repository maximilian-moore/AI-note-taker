# PocketScribe — AI Note Taker

Firmware + backend + web dashboard for the **Waveshare ESP32-S3 1.54" e-Paper AIoT board**.
Press a button, speak a thought or record a meeting. Recordings buffer on microSD and
sync over Wi-Fi to a self-hosted backend that transcribes them and uses AI to produce
**clean notes, action items, meeting summaries, and auto titles/tags** — all browsable
from a password-protected web dashboard.

> **Status:** Phase 0 (scaffold). See [`PRD.md`](./PRD.md) for the full spec and roadmap.

## Repository layout

| Path | What it is |
|---|---|
| [`PRD.md`](./PRD.md) | Product requirements — the source of truth |
| `firmware/pocketscribe/` | Arduino-ESP32 firmware (capture, microSD, Wi-Fi sync, e-paper) |
| `backend/` | FastAPI service: ingest, transcription, AI enrichment, storage, API |
| `dashboard/` | Web dashboard (served by the backend) |
| `docs/` | Quick-start guide and architecture notes |

## The 3 pieces

1. **Device** — records audio + shows glanceable info (to-dos, notes, meetings) on e-paper.
2. **Backend** — the "brain": transcription (cloud Whisper now, local later) + Claude enrichment. Runs on Max's home server via Docker.
3. **Dashboard** — read/manage notes from any browser, exposed on Max's own domain over HTTPS.

## Getting started

- **Build the device / flash it:** see [`docs/QUICKSTART.md`](./docs/QUICKSTART.md).
- **Run the backend:** `cp backend/.env.example backend/.env`, fill in keys, then `docker compose up -d`.

Cloud-first for the MVP; everything is designed so you can move transcription/LLM local later.
