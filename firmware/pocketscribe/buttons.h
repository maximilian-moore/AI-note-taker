// buttons.h — debounced two-button input with short / long / double detection.
// Emits high-level events consumed by the state machine in the main sketch.
#pragma once
#include <Arduino.h>
#include "board_pins.h"
#include "config.h"

enum BtnEvent {
  BTN_NONE = 0,
  BTN_A_SHORT, BTN_A_LONG,          // Navigate: next item / next section
  BTN_B_SHORT, BTN_B_LONG,          // Record: quick note / meeting (context-dependent)
  BTN_B_DOUBLE                      // Sync now (any screen)
};

class Button {
 public:
  explicit Button(uint8_t pin) : pin_(pin) {}

  void begin() { pinMode(pin_, BTN_ACTIVE_LOW ? INPUT_PULLUP : INPUT_PULLDOWN); }

  // Returns 0 (none), 1 (short), 2 (long), 3 (double) — poll every loop().
  uint8_t poll() {
    bool down = (digitalRead(pin_) == (BTN_ACTIVE_LOW ? LOW : HIGH));
    uint32_t nowMs = millis();
    uint8_t out = 0;

    if (down && !pressed_) {                 // edge: press
      if (nowMs - lastRelease_ < BTN_DEBOUNCE_MS) return 0;
      pressed_ = true; pressStart_ = nowMs; longFired_ = false;
    } else if (down && pressed_) {           // held
      if (!longFired_ && nowMs - pressStart_ >= BTN_LONGPRESS_MS) {
        longFired_ = true; out = 2;          // long fires as soon as threshold hit
      }
    } else if (!down && pressed_) {          // edge: release
      pressed_ = false; lastRelease_ = nowMs;
      if (longFired_) { pendingShort_ = false; return 0; }   // long already emitted
      // short press: defer to detect a possible double
      if (pendingShort_ && nowMs - firstShort_ <= BTN_DOUBLE_GAP_MS) {
        pendingShort_ = false; out = 3;      // double
      } else {
        pendingShort_ = true; firstShort_ = nowMs;
      }
    }

    // resolve a lone short press once the double-press window elapses
    if (pendingShort_ && nowMs - firstShort_ > BTN_DOUBLE_GAP_MS) {
      pendingShort_ = false; out = 1;
    }
    return out;
  }

 private:
  uint8_t pin_;
  bool pressed_ = false, longFired_ = false, pendingShort_ = false;
  uint32_t pressStart_ = 0, lastRelease_ = 0, firstShort_ = 0;
};

class Buttons {
 public:
  Buttons() : a_(BTN_A_PIN), b_(BTN_B_PIN) {}
  void begin() { a_.begin(); b_.begin(); }

  BtnEvent poll() {
    uint8_t ra = a_.poll();
    if (ra == 1) return BTN_A_SHORT;
    if (ra == 2) return BTN_A_LONG;
    uint8_t rb = b_.poll();
    if (rb == 1) return BTN_B_SHORT;
    if (rb == 2) return BTN_B_LONG;
    if (rb == 3) return BTN_B_DOUBLE;
    return BTN_NONE;
  }

 private:
  Button a_, b_;
};
