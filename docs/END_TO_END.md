# End-to-end test runbook

Two stages: **(1) prove the whole cloud flow today with the simulator** (no
hardware needed), then **(2) repeat it with the real device** once it arrives.
Same backend, same API, same result in the dashboard.

---

## Stage 1 — Test the full flow now (no device)

### 1. Start the backend
```bash
cp backend/.env.example backend/.env
# edit backend/.env: set DEVICE_PAIRING_TOKEN and DASHBOARD_PASSWORD to anything.
# Leave engines as "mock" for now (no API keys needed).
docker compose up -d
curl localhost:8080/health          # -> {"ok": true, ...}
```
(No Docker? Run it directly: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && DATA_DIR=./data uvicorn app.main:app --port 8080`.)

### 2. "Record" and sync with the simulator
The simulator does exactly what the firmware does over HTTP.
```bash
python tools/device_sim.py --url http://localhost:8080 --token <your-token> \
  record --mode meeting --gen 3 \
  --text "Um, in today's sync we agreed to ship Friday. I need to email the deck to the team."
```
You'll see the chunked upload, the "Sync now" pull, the device-screen preview,
and the transcript + to-dos coming back.

### 3. See it in the dashboard
Open **http://localhost:8080**, log in with `DASHBOARD_PASSWORD`, and you'll find
the note with its cleaned text, transcript, summary, to-dos, and audio player.

### 4. Turn on real transcription (cloud)
When you're ready for real speech-to-text and AI cleanup, edit `backend/.env`:
```
TRANSCRIBE_ENGINE=cloud
LLM_ENGINE=cloud
OPENAI_API_KEY=sk-...        # Whisper transcription
ANTHROPIC_API_KEY=sk-ant-... # Claude enrichment
```
`docker compose up -d` to restart, then record a **real** WAV (16 kHz mono):
```bash
python tools/device_sim.py --url http://localhost:8080 --token <token> record --wav my-voice.wav
```
Now the transcript is your actual words, cleaned up by Claude.

---

## Stage 2 — The real device

1. **Flash** it: [FLASHING.md](./FLASHING.md) (browser flasher = easiest).
2. **Connect Wi-Fi**: [WIFI.md](./WIFI.md) — join `PocketScribe-Setup`, enter your
   Wi-Fi + the same **Backend URL** and **pairing token** as the backend.
3. **Record**: press **Button B** (short = Quick Note, long = Meeting), speak, press again to stop.
4. **Sync**: **double-press Button B**. The screen shows upload progress, then updated counts.
5. **Read on device**: **Button A** cycles Home → To-dos → Notes → Meetings; open a
   note to read the transcript and **Button B** to play the audio.
6. **Dashboard**: everything the device captured is at your backend URL in the browser.

> The backend can't tell a real device from the simulator — they use the same
> endpoints — so anything you verified in Stage 1 will behave the same with hardware.

---

## Troubleshooting
| Symptom | Check |
|---|---|
| Device shows **Setup** and won't connect | Wi-Fi password, or re-run setup (hold **Button A** while powering on). |
| Sync says **No Wi-Fi** / fails | Backend URL reachable from the device's network? Server running? Token matches `.env`? |
| Note stuck on **Processing** | Backend logs (`docker compose logs -f backend`). In cloud mode, check API keys/quota. |
| Dashboard **wrong password** | It's `DASHBOARD_PASSWORD` from `.env` (restart after changing). |
| No audio playback on device | Confirm the audio output path + ES8311 pins at bring-up (see firmware README). |
| Categories/to-dos look rough in **mock** mode | Expected — mock uses simple heuristics. Switch to cloud for real quality. |
