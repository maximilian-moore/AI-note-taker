// audio.h — ES8311 codec + I2S: record microphone to a WAV on SD, play WAV back.
//
// ⚠ BENCH-VERIFY: the ES8311 register sequence and the I2S/I2C pins are the
// highest-risk part of this firmware. Values here follow common ES8311 mic
// configs; confirm against Espressif's `es8311` component and the Waveshare
// schematic. A wrong sequence yields silence/noise, not damage.
//
// Uses the ESP-IDF I2S "standard" driver (arduino-esp32 core 3.x / ESP-IDF v5).
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <SD_MMC.h>
#include <driver/i2s_std.h>
#include "board_pins.h"
#include "config.h"

namespace audio {

static i2s_chan_handle_t rx_handle = nullptr;
static i2s_chan_handle_t tx_handle = nullptr;

// ---- ES8311 register helpers ----
static void es8311Write(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ES8311_I2C_ADDR);
  Wire.write(reg); Wire.write(val);
  Wire.endTransmission();
}

// Minimal ES8311 init for 16 kHz mono capture (mic) + playback from MCLK.
// Reference: Espressif esp-adf/esp_codec_dev es8311 driver.
static void es8311Init() {
  const uint8_t seq[][2] = {
    {0x45, 0x00}, {0x01, 0x30}, {0x02, 0x10}, {0x02, 0x00},
    {0x03, 0x10}, {0x16, 0x24}, {0x04, 0x10}, {0x05, 0x00},
    {0x0B, 0x00}, {0x0C, 0x00}, {0x10, 0x1F}, {0x11, 0x7F},
    {0x00, 0x80}, {0x0D, 0x01}, {0x0E, 0x02}, {0x12, 0x00},
    {0x13, 0x10}, {0x1C, 0x6A}, {0x37, 0x08},
    {0x17, 0xBF}, {0x14, 0x1A},   // ADC/mic gain (0x14 = mic PGA) — tune on bench
    {0x0A, 0x00}, {0x0F, 0x44},
  };
  for (auto &r : seq) es8311Write(r[0], r[1]);
}

// ---- I2S standard mode, shared TX+RX (full-duplex codec) ----
static void i2sInit() {
  i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle);

  i2s_std_config_t std_cfg = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
    .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
      .mclk = (gpio_num_t)I2S_MCLK,
      .bclk = (gpio_num_t)I2S_BCLK,
      .ws   = (gpio_num_t)I2S_LRCK,
      .dout = (gpio_num_t)I2S_DOUT,
      .din  = (gpio_num_t)I2S_DIN,
      .invert_flags = {false, false, false},
    },
  };
  i2s_channel_init_std_mode(tx_handle, &std_cfg);
  i2s_channel_init_std_mode(rx_handle, &std_cfg);
}

static void begin() {
  Wire.begin(I2C_SDA, I2C_SCL);
  es8311Init();
  i2sInit();
#ifdef PA_ENABLE
  pinMode(PA_ENABLE, OUTPUT);
  digitalWrite(PA_ENABLE, LOW);  // amp off until playback
#endif
}

// ---- WAV header (44 bytes, streaming: patched with real sizes on stop) ----
static void writeWavHeader(File &f, uint32_t dataBytes) {
  uint32_t rate = AUDIO_SAMPLE_RATE, byteRate = rate * AUDIO_CHANNELS * (AUDIO_BITS / 8);
  uint16_t blockAlign = AUDIO_CHANNELS * (AUDIO_BITS / 8);
  uint32_t chunkSize = 36 + dataBytes;
  auto w32 = [&](uint32_t v){ f.write((uint8_t*)&v, 4); };
  auto w16 = [&](uint16_t v){ f.write((uint8_t*)&v, 2); };
  f.write((const uint8_t*)"RIFF", 4); w32(chunkSize); f.write((const uint8_t*)"WAVE", 4);
  f.write((const uint8_t*)"fmt ", 4); w32(16); w16(1); w16(AUDIO_CHANNELS);
  w32(rate); w32(byteRate); w16(blockAlign); w16(AUDIO_BITS);
  f.write((const uint8_t*)"data", 4); w32(dataBytes);
}

// ---- Recorder: call begin/loop/end from the state machine ----
class Recorder {
 public:
  bool start(const char *path) {
    file_ = SD_MMC.open(path, FILE_WRITE);
    if (!file_) return false;
    dataBytes_ = 0;
    writeWavHeader(file_, 0);            // placeholder, patched in stop()
    i2s_channel_enable(rx_handle);
    recording_ = true;
    return true;
  }

  // Call frequently while recording; drains the I2S RX buffer to SD.
  void pump() {
    if (!recording_) return;
    static uint8_t buf[2048];
    size_t got = 0;
    if (i2s_channel_read(rx_handle, buf, sizeof(buf), &got, 20) == ESP_OK && got) {
      file_.write(buf, got);
      dataBytes_ += got;
    }
  }

  uint32_t seconds() const {
    return dataBytes_ / (AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * (AUDIO_BITS / 8));
  }

  void stop() {
    if (!recording_) return;
    i2s_channel_disable(rx_handle);
    file_.seek(0);
    writeWavHeader(file_, dataBytes_);   // patch real sizes
    file_.close();
    recording_ = false;
  }

  bool active() const { return recording_; }

 private:
  File file_;
  uint32_t dataBytes_ = 0;
  bool recording_ = false;
};

// ---- Simple blocking WAV playback to the speaker ----
static void play(const char *path) {
  File f = SD_MMC.open(path, FILE_READ);
  if (!f) return;
  f.seek(44);  // skip header
#ifdef PA_ENABLE
  digitalWrite(PA_ENABLE, HIGH);
#endif
  i2s_channel_enable(tx_handle);
  uint8_t buf[2048]; size_t got, written;
  while ((got = f.read(buf, sizeof(buf))) > 0) {
    i2s_channel_write(tx_handle, buf, got, &written, 100);
  }
  i2s_channel_disable(tx_handle);
#ifdef PA_ENABLE
  digitalWrite(PA_ENABLE, LOW);
#endif
  f.close();
}

}  // namespace audio
