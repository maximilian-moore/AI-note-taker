// board_pins.h — GPIO map for Waveshare ESP32-S3-ePaper-1.54.
//
// VERIFIED against Waveshare's official board repo:
//   github.com/waveshareteam/ESP32-S3-ePaper-1.54
//   - E-paper + power pins: 02_Example/.../07_BATT_PWR_Test/user_config.h
//   - Power polarity:        .../src/power/board_power_bsp.cpp
//   - microSD pins:          .../04_SD_Card/sdcard_bsp.cpp
//   - Audio (ES8311) pins:   .../08_Audio_Test codec profile "S3_ePaper_1_54"
//   - Battery ADC:           .../01_ADC_Test/adc_bsp.cpp (ADC1_CH3 = GPIO4)
//
// GPIO notes for this module:
//   - GPIO0  = BOOT button (input at runtime; held low at power-on = flash mode)
//   - GPIO19/20 = USB, do not repurpose
#pragma once

// ---- E-paper (GDEY0154D67 / SSD1681, 200x200) ----
#define EPD_BUSY    8
#define EPD_RST     9
#define EPD_DC      10
#define EPD_CS      11
#define EPD_SCK     12
#define EPD_MOSI    13

// ---- Board power rails ------------------------------------------------------
// Waveshare's board_power_bsp drives EPD & Audio enables LOW to power ON, and
// the VBAT sense rail HIGH to enable. (POWEER_*_ON() -> level 0; VBAT_ON -> 1.)
#define EPD_PWR_EN     6    // LOW = panel powered
#define AUDIO_PWR_EN   42   // LOW = audio codec powered
#define VBAT_PWR_EN    17   // HIGH = battery-sense rail enabled
#define EPD_PWR_ON     LOW
#define AUDIO_PWR_ON   LOW
#define VBAT_PWR_ON    HIGH

// ---- Shared I2C bus (ES8311 codec ctrl, PCF85063 RTC, SHTC3 sensor) ----
#define I2C_SDA     47
#define I2C_SCL     48
#define ES8311_I2C_ADDR 0x18   // ES8311 default 7-bit address

// ---- I2S audio to/from ES8311 (codec profile "S3_ePaper_1_54") ----
#define I2S_MCLK    14
#define I2S_BCLK    15
#define I2S_LRCK    38     // a.k.a. WS
#define I2S_DIN     16     // codec -> ESP32 (microphone capture)
#define I2S_DOUT    45     // ESP32 -> codec (speaker playback)
#define PA_ENABLE   46     // speaker amplifier enable

// ---- microSD via SD_MMC (1-bit) ----
#define SD_CLK      39
#define SD_CMD      41
#define SD_D0       40

// ---- Buttons ----
// BTN_A = Navigate (BOOT, GPIO0, active-LOW).
// BTN_B = Record (PWR button, GPIO18, active-LOW). VERIFIED on hardware
// (2026-07-19 GPIO hunt): the PWR button shorts GPIO18 to GND, reading LOW when
// pressed with an internal pull-up — same polarity as BOOT, not active-HIGH as
// originally guessed. GPIO18 is not a boot strap, so it's safe to wake on.
#define BTN_A_PIN   0      // BOOT button
#define BTN_B_PIN   18     // PWR/user button
#define BTN_ACTIVE_LOW 1   // BTN_A pulls LOW when pressed
#define BTN_B_ACTIVE_LOW 1 // BTN_B (PWR) pulls LOW when pressed

// ---- Battery voltage sense (LiPo) ----
// ADC1_CH3 = GPIO4. Requires VBAT_PWR_EN driven HIGH to enable the divider.
#define VBAT_ADC    4      // ADC1 channel 3; divider ratio in config.h
