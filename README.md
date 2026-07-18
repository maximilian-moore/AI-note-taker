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

## Try the whole flow in 2 minutes (no hardware, no API keys)

```bash
cp backend/.env.example backend/.env      # set DEVICE_PAIRING_TOKEN + DASHBOARD_PASSWORD
docker compose up -d                      # backend + dashboard on :8080  (engines default to keyless "mock")
python tools/device_sim.py --url http://localhost:8080 --token <token> \
    record --mode meeting --gen 3 \
    --text "Um, we agreed to ship Friday. I need to email the deck to the team."
# then open http://localhost:8080  (log in with DASHBOARD_PASSWORD)
```
The simulator uses the **exact same HTTP contract as the firmware**, so this
proves the real device's path before it arrives. Flip `TRANSCRIBE_ENGINE`/
`LLM_ENGINE` to `cloud` (+ keys) for real Whisper + Claude.

## Docs
| Guide | For |
|---|---|
| [`docs/END_TO_END.md`](./docs/END_TO_END.md) | Full test runbook (simulator now → device later) |
| [`docs/FLASHING.md`](./docs/FLASHING.md) | Flashing the firmware (browser flasher / PlatformIO / Arduino IDE) |
| [`docs/WIFI.md`](./docs/WIFI.md) | Connecting the device to Wi-Fi |
| [`PRD.md`](./PRD.md) | Full product spec + roadmap |

Cloud-first for the MVP; everything is designed so you can move transcription/LLM local later.
