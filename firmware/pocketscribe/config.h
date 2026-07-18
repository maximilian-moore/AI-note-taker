// PocketScribe firmware — compile-time config.
// Runtime values (Wi-Fi creds, backend URL, pairing token) are set during
// on-device provisioning (SoftAP captive portal) and stored in NVS — NOT here.
#pragma once

// ---- Board: Waveshare ESP32-S3-Touch-ePaper-1.54 (N8R8) ---------------------
// Pin map to be confirmed at hardware bring-up against the Waveshare schematic.
// Placeholders below are grouped by subsystem so Phase 1 can fill them in.

// E-paper (SPI)
// #define EPD_CS   ..
// #define EPD_DC   ..
// #define EPD_RST  ..
// #define EPD_BUSY ..

// Audio ES8311 (I2C control + I2S data)
// #define I2C_SDA  ..
// #define I2C_SCL  ..
// #define I2S_BCLK ..
// #define I2S_LRCK ..
// #define I2S_DIN  ..

// microSD (SPI or SDMMC)
// #define SD_CS    ..

// Buttons: interaction is BUTTONS ONLY (no touch assumed on this unit).
// Two usable buttons on the board (BOOT = GPIO0, PWR). Roles are provisional
// and finalized at bring-up (BOOT is flash-mode when held at power-on; PWR may
// tie into power management).
//   Button A = Navigate (short: next page/item, long: next section)
//   Button B = Record   (short: Quick Note, long: Meeting)
// #define BTN_NAV_PIN   ..   // Button A
// #define BTN_REC_PIN   ..   // Button B
// #define VBAT_ADC      ..   // battery voltage divider

// ---- Audio ------------------------------------------------------------------
#define AUDIO_SAMPLE_RATE   16000   // 16 kHz mono
#define AUDIO_CHUNK_SECONDS 300     // 5-min segments (resumable upload)

// ---- Capture semantics ------------------------------------------------------
#define BTN_LONGPRESS_MS    1500    // >= this = Meeting; shorter = Quick Note
