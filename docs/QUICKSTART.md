# PocketScribe — Quick Start (target: ~15 minutes, no coding)

> This is the **intended** end-user flow. Steps marked _(Phase 1)_ become clickable
> once the firmware binary and installer page ship. It's written now so the build
> targets a genuinely easy install.

## 0. What you need
- The Waveshare ESP32-S3 1.54" e-Paper board (touch version).
- A **microSD card** (16–32 GB, Class 10) — **required**.
- A **LiPo battery** (~800–1200 mAh, matching connector) — for portable use.
- A **USB-C cable** and a Chrome or Edge browser (for flashing).
- Your **home server** running Docker (for the backend).

## 1. Set up the backend (home server)
```bash
git clone <this repo> && cd AI-note-taker
cp backend/.env.example backend/.env
# edit backend/.env: set DEVICE_PAIRING_TOKEN, DASHBOARD_PASSWORD,
# OPENAI_API_KEY (Whisper) and ANTHROPIC_API_KEY (Claude)
docker compose up -d
```
Check it's alive: open `http://<server-ip>:8080/health` — you should see `{"ok": true, ...}`.

## 2. Flash the device _(Phase 1)_
1. Insert the microSD card.
2. Plug the board into your computer via USB-C.
3. Open the **PocketScribe install page** in Chrome/Edge and click **Install**.
4. Select the serial port when prompted; wait for "Flashing complete."

_No IDE, no drivers, no command line._

## 3. Provision Wi-Fi _(Phase 1)_
1. On first boot the device creates a Wi-Fi hotspot **"PocketScribe-Setup"**.
2. Connect your phone to it; a setup page opens automatically.
3. Enter: your **Wi-Fi** name + password, the **backend URL** (`http://<server-ip>:8080`),
   and the **pairing token** you set in `.env`.
4. Save — the device reboots and joins your network.

## 4. Capture your first note _(Phase 1)_
The device is button-only (no touch). The **Record button (Button B)**:
- **Quick Note:** short-press to start, speak, short-press to stop.
- **Meeting:** long-press to start, long-press to stop.
- The **Navigate button (Button A)** cycles the screens (Home / To-dos / Notes / Meetings).
- The screen shows "Saved ✓". When on Wi-Fi it uploads automatically.

## 5. Read your notes
- Open the dashboard in any browser and log in with `DASHBOARD_PASSWORD`.
- See the cleaned note, raw transcript, meeting summary, action items, and to-dos.

## 6. Access it away from home _(Phase 2)_
Put the dashboard on your own domain over HTTPS with a login — recommended via a
**Cloudflare Tunnel** (no router changes). Setup steps will be added here.
