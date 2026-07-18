# Firmware build environment — what to install

Everything you need to **build, flash, and iterate** on the PocketScribe firmware
(`firmware/pocketscribe/`) for the Waveshare **ESP32-S3-ePaper-1.54** board.

You have two supported toolchains. **Pick one:**

- **PlatformIO** (recommended) — one config file pins the board + exact library
  versions, one command builds and flashes. Best for real development.
- **Arduino IDE** — friendlier GUI if you've used it before.

If you're setting this up with the **Claude Code CLI** on your other PC, jump to
[§6 "Doing this with Claude Code CLI"](#6-doing-this-with-claude-code-cli) — it has a
copy-paste brief you can hand to Claude.

---

## 1. Prerequisites (all platforms)

| Tool | Why | Check |
|---|---|---|
| **Git** | clone the repo | `git --version` |
| **Python 3.9+** | PlatformIO runs on Python | `python3 --version` |
| **A USB-C cable** | data-capable (not charge-only) | — |
| **microSD card** | the firmware records to it | — |

Clone the repo first:
```bash
git clone https://github.com/maximilian-moore/AI-note-taker.git
cd AI-note-taker/firmware/pocketscribe
```

### USB driver
The board uses the ESP32-S3's **native USB (USB-CDC)**, so on **macOS and Linux no
driver is needed**. On **Windows 10/11** it usually enumerates automatically; if the
COM port doesn't appear, install the **CP210x** *or* **CH343** VCP driver (depending
on the board revision) from Silicon Labs / WCH.

**Linux only** — allow non-root serial access (log out/in afterward):
```bash
sudo usermod -a -G dialout $USER          # Debian/Ubuntu
# (Arch/Fedora: the group is 'uucp' -> sudo usermod -a -G uucp $USER)
```

---

## 2. Option A — PlatformIO (recommended)

### Install
PlatformIO Core (CLI):
```bash
python3 -m pip install --user platformio
pio --version                              # confirm it's on PATH
```
(Or install the **PlatformIO IDE** extension in VS Code, which bundles Core.)

### Build & flash
```bash
cd firmware/pocketscribe
pio run                 # first run downloads the espressif32 platform + toolchain
                        # (~hundreds of MB, a few minutes — needs internet)
pio run -t upload       # build + flash over USB
pio device monitor      # serial logs @ 115200 (Ctrl-C to exit)
```
`platformio.ini` already sets everything (board `esp32-s3-devkitc-1`, 8 MB flash,
OPI PSRAM, native-USB CDC) and pins the libraries — nothing else to configure.

### What PlatformIO pulls in automatically (for reference)
- **Platform:** `espressif32` (Arduino-ESP32 core 3.x, ESP-IDF v5 underneath).
- **Libraries** (from `platformio.ini` → `lib_deps`):
  - `tzapu/WiFiManager` ^2.0.17 — captive-portal Wi-Fi provisioning
  - `zinggjm/GxEPD2` ^1.6.0 — e-paper driver (also pulls Adafruit GFX)
  - `bblanchon/ArduinoJson` ^7.1.0 — device_state / note JSON

---

## 3. Option B — Arduino IDE

1. Install **Arduino IDE 2.x** (arduino.cc/en/software).
2. **Preferences → Additional Boards Manager URLs**, add:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. **Boards Manager** → install **esp32 by Espressif Systems** (use **v3.0.0 or newer** — the firmware uses the ESP-IDF v5 I2S `i2s_std` API).
4. **Library Manager** → install:
   - **WiFiManager** by tzapu
   - **GxEPD2** by Jean-Marc Zingg (accept the Adafruit GFX dependency)
   - **ArduinoJson** by Benoit Blanchon (v7.x)
5. Open `firmware/pocketscribe/pocketscribe.ino`.
6. **Tools →** set:
   | Setting | Value |
   |---|---|
   | Board | **ESP32S3 Dev Module** |
   | USB CDC On Boot | **Enabled** |
   | Flash Size | **8MB (64Mb)** |
   | PSRAM | **OPI PSRAM** |
   | Partition Scheme | **8M with spiffs / default 8MB** |
   | Upload Speed | 921600 (drop to 115200 if uploads fail) |
7. Select the board's **Port**, click **Upload**, open **Serial Monitor** @ 115200.

> If upload fails to start: hold **BOOT**, tap **RESET**, release **BOOT** to force
> download mode, then upload again.

---

## 4. Building the browser-flasher `.bin` (optional)

To let yourself (or others) flash with no toolchain via `firmware/webflash/`
([FLASHING.md](./FLASHING.md) Option A), produce a single merged image:

```bash
cd firmware/pocketscribe
pio run -t buildfs           # only if you add a filesystem later; usually skip
pio run                      # normal build
# merge the bootloader+partitions+app into one file at offset 0:
pio pkg exec -- esptool.py --chip esp32s3 merge_bin \
  -o ../webflash/pocketscribe.bin \
  --flash_mode dio --flash_size 8MB \
  0x0 .pio/build/pocketscribe/bootloader.bin \
  0x8000 .pio/build/pocketscribe/partitions.bin \
  0x10000 .pio/build/pocketscribe/firmware.bin
```
Then commit `firmware/webflash/pocketscribe.bin`; the install page's
`manifest.json` already points at it (offset 0).

---

## 5. Bench bring-up — verify the hardware pins

The firmware targets the documented hardware but **has not been run on a physical
board**. On first flash, work through the checklist in
[`firmware/pocketscribe/README.md`](../firmware/pocketscribe/README.md), confirming
values in **`board_pins.h`**:

1. **E-paper** — pins are confirmed from Waveshare; should render on first try.
2. **microSD** (`SD_CLK/CMD/D0`) — mounts?
3. **Buttons** — which physical button is A (navigate) vs B (record); BOOT = GPIO0.
4. **Audio** — the **ES8311 init + I2S pins in `audio.h`** are the highest-risk part.
   Reference: Espressif's official driver
   (`components/esp_codec_dev` / `esp-adf`'s `es8311`) and the board schematic on the
   [Waveshare wiki](https://www.waveshare.com/wiki/ESP32-S3-ePaper-1.54).
5. **Battery ADC** pin + `VBAT_DIVIDER` ratio in `config.h`.

Use `pio device monitor` (or the Arduino Serial Monitor) to watch the boot log while
you verify each subsystem.

---

## 6. Doing this with Claude Code CLI

On your other PC, install the Claude Code CLI, `cd` into a clone of this repo, and
give Claude this brief:

> Set up the firmware build environment described in `docs/FIRMWARE_BUILD_ENV.md`.
> I'm on **<macOS / Windows / Linux>**. Install PlatformIO Core, then run
> `cd firmware/pocketscribe && pio run` and fix any toolchain/library errors until it
> builds. Do **not** change `board_pins.h` values — those need hardware verification.
> When it builds, tell me the exact `pio run -t upload` command and how to open the
> serial monitor.

Claude can install PlatformIO, trigger the platform/library download, resolve build
errors, and produce the flashable binary. It **cannot** verify the hardware pins or
the ES8311 audio path without the physical board in front of you — that's the manual
bench step in §5.

### Minimum to get a green build
- Git, Python 3.9+, PlatformIO Core.
- Internet access for the first `pio run` (downloads the ESP32 platform + libs).
- ~2 GB free disk for the toolchain/platform cache.

That's it — once `pio run` succeeds you have a buildable, flashable firmware.
