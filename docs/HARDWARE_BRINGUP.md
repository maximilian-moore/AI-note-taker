# Hardware bring-up status — Waveshare ESP32-S3-ePaper-1.54

Living record of getting the PocketScribe firmware running on the real board.
Update the status table as peripherals are verified.

_Last updated: 2026-07-19 — firmware commit `3ec4c56`._

---

## 1. Board summary

| Item | Value |
|---|---|
| Module | ESP32-S3-PICO-1-N8R8 (8 MB flash, 8 MB OPI PSRAM) |
| Display | 1.54" 200×200 B/W e-paper, GDEY0154D67 / SSD1681 |
| Audio | ES8311 codec + onboard mic, speaker amp |
| Storage | microSD (SD_MMC, 1-bit) |
| Sensors | PCF85063 RTC, SHTC3 temp/humidity |
| Touch | **None** — see §3 |
| Buttons | BOOT (GPIO0) + PWR (GPIO18), both active-LOW |
| USB | Native USB-CDC (VID `303A`, PID `1001`) |

---

## 2. Peripheral status

| Peripheral | Status | Notes |
|---|---|---|
| USB / flashing | ✅ Working | Native USB-CDC; see build-env gotcha §5 |
| E-paper display | ✅ Working | Partial refresh ~0.5s, full ~1.8s; see §4 |
| Button A (BOOT / GPIO0) | ✅ Working | Navigate |
| Button B (PWR / GPIO18) | ✅ Working | Record; polarity was mis-mapped, now fixed |
| I2C bus (SDA 47 / SCL 48) | ✅ Working | 3 devices found — see §3 |
| PCF85063 RTC (`0x51`) | ✅ ACKs | Timekeeping across reboot not yet verified |
| SHTC3 sensor (`0x70`) | ✅ ACKs | Read values not yet verified |
| ES8311 codec control (`0x18`) | ✅ ACKs | I2C control only; **audio path untested** |
| microSD mount | ⬜ Untested | Record a note, confirm `/rec/*.wav` |
| ES8311 mic capture | ⬜ Untested | **Highest risk** |
| ES8311 speaker playback | ⬜ Untested | Detail screen → B short plays the WAV |
| Battery ADC (GPIO4) | ⬜ Untested | `VBAT_DIVIDER=2.0` is a guess — verify |
| Wi-Fi / backend sync | ⬜ Untested | Backend server not yet running |
| Deep-sleep / wake | ⬜ Untested | Wakes on Button B (GPIO18) |

Legend: ✅ verified on hardware · ⬜ not yet tested.

---

## 3. Touch: confirmed absent

Despite "Touch" in some product listings, this unit has **no touch digitizer**. An
I2C bus scan found exactly three devices — ES8311 `0x18`, PCF85063 RTC `0x51`,
SHTC3 `0x70` — and **no touch controller** (checked GT911 `0x5D`/`0x14`, CST816
`0x15`, FT6x36 `0x38`). The UI is buttons-only, which matches the PRD assumption.

---

## 4. Input & display design (important)

**Buttons.** Both BOOT (A) and PWR (B) are active-LOW (short to GND, internal
pull-up). The original board map guessed B was active-HIGH — it read `0` both idle
and pressed, so B never registered. Fixed in `board_pins.h`.

**GPIO0 is a boot strap.** Holding GPIO0 (Button A) low at reset drops the S3 into
USB download mode and the app never runs. So the **recovery portal** and the
**deep-sleep wake** both trigger on Button B (GPIO18, not a strap), never A.

**Control map:**

| Gesture | Action |
|---|---|
| A short | Next section (Home → To-dos → Notes → Meetings → Home); in Detail, next page |
| A long | In Detail: back to list. In a list: next item. On Home: **Sync** |
| B short | Context: start/stop quick note · open item · play WAV |
| B long | Start/stop **meeting** recording |
| Hold B at power-on | Force Wi-Fi setup portal |
| Press B (asleep) | Wake from deep sleep |

**Display responsiveness.** A full e-paper refresh takes ~1.8s and **blocks the
CPU** — during it, buttons aren't polled and taps are lost, which feels like dead
buttons. Fix: navigation uses **partial refresh** (~0.5s, verified visible on this
panel); `beginWindow()` forces a full refresh only on the first draw and every
`EPD_PARTIAL_MAX` draws to clear ghosting. The recording timer ticks every 3s (not
1s) to keep the polling blind-window small. **Do not revert nav to full refresh.**

---

## 5. Build / flash gotchas

- **PlatformIO** lives at `%APPDATA%\Python\Python312\Scripts\pio.exe` (not on PATH).
  Uses the **pioarduino** platform fork (Arduino core 3.x / ESP-IDF v5) — the
  official platform ships core 2.0.17, which lacks `driver/i2s_std.h`.
- **cp1252 UnicodeEncodeError on Windows.** `pio run -t upload` can crash mid-flash
  printing esptool's progress-bar glyph (`█`) to a non-UTF-8 console; it then hangs
  for minutes before failing. It looks like a stuck board — it is not. **Fix:** set
  `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` before invoking `pio`.
- **Do not use the pyserial DTR/RTS reset-capture script** — it de-enumerates the
  native-USB board. Use `pio device monitor` to read serial.
- **`BTN_DEBUG`** in `pocketscribe.ino` is currently `1` — it dumps raw pin levels
  and button events on serial (115200). **Set to `0` before shipping.**

Flash command:
```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
pio run -d firmware/pocketscribe -t upload --upload-port COM5
```

---

## 6. Next steps

1. **microSD** — record a note; confirm the WAV lands at `/rec/<uid>.wav`. Check the
   boot serial for an SD mount-failure line.
2. **ES8311 audio (highest risk)** — record, then open the item and B-short to play
   back. Validates mic capture (I2S DIN) + speaker (I2S DOUT + PA_ENABLE).
3. **Battery ADC** — attach a LiPo, sanity-check the reported %, verify `VBAT_DIVIDER`.
4. **Backend + Wi-Fi sync** — bring up the `backend/` server, provision Wi-Fi via the
   setup portal, test a sync (long-A on Home).
5. **Deep-sleep / wake** — leave idle 2 min, confirm sleep + Button-B wake.
6. **Cleanup** — set `BTN_DEBUG 0`; confirm RTC + SHTC3 read sane values.
