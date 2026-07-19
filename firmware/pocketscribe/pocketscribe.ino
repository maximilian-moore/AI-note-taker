// pocketscribe.ino — PocketScribe AI note taker firmware (Arduino-ESP32).
//
// Flow: press Button B to record (short = Quick Note, long = Meeting) -> audio
// is saved to microSD -> double-press Button B to sync (upload + pull results)
// -> browse notes/meetings/to-dos and read/play them with Button A.
//
// See PRD.md §6 for the full behaviour and docs/ for flashing + Wi-Fi setup.
// Libraries: WiFiManager, GxEPD2, ArduinoJson, ESP32 core (SD_MMC, I2S, Wire).
#include <Arduino.h>
#include <SD_MMC.h>
#include <ArduinoJson.h>
#include <esp_sleep.h>
#include <vector>
#include "board_pins.h"
#include "config.h"
#include "buttons.h"
#include "audio.h"
#include "netsync.h"
#include "ui.h"

// Bring-up diagnostic: 1 = print raw button pin levels 2x/sec so you can see
// whether GPIO0 (Button A) actually toggles when pressed. Set 0 to silence.
#define BTN_DEBUG 1

enum Screen { S_HOME, S_TODOS, S_NOTES, S_MEETINGS, S_DETAIL, S_RECORDING };

Buttons buttons;
audio::Recorder recorder;
DynamicJsonDocument state(8192);   // last /device/state
DynamicJsonDocument noteDoc(8192); // opened note for reading

Screen screen = S_HOME;
Screen lastListScreen = S_NOTES;
int sel = 0;                       // highlighted row in a list
int detailPage = 0;
String detailUid, detailBody, detailTitle;
String recUid, recMode;
uint32_t recStart = 0, lastActivity = 0;
bool haveState = false;

// ---------------------------------------------------------------- helpers ----
static int battPercent() {
  int mv = analogReadMilliVolts(VBAT_ADC) * VBAT_DIVIDER;
  int pct = (mv - VBAT_EMPTY_MV) * 100 / (VBAT_FULL_MV - VBAT_EMPTY_MV);
  return constrain(pct, 0, 100);
}

static void toast(const char *phase, int a = 0, int b = 0) { ui::syncing(phase, a, b); }

static void refreshState() {
  haveState = net::fetchState(state);
}

// Count recordings on SD that haven't been uploaded yet (the "on device" state).
static int pendingCount() {
  int n = 0;
  File dir = SD_MMC.open("/rec");
  if (!dir) return 0;
  for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
    String name = f.name();
    if (name.endsWith(".json")) {
      DynamicJsonDocument m(256);
      if (deserializeJson(m, f) == DeserializationError::Ok && !m["uploaded"].as<bool>()) n++;
    }
  }
  return n;
}

static void drawHome() {
  int notes = haveState ? state["counts"]["notes"] | 0 : 0;
  int meetings = haveState ? state["counts"]["meetings"] | 0 : 0;
  int todos = haveState ? state["counts"]["open_todos"] | 0 : 0;
  int processing = haveState ? state["counts"]["processing"] | 0 : 0;
  String last = haveState ? String((const char *)(state["last_sync_at"] | "")) : "";
  last = last.length() >= 16 ? last.substring(0, 16) : last;
  ui::home(notes, meetings, todos, pendingCount(), processing, last,
           battPercent(), WiFi.status() == WL_CONNECTED);
}

// Build display lines from a JSON array field of /device/state.
static int buildList(const char *field, String *out, int maxN) {
  int n = 0;
  if (!haveState) return 0;
  for (JsonObject it : state[field].as<JsonArray>()) {
    if (n >= maxN) break;
    if (strcmp(field, "open_todos") == 0) {
      out[n++] = String("- ") + (const char *)(it["text"] | "");
    } else {
      const char *t = it["title"] | "(processing...)";
      const char *c = it["category"] | "";
      out[n++] = String(t) + (strlen(c) ? String("  [") + c + "]" : "");
    }
  }
  return n;
}

static void drawCurrent() {
  static String items[16];
  switch (screen) {
    case S_HOME: drawHome(); break;
    case S_TODOS: ui::list("To-dos", items, buildList("open_todos", items, 12), -1, "A=section"); break;
    case S_NOTES: { int n = buildList("notes", items, 12); ui::list("Notes", items, n, constrain(sel, 0, max(0, n - 1)), "B=open A=next"); break; }
    case S_MEETINGS: { int n = buildList("meetings", items, 12); ui::list("Meetings", items, n, constrain(sel, 0, max(0, n - 1)), "B=open A=next"); break; }
    case S_DETAIL: {
      int pages = max(1, (int)(detailBody.length() / (32 * 13)) + 1);
      ui::notePage(detailTitle.c_str(), detailBody, detailPage, pages);
      break;
    }
    case S_RECORDING: break;  // drawn by the recording loop
  }
}

// ------------------------------------------------------------- actions -------
static void startRecording(const String &mode) {
  SD_MMC.mkdir("/rec");
  recUid = net::cfg.deviceId + "-" + String(millis(), HEX);
  recMode = mode;
  String path = "/rec/" + recUid + ".wav";
  if (!recorder.start(path.c_str())) { toast("SD error"); return; }
  recStart = millis();
  screen = S_RECORDING;
  ui::recordingStart(mode.c_str());   // full clear so the timer doesn't overlay Home
}

static void stopRecording() {
  recorder.stop();
  uint32_t dur = (millis() - recStart) / 1000;
  // manifest so sync knows what to upload (kept after upload for playback)
  DynamicJsonDocument m(256);
  m["uid"] = recUid; m["mode"] = recMode; m["duration_s"] = dur; m["uploaded"] = false;
  File mf = SD_MMC.open("/rec/" + recUid + ".json", FILE_WRITE);
  if (mf) { serializeJson(m, mf); mf.close(); }
  screen = S_HOME;
  drawCurrent();
}

// Double-press = sync: upload every pending recording, then pull fresh state.
static void doSync() {
  if (WiFi.status() != WL_CONNECTED) { toast("No Wi-Fi"); delay(1200); drawCurrent(); return; }

  // Phase 1: collect pending uids first (don't mutate the dir while iterating it).
  std::vector<String> pending;
  File dir = SD_MMC.open("/rec");
  if (dir) {
    for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
      String name = String(f.name());
      if (!name.endsWith(".json")) continue;
      DynamicJsonDocument m(256);
      if (deserializeJson(m, f) == DeserializationError::Ok && !m["uploaded"].as<bool>())
        pending.push_back(m["uid"].as<String>());
    }
    dir.close();
  }

  // Phase 2: upload each and mark it uploaded (keep audio on SD for playback).
  for (const String &uid : pending) {
    DynamicJsonDocument m(256);
    File rf = SD_MMC.open("/rec/" + uid + ".json", FILE_READ);
    if (!rf) continue;
    bool okr = deserializeJson(m, rf) == DeserializationError::Ok;
    rf.close();
    if (!okr) continue;
    bool ok = net::uploadRecording("/rec/" + uid + ".wav", uid, m["mode"].as<String>(),
                                   m["duration_s"] | 0,
                                   [](int s, int c){ ui::syncing("Uploading", s, c); });
    if (ok) {
      m["uploaded"] = true;
      File wf = SD_MMC.open("/rec/" + uid + ".json", FILE_WRITE);
      if (wf) { serializeJson(m, wf); wf.close(); }
    }
  }

  toast("Fetching results");
  refreshState();
  screen = S_HOME;
  drawHome();
}

static void openDetail() {
  const char *field = (screen == S_MEETINGS) ? "meetings" : "notes";
  JsonArray arr = state[field].as<JsonArray>();
  if (sel < 0 || sel >= (int)arr.size()) return;
  detailUid = (const char *)arr[sel]["uid"];
  lastListScreen = screen;
  toast("Loading");
  if (net::fetchNote(detailUid, noteDoc) && noteDoc["ready"].as<bool>()) {
    detailTitle = (const char *)(noteDoc["title"] | "Note");
    detailBody = (const char *)(noteDoc["cleaned_text"] | "");
    detailPage = 0;
    screen = S_DETAIL;
  } else {
    toast("Not ready yet"); delay(1000); screen = lastListScreen;
  }
  drawCurrent();
}

static void nextSection() {
  sel = 0;
  screen = (screen == S_HOME) ? S_TODOS : (screen == S_TODOS) ? S_NOTES
         : (screen == S_NOTES) ? S_MEETINGS : S_HOME;
  Serial.printf("[nav] -> screen=%d\n", (int)screen);
}

// --------------------------------------------------------------- lifecycle ---
void setup() {
  Serial.begin(115200);

  // Power the board rails BEFORE touching any peripheral. On this board the EPD
  // and audio power enables are active-LOW and the battery-sense rail is
  // active-HIGH (see board_pins.h / Waveshare board_power_bsp). Getting this
  // wrong leaves the panel/codec unpowered -> blank screen + I2C failures.
  pinMode(VBAT_PWR_EN, OUTPUT);  digitalWrite(VBAT_PWR_EN, VBAT_PWR_ON);
  pinMode(EPD_PWR_EN, OUTPUT);   digitalWrite(EPD_PWR_EN, EPD_PWR_ON);
  pinMode(AUDIO_PWR_EN, OUTPUT); digitalWrite(AUDIO_PWR_EN, AUDIO_PWR_ON);
  delay(100);                    // let the rails settle before init

  ui::begin();
  ui::boot("Starting...");

  if (!SD_MMC.setPins(SD_CLK, SD_CMD, SD_D0) || !SD_MMC.begin("/sdcard", true)) {
    ui::boot("Insert microSD");   // recording needs the card
  }
  audio::begin();

  // Recovery: hold Button B (PWR) during power-on to force the Wi-Fi setup
  // portal. NOTE: must NOT use Button A here — A is BOOT/GPIO0, a boot strap;
  // holding it at reset puts the ESP32-S3 in USB download mode and the app
  // never runs. GPIO18 (PWR) is not a strap, so it's safe to sample at boot.
  buttons.begin();
  pinMode(BTN_B_PIN, BTN_B_ACTIVE_LOW ? INPUT_PULLUP : INPUT_PULLDOWN);
  bool forceSetup = (digitalRead(BTN_B_PIN) == (BTN_B_ACTIVE_LOW ? LOW : HIGH));

  ui::boot("Connecting Wi-Fi...");
  net::begin([](const char *ap){ ui::setup(ap, SETUP_AP_PASSWORD); }, forceSetup);

  refreshState();
  screen = S_HOME;
  drawHome();
  lastActivity = millis();
}

void loop() {
  // While recording: drain audio to SD and update the timer once a second.
  if (screen == S_RECORDING) {
    recorder.pump();
    static uint32_t lastTick = 0;
    // Update every 3s, not 1s: each e-paper refresh blocks the loop (~0.5s
    // partial) and button polling with it, so a frequent tick makes Stop feel
    // laggy. 3s keeps a live-ish counter while leaving the loop free to catch a
    // B press promptly. Wall-clock elapsed (not byte-derived) so the timer
    // advances even if mic capture yields no data; recorder.seconds() (byte
    // count) is used only for the stored WAV duration.
    if (millis() - lastTick > 3000) {
      lastTick = millis();
      ui::recording(recMode.c_str(), (millis() - recStart) / 1000);
    }
    if (battPercent() <= 5) stopRecording();   // FR-P2: finalize on low battery
  }

#if BTN_DEBUG
  {
    // Raw levels straight from the pins (no debounce). Press A: gpio0 should
    // flip 1->0 (active-low). Press B (PWR): gpio18 should flip 0->1.
    static uint32_t dbgT = 0;
    if (millis() - dbgT > 500) {
      dbgT = millis();
      Serial.printf("[raw] A/gpio%d=%d  B/gpio%d=%d\n",
                    BTN_A_PIN, digitalRead(BTN_A_PIN),
                    BTN_B_PIN, digitalRead(BTN_B_PIN));
    }
  }
#endif

  BtnEvent e = buttons.poll();
  if (e != BTN_NONE) {
    // Diagnostic: watch on the serial monitor to confirm A/B events fire.
    // e: 1=A_SHORT 2=A_LONG 3=B_SHORT 4=B_LONG 5=B_DOUBLE ; screen 0=Home.
    Serial.printf("[btn] e=%d screen=%d\n", (int)e, (int)screen);
    lastActivity = millis();
  }

  switch (e) {
    case BTN_B_SHORT:
      if (screen == S_RECORDING) stopRecording();
      else if (screen == S_NOTES || screen == S_MEETINGS) openDetail();
      else if (screen == S_DETAIL) { String p = "/rec/" + detailUid + ".wav"; if (SD_MMC.exists(p)) audio::play(p.c_str()); }
      else startRecording("quicknote");
      break;
    case BTN_B_LONG:
      if (screen == S_RECORDING) stopRecording();
      else startRecording("meeting");
      break;
    case BTN_B_DOUBLE:
      doSync();
      break;
    case BTN_A_SHORT:
      // Short A always advances to the next section (Home -> To-dos -> Notes ->
      // Meetings -> Home) so a single tap cycles every screen. Detail is not a
      // section, so there a short tap pages through the note text instead.
      if (screen == S_DETAIL) { detailPage++; drawCurrent(); }
      else { nextSection(); drawCurrent(); }
      break;
    case BTN_A_LONG:
      // Long A: in Detail, back to the list. In a list, scroll the selection to
      // the next item (short A is now reserved for section cycling). On Home, a
      // long A triggers Sync (moved off the old B double-tap). To-dos falls
      // through to a section advance.
      if (screen == S_DETAIL) { screen = lastListScreen; drawCurrent(); }
      else if (screen == S_NOTES || screen == S_MEETINGS) { sel++; drawCurrent(); }
      else if (screen == S_HOME) { doSync(); }
      else { nextSection(); drawCurrent(); }
      break;
    default: break;
  }

  // Idle -> deep sleep; a Button B press wakes it. NOTE: wake on B (GPIO18),
  // NOT A. ext1 wake resets the chip, and the ROM samples strapping pins at
  // reset. BTN_A = GPIO0 is a strap: if it's still held LOW when the ROM reads
  // it (very likely during a real press), the chip enters USB download mode and
  // the app never runs. GPIO18 is RTC-capable and not a strap, so it's safe.
  if (screen != S_RECORDING && millis() - lastActivity > IDLE_SLEEP_MS) {
    ui::boot("Sleeping - press B");
    esp_sleep_enable_ext1_wakeup(1ULL << BTN_B_PIN,
                                 BTN_B_ACTIVE_LOW ? ESP_EXT1_WAKEUP_ANY_LOW : ESP_EXT1_WAKEUP_ANY_HIGH);
    esp_deep_sleep_start();
  }
  delay(5);
}
