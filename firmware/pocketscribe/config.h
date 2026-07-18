// config.h — user-tunable firmware constants (NOT pins; see board_pins.h).
// Runtime secrets (Wi-Fi creds, backend URL, pairing token) are entered during
// on-device provisioning and stored in NVS — never hard-coded here.
#pragma once

// ---- Identity / provisioning ----
#define FW_VERSION        "0.1.0"
#define SETUP_AP_SSID     "PocketScribe-Setup"   // captive-portal AP on first boot
#define SETUP_AP_PASSWORD "pocket1234"           // 8+ chars; shown in the quick-start

// ---- Audio capture ----
#define AUDIO_SAMPLE_RATE   16000   // 16 kHz mono
#define AUDIO_BITS          16
#define AUDIO_CHANNELS      1

// ---- Upload ----
#define UPLOAD_CHUNK_BYTES  (32 * 1024)   // must match tools/device_sim.py
#define HTTP_TIMEOUT_MS     20000
#define UPLOAD_MAX_RETRIES  4             // exponential backoff between retries

// ---- Buttons ----
#define BTN_DEBOUNCE_MS     30
#define BTN_LONGPRESS_MS    1500   // >= this = Meeting (Button B) / next section (Button A)
#define BTN_DOUBLE_GAP_MS   350    // two presses within this window = double-press (Sync now)

// ---- Power ----
#define VBAT_DIVIDER        2.0     // on-board resistor divider ratio — VERIFY
#define VBAT_FULL_MV        4200
#define VBAT_EMPTY_MV       3300
#define VBAT_LOW_WARN_MV    3450    // warn + finalize current recording below this
#define IDLE_SLEEP_MS       120000  // deep-sleep after this much inactivity

// ---- Display ----
#define EPD_PARTIAL_MAX     20      // full refresh after N partial refreshes (de-ghost)
