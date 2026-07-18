// ui.h — e-paper rendering (GxEPD2) for the PocketScribe screens.
//
// Panel: Waveshare 1.54" 200x200 B/W (SSD1681) -> GxEPD2_154_D67.
// Uses full refresh on screen changes and partial refresh for the recording
// timer / sync progress to avoid full-screen flashing (PRD FR-D7).
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_BW.h>       // https://github.com/ZinggJM/GxEPD2
#include "board_pins.h"
#include "config.h"

namespace ui {

GxEPD2_BW<GxEPD2_154_D67, GxEPD2_154_D67::HEIGHT>
    display(GxEPD2_154_D67(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static int partialCount = 0;

static void begin() {
#ifdef EPD_PWR_EN
  pinMode(EPD_PWR_EN, OUTPUT);
  digitalWrite(EPD_PWR_EN, HIGH);   // power the panel
#endif
  SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
  display.init(115200);
  display.setRotation(0);
  display.setTextColor(GxEPD_BLACK);
}

// --- low-level helpers -------------------------------------------------------
static void header(const char *title) {
  display.setTextSize(2);
  display.setCursor(4, 4);
  display.print(title);
  display.drawFastHLine(0, 24, 200, GxEPD_BLACK);
}

// Draw a titled screen with up to `n` body lines (small font). Full refresh.
static void screen(const char *title, const String *lines, int n, const char *footer = nullptr) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    header(title);
    display.setTextSize(1);
    int y = 32;
    for (int i = 0; i < n && y < 184; i++) {
      display.setCursor(4, y);
      display.print(lines[i].substring(0, 32));  // ~32 chars fit at size 1
      y += 12;
    }
    if (footer) {
      display.drawFastHLine(0, 186, 200, GxEPD_BLACK);
      display.setCursor(4, 190);
      display.print(footer);
    }
  } while (display.nextPage());
  partialCount = 0;
}

// --- screens -----------------------------------------------------------------
static void boot(const char *msg) {
  String l[1] = {String(msg)};
  screen("PocketScribe", l, 1, FW_VERSION);
}

static void setup(const char *apSsid, const char *apPass) {
  String l[5] = {
    "Wi-Fi setup needed.",
    "1. Join Wi-Fi:",
    String("   ") + apSsid,
    String("   pass ") + apPass,
    "2. Open the page,",
  };
  screen("Setup", l, 5, "then enter your Wi-Fi");
}

// Home/status with the three-state counts + last sync (FR-D1).
static void home(int notes, int meetings, int openTodos, int onDevice,
                 int processing, const String &lastSync, int battPct, bool wifi) {
  String l[6] = {
    String("Notes: ") + notes + "   Meetings: " + meetings,
    String("Open to-dos: ") + openTodos,
    String("On device: ") + onDevice + "  Processing: " + processing,
    String("Last sync: ") + (lastSync.length() ? lastSync : "never"),
    String("Batt ") + battPct + "%   Wi-Fi " + (wifi ? "OK" : "--"),
    "B = record   BB = sync",
  };
  screen("Home", l, 6, "A = browse screens");
}

// Full clear + header once when recording starts, so the partial timer updates
// below don't overlay leftover content from the previous screen.
static void recordingStart(const char *mode) {
  String l[1] = {String("Recording ") + mode + "..."};
  screen("Recording", l, 1, "B = stop");
}

static void recording(const char *mode, uint32_t seconds) {
  // partial refresh of just the timer area for a smooth counter
  display.setPartialWindow(0, 60, 200, 60);
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextSize(2);
    display.setCursor(4, 66);
    display.printf("* REC %s", mode);
    display.setTextSize(3);
    display.setCursor(4, 92);
    display.printf("%02u:%02u", seconds / 60, seconds % 60);
  } while (display.nextPage());
  if (++partialCount > EPD_PARTIAL_MAX) partialCount = 0;  // periodic de-ghost handled by caller
}

static void syncing(const char *phase, int seq, int count) {
  String l[2] = {String(phase), count ? (String("Chunk ") + seq + "/" + count) : String("")};
  screen("Syncing", l, 2, "please wait");
}

// A browsable list screen (Notes / Meetings / To-dos). `sel` highlights a row.
static void list(const char *title, const String *items, int n, int sel, const char *footer) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    header(title);
    display.setTextSize(1);
    int y = 32;
    for (int i = 0; i < n && y < 184; i++) {
      if (i == sel) { display.fillRect(0, y - 2, 200, 12, GxEPD_BLACK); display.setTextColor(GxEPD_WHITE); }
      display.setCursor(4, y);
      display.print(items[i].substring(0, 32));
      if (i == sel) display.setTextColor(GxEPD_BLACK);
      y += 12;
    }
    if (footer) { display.drawFastHLine(0, 186, 200, GxEPD_BLACK); display.setCursor(4, 190); display.print(footer); }
  } while (display.nextPage());
  partialCount = 0;
}

// A page of note text for on-device reading (FR-D9).
static void notePage(const char *title, const String &body, int page, int pages) {
  String lines[13];
  int n = 0;
  // naive wrap at ~32 chars, paginate 13 lines/page
  String w = body;
  int start = page * 13;
  int idx = 0;
  for (int i = 0; i < w.length() && n < 13; ) {
    String line = w.substring(i, i + 32);
    if (idx++ >= start) lines[n++] = line;
    i += 32;
  }
  String foot = String("Page ") + (page + 1) + "/" + max(1, pages) + "  B=play A=page";
  screen(title, lines, n, foot.c_str());
}

}  // namespace ui
