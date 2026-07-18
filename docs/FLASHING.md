# Flashing the firmware

Three ways, easiest first. You only need **one**.

---

## Option A — Flash from your browser (no toolchain) ✅ recommended

Uses [ESP Web Tools](https://esphome.github.io/esp-web-tools/) — works in **Chrome or Edge** on desktop (Web Serial).

1. Plug the board into your computer with a USB-C cable.
2. Open the install page (`firmware/webflash/index.html`) — host it on GitHub Pages, or open it locally in Chrome/Edge.
3. Click **Install PocketScribe**, pick the serial port, and wait for "Flashing complete."
4. Unplug/replug — the device boots into Wi-Fi setup (see [`WIFI.md`](./WIFI.md)).

> The board uses the ESP32-S3 **native USB**, so on most systems **no driver** is needed. If the port doesn't appear, hold **BOOT**, tap **RESET**, release **BOOT** to force download mode, then retry.

**Producing the `.bin` the page installs** (done once, by whoever builds it):
```bash
# with PlatformIO installed:
cd firmware/pocketscribe
pio run                                   # builds the firmware
pio run -t mergebin                       # -> merged single-file image
# copy the merged bin next to the web page and point manifest.json at it
cp .pio/build/pocketscribe/firmware-merged.bin ../webflash/pocketscribe.bin
```
(If `mergebin` isn't available, use `esptool.py --chip esp32s3 merge_bin -o firmware-merged.bin @flash_args`.)

---

## Option B — PlatformIO (recommended for building/iterating)
```bash
pip install platformio
cd firmware/pocketscribe
pio run -t upload           # builds + flashes over USB
pio device monitor          # serial logs at 115200
```
`platformio.ini` pins the board (ESP32-S3, 8 MB flash, OPI PSRAM) and the exact library versions.

---

## Option C — Arduino IDE
1. **Boards Manager** → install **esp32** by Espressif.
2. **Library Manager** → install: **WiFiManager** (tzapu), **GxEPD2** (ZinggJM), **ArduinoJson** (bblanchon).
3. Board: an **ESP32-S3** entry (e.g. "ESP32S3 Dev Module"). Set **PSRAM: OPI PSRAM**, **Flash Size: 8MB**, **USB CDC On Boot: Enabled**.
4. Open `firmware/pocketscribe/pocketscribe.ino` → **Upload**.

---

## After flashing
Continue to **[WIFI.md](./WIFI.md)** to connect the device to your network, then **[END_TO_END.md](./END_TO_END.md)** to record → sync → see it in the dashboard.
