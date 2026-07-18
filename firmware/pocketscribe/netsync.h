// netsync.h — Wi-Fi provisioning + sync with the backend.
//
// Wi-Fi onboarding (no hard-coded credentials):
//   On first boot (or when it can't join a known network) the device starts a
//   captive-portal access point "PocketScribe-Setup". You connect your phone to
//   it, a page opens automatically, and you enter your Wi-Fi name + password,
//   the backend URL, and the pairing token. These are saved to NVS (flash) and
//   reused on every later boot — WiFiManager handles the whole flow.
//
// Sync (matches the backend + tools/device_sim.py HTTP contract exactly):
//   - POST /ingest   : ordered byte-range chunks of one recording (multipart)
//   - GET  /device/state         : counts + recent notes/meetings/to-dos
//   - GET  /device/notes/{uid}   : full text for on-device reading
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiManager.h>      // https://github.com/tzapu/WiFiManager
#include <Preferences.h>
#include <ArduinoJson.h>      // https://arduinojson.org
#include <SD_MMC.h>
#include "config.h"

namespace net {

struct Config {
  String backendUrl;   // e.g. http://192.168.1.20:8080
  String token;        // device pairing token (matches backend .env)
  String deviceId;     // stable per-device id
};

static Config cfg;
static Preferences prefs;

static void loadConfig() {
  prefs.begin("pocketscribe", true);
  cfg.backendUrl = prefs.getString("url", "");
  cfg.token      = prefs.getString("token", "");
  cfg.deviceId   = prefs.getString("devid", "");
  prefs.end();
  if (cfg.deviceId.isEmpty()) {
    uint64_t mac = ESP.getEfuseMac();
    cfg.deviceId = "ps-" + String((uint32_t)(mac >> 24), HEX);
  }
}

static void saveConfig() {
  prefs.begin("pocketscribe", false);
  prefs.putString("url", cfg.backendUrl);
  prefs.putString("token", cfg.token);
  prefs.putString("devid", cfg.deviceId);
  prefs.end();
}

// Connect to Wi-Fi, running the captive-portal setup when needed. Set
// `forcePortal` to always open the portal (re-provisioning). `portalCb` lets
// the UI show "Setup mode — join PocketScribe-Setup". Persists the custom
// Backend URL + pairing token fields on save.
static bool begin(void (*portalCb)(const char * apSsid) = nullptr, bool forcePortal = false) {
  loadConfig();
  WiFiManager wm;
  WiFiManagerParameter pUrl("url", "Backend URL (http://ip:8080)", cfg.backendUrl.c_str(), 96);
  WiFiManagerParameter pTok("token", "Pairing token", cfg.token.c_str(), 96);
  wm.addParameter(&pUrl);
  wm.addParameter(&pTok);
  wm.setConfigPortalTimeout(300);  // 5 min, then retry/sleep
  if (portalCb) wm.setAPCallback([portalCb](WiFiManager *m){ portalCb(SETUP_AP_SSID); });

  bool ok = forcePortal ? wm.startConfigPortal(SETUP_AP_SSID, SETUP_AP_PASSWORD)
                        : wm.autoConnect(SETUP_AP_SSID, SETUP_AP_PASSWORD);
  if (ok) {
    if (strlen(pUrl.getValue())) cfg.backendUrl = pUrl.getValue();
    if (strlen(pTok.getValue())) cfg.token = pTok.getValue();
    saveConfig();
  }
  return ok;
}

// ---- HTTP helpers ----
static bool getJson(const String &path, JsonDocument &doc) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(cfg.backendUrl + path);
  http.addHeader("X-Device-Token", cfg.token);
  http.setTimeout(HTTP_TIMEOUT_MS);
  int code = http.GET();
  bool ok = false;
  if (code == 200) ok = (deserializeJson(doc, http.getStream()) == DeserializationError::Ok);
  http.end();
  return ok;
}

static bool fetchState(JsonDocument &doc)          { return getJson("/device/state", doc); }
static bool fetchNote(const String &uid, JsonDocument &doc) { return getJson("/device/notes/" + uid, doc); }

// ---- Upload one recording as ordered byte-range multipart chunks ----
static bool postChunk(const String &uid, const String &mode, int seq, bool final,
                      uint32_t durationS, const uint8_t *data, size_t len) {
  const String boundary = "----pocketscribe";
  String head;
  auto field = [&](const String &name, const String &val) {
    head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n" + val + "\r\n";
  };
  field("device_id", cfg.deviceId);
  field("recording_uid", uid);
  field("mode", mode);
  field("seq", String(seq));
  field("final", final ? "true" : "false");
  field("audio_ext", "wav");
  field("duration_s", String(durationS));
  head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"chunk\"; "
          "filename=\"" + uid + "." + seq + ".wav\"\r\nContent-Type: audio/wav\r\n\r\n";
  const String tail = "\r\n--" + boundary + "--\r\n";

  size_t total = head.length() + len + tail.length();
  uint8_t *body = (uint8_t *)ps_malloc(total);   // PSRAM
  if (!body) return false;
  size_t o = 0;
  memcpy(body + o, head.c_str(), head.length()); o += head.length();
  memcpy(body + o, data, len);                   o += len;
  memcpy(body + o, tail.c_str(), tail.length()); o += tail.length();

  bool ok = false;
  for (int attempt = 0; attempt < UPLOAD_MAX_RETRIES && !ok; attempt++) {
    if (attempt) delay(2000 << attempt);         // 2s,4s,8s,16s backoff
    HTTPClient http;
    http.begin(cfg.backendUrl + "/ingest");
    http.addHeader("X-Device-Token", cfg.token);
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    http.setTimeout(HTTP_TIMEOUT_MS);
    int code = http.POST(body, total);
    ok = (code == 200);
    http.end();
  }
  free(body);
  return ok;
}

// Slice a WAV file on SD into UPLOAD_CHUNK_BYTES pieces and upload them.
// progressCb(seq, count) drives the on-screen "Uploading n/m…".
static bool uploadRecording(const String &path, const String &uid, const String &mode,
                            uint32_t durationS, void (*progressCb)(int, int) = nullptr) {
  File f = SD_MMC.open(path, FILE_READ);
  if (!f) return false;
  size_t size = f.size();
  int count = (int)((size + UPLOAD_CHUNK_BYTES - 1) / UPLOAD_CHUNK_BYTES);
  if (count == 0) count = 1;

  static uint8_t buf[UPLOAD_CHUNK_BYTES];
  bool ok = true;
  for (int seq = 0; seq < count && ok; seq++) {
    size_t got = f.read(buf, UPLOAD_CHUNK_BYTES);
    bool final = (seq == count - 1);
    if (progressCb) progressCb(seq + 1, count);
    ok = postChunk(uid, mode, seq, final, durationS, buf, got);
  }
  f.close();
  return ok;
}

}  // namespace net
