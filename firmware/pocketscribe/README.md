# PocketScribe firmware (Arduino-ESP32)

Firmware for the Waveshare **ESP32-S3-ePaper-1.54** board.

## What it does (PRD §6)
- **Record** with **Button B** (short = Quick Note, long = Meeting) → 16 kHz mono WAV on microSD, works offline.
- **Sync** with **Button B double-press** → uploads pending recordings and pulls back transcripts, to-dos and counts.
- **Browse** with **Button A** → Home/status, To-dos, Notes, Meetings; open a note to **read** it and **play** the audio.
- **Wi-Fi onboarding** with no hard-coded credentials via a captive-portal setup AP.
- **Power**: LiPo gauge, low-battery auto-finalize, deep-sleep when idle.

## Source layout
| File | Responsibility |
|---|---|
| `pocketscribe.ino` | State machine, screens, lifecycle |
| `board_pins.h` | GPIO map (e-paper confirmed; audio/SD/buttons marked **VERIFY**) |
| `config.h` | Tunable constants (sample rate, timings, thresholds) |
| `buttons.h` | Debounced 2-button input (short / long / double) |
| `audio.h` | ES8311 + I2S: record WAV to SD, play back |
| `netsync.h` | WiFiManager provisioning + chunked upload + state fetch |
| `ui.h` | e-paper rendering (GxEPD2) |

## Build & flash — two paths
**Easiest (no toolchain): browser flasher.** Once a `.bin` is built, open the install page and click Install. See [`../../docs/FLASHING.md`](../../docs/FLASHING.md).

**PlatformIO** (recommended for building): `pio run -t upload` using `platformio.ini` (pins the exact library versions).

**Arduino IDE**: install ESP32 board support, the libraries in `platformio.ini` `lib_deps`, select an ESP32-S3 board with PSRAM (OPI) + 8 MB flash, open `pocketscribe.ino`, Upload.

## ⚠ Bench bring-up checklist (before trusting a build)
This code targets the documented hardware but **could not be compiled/flashed during development**. On first hardware contact, verify in `board_pins.h`:
1. **e-paper** renders (pins are confirmed — should work first try).
2. **microSD** mounts (`SD_CLK/CMD/D0`).
3. **buttons** map to the right roles (which physical button is A vs B; BOOT=GPIO0).
4. **audio** records/plays — the **ES8311 register sequence + I2S pins** in `audio.h` are the highest-risk items; cross-check Espressif's `es8311` driver.
5. **battery ADC** pin + divider ratio.
