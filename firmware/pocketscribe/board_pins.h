// board_pins.h — GPIO map for Waveshare ESP32-S3-ePaper-1.54 (N8R8).
//
// CONFIRMED from Waveshare example code / docs:
//   E-paper: BUSY=5, RST=7, DC=4, CS=10, SCK=1, MOSI=2, PWR_EN=6
//
// TO VERIFY at bench bring-up (values below are best-effort placeholders based
// on the board's peripherals; check against the Waveshare schematic before you
// trust them — a wrong pin just means "no audio"/"no SD", not damage):
//   ES8311 audio (I2S + I2C control), microSD (SD_MMC), buttons, battery ADC.
//
// GPIO notes for this module (from Waveshare docs):
//   - GPIO0 = BOOT button (usable as input at runtime; held low at power-on = flash mode)
//   - GPIO19/20 = USB, do not repurpose
//   - GPIO33..37 = Octal PSRAM, unavailable
#pragma once

// ---- E-paper (SSD1681, 200x200) — CONFIRMED ----
#define EPD_BUSY    5
#define EPD_RST     7
#define EPD_DC      4
#define EPD_CS      10
#define EPD_SCK     1
#define EPD_MOSI    2
#define EPD_PWR_EN  6      // panel power enable (drive HIGH to power the display)

// ---- Shared I2C bus (ES8311 codec ctrl, PCF85063 RTC, SHTC3 sensor) — VERIFY ----
#define I2C_SDA     8
#define I2C_SCL     9
#define ES8311_I2C_ADDR 0x18   // ES8311 default 7-bit address

// ---- I2S audio to/from ES8311 — VERIFY ----
#define I2S_MCLK    16
#define I2S_BCLK    15
#define I2S_LRCK    17     // a.k.a. WS
#define I2S_DIN     18     // codec -> ESP32 (microphone capture)
#define I2S_DOUT    45     // ESP32 -> codec (speaker playback)
#define PA_ENABLE   46     // speaker amplifier enable — VERIFY (may not exist)

// ---- microSD via SD_MMC (1-bit) — VERIFY ----
#define SD_CLK      39
#define SD_CMD      38
#define SD_D0       40

// ---- Buttons (2 usable) — VERIFY which is safe for which role ----
// BTN_A = Navigate, BTN_B = Record (see PRD §6.0). BOOT is GPIO0.
#define BTN_A_PIN   0      // BOOT button
#define BTN_B_PIN   47     // PWR/user button — VERIFY (PWR may be power-mgmt only)
#define BTN_ACTIVE_LOW 1   // buttons pull the line LOW when pressed

// ---- Battery voltage sense (LiPo) — VERIFY ----
#define VBAT_ADC    3      // ADC1 channel; divider ratio in config.h
