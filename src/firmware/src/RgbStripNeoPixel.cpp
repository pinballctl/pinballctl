#include "drivers/RgbStrip/NeoPixel.h"

#include <Adafruit_NeoPixel.h>
#include <math.h>
#include <memory>
#include <vector>

namespace {

struct StripState {
  int pin = -1;
  int pixel_count = 0;
  int logical_pixel_count = 0;
  std::unique_ptr<Adafruit_NeoPixel> strip;
  std::vector<uint32_t> base;
  std::vector<uint32_t> frame;
};

struct BlinkEffect {
  int pin = -1;
  std::vector<uint16_t> indexes;
  uint32_t on_color = 0;
  bool is_on = true;
  uint32_t interval_ms = 150;
  uint32_t next_toggle_ms = 0;
  uint32_t toggles_remaining = 0;
};

std::vector<StripState> g_strips;
std::vector<BlinkEffect> g_effects;
uint16_t g_batch_depth = 0;
bool g_batch_dirty = false;
std::vector<int> g_batch_pins;

constexpr int kMaxPixelsPerStrip = 2048;
constexpr int kMaxStrips = 16;

bool parseHexNibble(char c, uint8_t* out) {
  if (!out) return false;
  if (c >= '0' && c <= '9') {
    *out = static_cast<uint8_t>(c - '0');
    return true;
  }
  if (c >= 'a' && c <= 'f') {
    *out = static_cast<uint8_t>(10 + (c - 'a'));
    return true;
  }
  if (c >= 'A' && c <= 'F') {
    *out = static_cast<uint8_t>(10 + (c - 'A'));
    return true;
  }
  return false;
}

bool parseHexColor(const String& color_hex, uint32_t* out) {
  if (!out) return false;
  String s = color_hex;
  s.trim();
  if (s.startsWith("#")) s = s.substring(1);
  if (s.length() != 6) return false;
  uint8_t n0 = 0;
  uint8_t n1 = 0;
  uint8_t n2 = 0;
  uint8_t n3 = 0;
  uint8_t n4 = 0;
  uint8_t n5 = 0;
  if (!parseHexNibble(s[0], &n0) || !parseHexNibble(s[1], &n1) ||
      !parseHexNibble(s[2], &n2) || !parseHexNibble(s[3], &n3) ||
      !parseHexNibble(s[4], &n4) || !parseHexNibble(s[5], &n5)) {
    return false;
  }
  const uint8_t r = static_cast<uint8_t>((n0 << 4) | n1);
  const uint8_t g = static_cast<uint8_t>((n2 << 4) | n3);
  const uint8_t b = static_cast<uint8_t>((n4 << 4) | n5);
  *out = (static_cast<uint32_t>(r) << 16) |
         (static_cast<uint32_t>(g) << 8) |
         static_cast<uint32_t>(b);
  return true;
}

uint8_t scale8(float brightness, uint8_t value) {
  if (brightness <= 0.0f) return 0;
  if (brightness >= 1.0f) return value;
  constexpr float kBrightnessGamma = 2.2f;
  float perceptual = powf(brightness, kBrightnessGamma) * brightness;
  float scaled = static_cast<float>(value) * perceptual;
  if (scaled <= 0.0f) return 0;
  if (scaled >= 255.0f) return 255;
  return static_cast<uint8_t>(scaled + 0.5f);
}

uint32_t scaleColor(float brightness, uint32_t color) {
  const uint8_t r = static_cast<uint8_t>((color >> 16) & 0xFFu);
  const uint8_t g = static_cast<uint8_t>((color >> 8) & 0xFFu);
  const uint8_t b = static_cast<uint8_t>(color & 0xFFu);
  return (static_cast<uint32_t>(scale8(brightness, r)) << 16) |
         (static_cast<uint32_t>(scale8(brightness, g)) << 8) |
         static_cast<uint32_t>(scale8(brightness, b));
}

void setPixelRaw(StripState* strip, int idx, uint32_t color) {
  if (!strip || !strip->strip || idx < 0 || idx >= strip->pixel_count) return;
  const uint8_t r = static_cast<uint8_t>((color >> 16) & 0xFFu);
  const uint8_t g = static_cast<uint8_t>((color >> 8) & 0xFFu);
  const uint8_t b = static_cast<uint8_t>(color & 0xFFu);
  strip->strip->setPixelColor(static_cast<uint16_t>(idx), r, g, b);
}

StripState* findStrip(int pin) {
  for (size_t i = 0; i < g_strips.size(); ++i) {
    if (g_strips[i].pin == pin) return &g_strips[i];
  }
  return nullptr;
}

void appendUniquePin(std::vector<int>* pins, int pin) {
  if (!pins) return;
  for (size_t i = 0; i < pins->size(); ++i) {
    if ((*pins)[i] == pin) return;
  }
  pins->push_back(pin);
}

void markBatchDirtyPin(int pin) {
  g_batch_dirty = true;
  appendUniquePin(&g_batch_pins, pin);
}

bool indexInList(const std::vector<uint16_t>& indexes, uint16_t idx) {
  for (size_t i = 0; i < indexes.size(); ++i) {
    if (indexes[i] == idx) return true;
  }
  return false;
}

bool hasActiveBlinkForPixel(int pin, uint16_t idx) {
  for (size_t i = 0; i < g_effects.size(); ++i) {
    const BlinkEffect& fx = g_effects[i];
    if (fx.pin != pin) continue;
    if (fx.toggles_remaining == 0) continue;
    if (indexInList(fx.indexes, idx)) return true;
  }
  return false;
}

void pruneEffectsForPinToLogicalCount(int pin, int logical_count) {
  if (logical_count < 0) logical_count = 0;
  for (size_t i = 0; i < g_effects.size();) {
    BlinkEffect& fx = g_effects[i];
    if (fx.pin != pin) {
      ++i;
      continue;
    }
    std::vector<uint16_t> kept;
    kept.reserve(fx.indexes.size());
    for (size_t j = 0; j < fx.indexes.size(); ++j) {
      const uint16_t idx = fx.indexes[j];
      if (idx < static_cast<uint16_t>(logical_count)) kept.push_back(idx);
    }
    fx.indexes.swap(kept);
    if (fx.indexes.empty()) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    ++i;
  }
}

void removeEffectsForPinIndexes(int pin, const std::vector<uint16_t>& indexes) {
  if (indexes.empty()) return;
  for (size_t i = 0; i < g_effects.size();) {
    BlinkEffect& fx = g_effects[i];
    if (fx.pin != pin) {
      ++i;
      continue;
    }
    std::vector<uint16_t> kept;
    kept.reserve(fx.indexes.size());
    for (size_t j = 0; j < fx.indexes.size(); ++j) {
      const uint16_t idx = fx.indexes[j];
      if (!indexInList(indexes, idx)) kept.push_back(idx);
    }
    fx.indexes.swap(kept);
    if (fx.indexes.empty()) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    ++i;
  }
}

bool initStrip(StripState* strip, int pin, int pixel_count, String* error) {
  if (!strip) {
    if (error) *error = "alloc_failed";
    return false;
  }
  if (pin < 0) {
    if (error) *error = "bad_pin";
    return false;
  }
  if (pixel_count < 1 || pixel_count > kMaxPixelsPerStrip) {
    if (error) *error = "bad_pixel_count";
    return false;
  }

  std::unique_ptr<Adafruit_NeoPixel> driver(
      new Adafruit_NeoPixel(static_cast<uint16_t>(pixel_count), static_cast<int16_t>(pin), NEO_GRB + NEO_KHZ800));
  if (!driver) {
    if (error) *error = "alloc_failed";
    return false;
  }
  driver->begin();
  driver->clear();
  driver->show();

  strip->pin = pin;
  strip->pixel_count = pixel_count;
  strip->logical_pixel_count = pixel_count;
  strip->strip = std::move(driver);
  strip->base.assign(static_cast<size_t>(pixel_count), 0);
  strip->frame.assign(static_cast<size_t>(pixel_count), 0);
  return true;
}

StripState* ensureStrip(int pin, int pixel_count, String* error) {
  if (pixel_count < 1 || pixel_count > kMaxPixelsPerStrip) {
    if (error) *error = "bad_pixel_count";
    return nullptr;
  }
  for (size_t i = 0; i < g_strips.size(); ++i) {
    if (g_strips[i].pin != pin) continue;
    StripState& strip = g_strips[i];
    if (!strip.strip) break;
    if (strip.pixel_count == pixel_count) {
      const int old_logical = strip.logical_pixel_count;
      strip.logical_pixel_count = pixel_count;
      if (strip.logical_pixel_count < old_logical) {
        for (int j = strip.logical_pixel_count; j < strip.pixel_count; ++j) {
          strip.base[static_cast<size_t>(j)] = 0;
          strip.frame[static_cast<size_t>(j)] = 0;
        }
        pruneEffectsForPinToLogicalCount(pin, strip.logical_pixel_count);
        if (g_batch_depth > 0) {
          markBatchDirtyPin(pin);
        } else {
          for (int j = 0; j < strip.pixel_count; ++j) {
            setPixelRaw(&strip, j, strip.base[static_cast<size_t>(j)]);
          }
          strip.strip->show();
        }
      }
      return &strip;
    }
    pruneEffectsForPinToLogicalCount(pin, 0);
    if (!initStrip(&strip, pin, pixel_count, error)) return nullptr;
    return &strip;
  }

  if (static_cast<int>(g_strips.size()) >= kMaxStrips) {
    if (error) *error = "too_many_strips";
    return nullptr;
  }
  StripState strip;
  if (!initStrip(&strip, pin, pixel_count, error)) return nullptr;
  g_strips.push_back(std::move(strip));
  return &g_strips.back();
}

void applyColorToBuffer(std::vector<uint32_t>* buf, int pixel_count, const std::vector<uint16_t>& indexes, uint32_t color, bool* applied) {
  if (!buf || pixel_count < 1) return;
  for (size_t i = 0; i < indexes.size(); ++i) {
    const uint16_t idx = indexes[i];
    if (idx >= static_cast<uint16_t>(pixel_count)) continue;
    (*buf)[static_cast<size_t>(idx)] = color;
    if (applied) *applied = true;
  }
}

void composeStrip(StripState* strip) {
  if (!strip || !strip->strip || strip->pixel_count < 1) return;
  strip->frame = strip->base;
  for (size_t i = 0; i < g_effects.size(); ++i) {
    const BlinkEffect& fx = g_effects[i];
    if (fx.pin != strip->pin || !fx.is_on) continue;
    applyColorToBuffer(&strip->frame, strip->pixel_count, fx.indexes, fx.on_color, nullptr);
  }
  for (int i = 0; i < strip->pixel_count; ++i) {
    setPixelRaw(strip, i, strip->frame[static_cast<size_t>(i)]);
  }
}

bool composePin(int pin) {
  StripState* strip = findStrip(pin);
  if (!strip) return false;
  composeStrip(strip);
  return true;
}

void showPin(int pin) {
  StripState* strip = findStrip(pin);
  if (!strip || !strip->strip) return;
  strip->strip->show();
}

}  // namespace

bool RgbStripNeoPixel::writePixels(
    int pin,
    int pixel_count,
    const std::vector<uint16_t>& pixel_indexes,
    const String& mode,
    const String& color_hex,
    float brightness,
    uint16_t blink_count,
    uint32_t blink_interval_ms,
    String* error) {
  StripState* strip = ensureStrip(pin, pixel_count, error);
  if (strip == nullptr || !strip->strip) return false;

  std::vector<uint16_t> valid_indexes;
  valid_indexes.reserve(pixel_indexes.size());
  for (size_t i = 0; i < pixel_indexes.size(); ++i) {
    const uint16_t idx = pixel_indexes[i];
    if (idx >= static_cast<uint16_t>(strip->logical_pixel_count)) continue;
    valid_indexes.push_back(idx);
  }
  if (valid_indexes.empty()) {
    if (error) *error = "pixel_out_of_range";
    return false;
  }

  uint32_t color = 0;
  if (!parseHexColor(color_hex, &color)) {
    if (error) *error = "bad_color";
    return false;
  }
  if (brightness < 0.0f) brightness = 0.0f;
  if (brightness > 1.0f) brightness = 1.0f;
  color = scaleColor(brightness, color);

  String mode_norm = mode;
  mode_norm.trim();
  mode_norm.toLowerCase();
  if (mode_norm != "on" && mode_norm != "off" && mode_norm != "off_force" && mode_norm != "blink") mode_norm = "on";
  if (blink_count < 1) blink_count = 1;
  if (blink_count > 1000) blink_count = 1000;
  if (blink_interval_ms < 10) blink_interval_ms = 10;
  if (blink_interval_ms > 60000) blink_interval_ms = 60000;

  bool applied = false;
  if (mode_norm == "off" || mode_norm == "off_force") {
    if (mode_norm == "off_force") {
      removeEffectsForPinIndexes(pin, valid_indexes);
    }
    std::vector<uint16_t> safe_indexes;
    safe_indexes.reserve(valid_indexes.size());
    for (size_t i = 0; i < valid_indexes.size(); ++i) {
      const uint16_t idx = valid_indexes[i];
      if (mode_norm != "off_force" && hasActiveBlinkForPixel(pin, idx)) continue;
      safe_indexes.push_back(idx);
    }
    applyColorToBuffer(&strip->base, strip->pixel_count, safe_indexes, 0, &applied);
    if (!applied) applied = !valid_indexes.empty();
  } else if (mode_norm == "on") {
    std::vector<uint16_t> safe_indexes;
    safe_indexes.reserve(valid_indexes.size());
    for (size_t i = 0; i < valid_indexes.size(); ++i) {
      const uint16_t idx = valid_indexes[i];
      if (hasActiveBlinkForPixel(pin, idx)) continue;
      safe_indexes.push_back(idx);
    }
    applyColorToBuffer(&strip->base, strip->pixel_count, safe_indexes, color, &applied);
    if (!applied) applied = !valid_indexes.empty();
  } else {
    applied = !valid_indexes.empty();
  }
  if (!applied) {
    if (error) *error = "pixel_out_of_range";
    return false;
  }

  if (mode_norm == "blink") {
    BlinkEffect fx;
    fx.pin = pin;
    fx.indexes = valid_indexes;
    fx.on_color = color;
    fx.is_on = true;
    fx.interval_ms = blink_interval_ms;
    fx.next_toggle_ms = millis() + blink_interval_ms;
    fx.toggles_remaining = static_cast<uint32_t>(blink_count) * 2u - 1u;
    g_effects.push_back(fx);
  }

  if (g_batch_depth > 0) {
    markBatchDirtyPin(pin);
  } else {
    composeStrip(strip);
    strip->strip->show();
  }
  return true;
}

void RgbStripNeoPixel::service(unsigned long now_ms) {
  if (g_effects.empty()) return;
  std::vector<int> dirty_pins;
  for (size_t i = 0; i < g_effects.size();) {
    BlinkEffect& fx = g_effects[i];
    if (fx.toggles_remaining == 0) {
      appendUniquePin(&dirty_pins, fx.pin);
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    if (static_cast<long>(now_ms - fx.next_toggle_ms) < 0) {
      ++i;
      continue;
    }
    StripState* strip = findStrip(fx.pin);
    if (!strip || !strip->strip) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    fx.is_on = !fx.is_on;
    appendUniquePin(&dirty_pins, fx.pin);
    if (fx.toggles_remaining > 0) fx.toggles_remaining -= 1;
    fx.next_toggle_ms = now_ms + fx.interval_ms;
    if (fx.toggles_remaining == 0 && !fx.is_on) {
      appendUniquePin(&dirty_pins, fx.pin);
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    ++i;
  }
  if (dirty_pins.empty()) return;
  if (g_batch_depth > 0) {
    for (size_t i = 0; i < dirty_pins.size(); ++i) {
      markBatchDirtyPin(dirty_pins[i]);
    }
  } else {
    for (size_t i = 0; i < dirty_pins.size(); ++i) {
      composePin(dirty_pins[i]);
      showPin(dirty_pins[i]);
    }
  }
}

void RgbStripNeoPixel::beginBatch() {
  if (g_batch_depth < 0xFFFFu) g_batch_depth += 1;
}

void RgbStripNeoPixel::endBatch() {
  if (g_batch_depth == 0) return;
  g_batch_depth -= 1;
  if (g_batch_depth == 0 && g_batch_dirty) {
    for (size_t i = 0; i < g_batch_pins.size(); ++i) {
      composePin(g_batch_pins[i]);
      showPin(g_batch_pins[i]);
    }
    g_batch_dirty = false;
    g_batch_pins.clear();
  }
}

void RgbStripNeoPixel::clearAll() {
  g_effects.clear();
  if (g_batch_depth > 0) {
    for (size_t i = 0; i < g_strips.size(); ++i) {
      StripState& strip = g_strips[i];
      if (!strip.strip) continue;
      for (int j = 0; j < strip.pixel_count; ++j) {
        strip.base[static_cast<size_t>(j)] = 0;
        strip.frame[static_cast<size_t>(j)] = 0;
      }
      markBatchDirtyPin(strip.pin);
    }
    return;
  }

  for (size_t i = 0; i < g_strips.size(); ++i) {
    StripState& strip = g_strips[i];
    if (!strip.strip) continue;
    for (int j = 0; j < strip.pixel_count; ++j) {
      strip.base[static_cast<size_t>(j)] = 0;
      strip.frame[static_cast<size_t>(j)] = 0;
      setPixelRaw(&strip, j, 0);
    }
    strip.strip->show();
  }
}
