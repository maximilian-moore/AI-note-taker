# PocketScribe firmware (Arduino-ESP32)

Firmware for the Waveshare **ESP32-S3-Touch-ePaper-1.54** board.

> **Status:** Phase 0 scaffold. Sketch + drivers land in Phase 1.

## Responsibilities (see PRD.md §6.1–6.5)
- **Interaction:** buttons only, no touch. **Button B** records (short = Quick Note, long = Meeting); **Button A** navigates the screens.
- **Capture:** records 16 kHz mono to microSD in chunks. Works offline.
- **Sync:** when Wi-Fi is up, upload unsynced chunks to the backend (`/ingest`), resumable + retryable; pull `/device/state` for the screen.
- **Display:** button-navigated e-paper — Home/status, To-dos, Notes (title + category), Meetings. Partial refresh for timers/paging.
- **Power:** LiPo gauge, low-battery warning, safe shutdown (finalize current chunk), deep-sleep when idle.
- **Onboarding:** first boot → SoftAP captive portal to enter Wi-Fi + backend URL + pairing token (stored in NVS).

## Build & flash

Two supported paths (decided in Phase 1):
- **Arduino IDE / arduino-cli** with the ESP32-S3 board package, or
- **PlatformIO** (`platformio.ini` to be added).

For end users, the goal is **no toolchain at all**: a prebuilt binary flashed from a
browser via ESP Web Tools. See [`../../docs/QUICKSTART.md`](../../docs/QUICKSTART.md).

## Config
- `config.h` — compile-time pins + audio constants (pin map TBD at bring-up).
- Runtime secrets (Wi-Fi, backend URL, token) come from **provisioning**, never hard-coded.
