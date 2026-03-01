#include "drivers/RgbStrip/Default.h"

#include <FastLED.h>

namespace {

struct StripState {
  int pin = -1;
  int pixel_count = 0;
  CRGB* leds = nullptr;
};

struct BlinkEffect {
  int pin = -1;
  std::vector<uint16_t> indexes;
  CRGB on_color = CRGB::Black;
  bool is_on = true;
  uint32_t interval_ms = 150;
  uint32_t next_toggle_ms = 0;
  uint32_t toggles_remaining = 0;  // Number of ON/OFF edge toggles left.
};

std::vector<StripState> g_strips;
std::vector<BlinkEffect> g_effects;
constexpr int kMaxPixelsPerStrip = 2048;
constexpr int kMaxStrips = 16;

template <int Pin>
bool attachForPin(CRGB* leds, int pixel_count) {
  FastLED.addLeds<WS2812B, Pin, GRB>(leds, pixel_count);
  return true;
}

bool attachStripForPin(int pin, CRGB* leds, int pixel_count) {
  if (leds == nullptr || pixel_count < 1) return false;
  switch (pin) {
    case 0: return attachForPin<0>(leds, pixel_count);
    case 1: return attachForPin<1>(leds, pixel_count);
    case 2: return attachForPin<2>(leds, pixel_count);
    case 3: return attachForPin<3>(leds, pixel_count);
    case 4: return attachForPin<4>(leds, pixel_count);
    case 5: return attachForPin<5>(leds, pixel_count);
    case 6: return attachForPin<6>(leds, pixel_count);
    case 7: return attachForPin<7>(leds, pixel_count);
    case 8: return attachForPin<8>(leds, pixel_count);
    case 9: return attachForPin<9>(leds, pixel_count);
    case 10: return attachForPin<10>(leds, pixel_count);
    case 11: return attachForPin<11>(leds, pixel_count);
    case 12: return attachForPin<12>(leds, pixel_count);
    case 13: return attachForPin<13>(leds, pixel_count);
    case 14: return attachForPin<14>(leds, pixel_count);
    case 15: return attachForPin<15>(leds, pixel_count);
    case 16: return attachForPin<16>(leds, pixel_count);
    case 17: return attachForPin<17>(leds, pixel_count);
    case 18: return attachForPin<18>(leds, pixel_count);
    case 19: return attachForPin<19>(leds, pixel_count);
    case 20: return attachForPin<20>(leds, pixel_count);
    case 21: return attachForPin<21>(leds, pixel_count);
    case 26: return attachForPin<26>(leds, pixel_count);
    case 37: return attachForPin<37>(leds, pixel_count);
    case 38: return attachForPin<38>(leds, pixel_count);
    case 39: return attachForPin<39>(leds, pixel_count);
    case 40: return attachForPin<40>(leds, pixel_count);
    case 41: return attachForPin<41>(leds, pixel_count);
    case 42: return attachForPin<42>(leds, pixel_count);
    case 47: return attachForPin<47>(leds, pixel_count);
    case 48: return attachForPin<48>(leds, pixel_count);
    default: return false;
  }
}

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

bool parseHexColor(const String& color_hex, CRGB* out) {
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
  out->r = static_cast<uint8_t>((n0 << 4) | n1);
  out->g = static_cast<uint8_t>((n2 << 4) | n3);
  out->b = static_cast<uint8_t>((n4 << 4) | n5);
  return true;
}

uint8_t scale8(float brightness, uint8_t value) {
  if (brightness <= 0.0f) return 0;
  if (brightness >= 1.0f) return value;
  float scaled = static_cast<float>(value) * brightness;
  if (scaled <= 0.0f) return 0;
  if (scaled >= 255.0f) return 255;
  return static_cast<uint8_t>(scaled + 0.5f);
}

StripState* findStrip(int pin) {
  for (size_t i = 0; i < g_strips.size(); ++i) {
    if (g_strips[i].pin == pin) return &g_strips[i];
  }
  return nullptr;
}

StripState* ensureStrip(int pin, int pixel_count, String* error) {
  if (pin < 0) {
    if (error) *error = "bad_pin";
    return nullptr;
  }
  if (pixel_count < 1 || pixel_count > kMaxPixelsPerStrip) {
    if (error) *error = "bad_pixel_count";
    return nullptr;
  }
  for (size_t i = 0; i < g_strips.size(); ++i) {
    if (g_strips[i].pin != pin) continue;
    StripState& strip = g_strips[i];
    if (strip.pixel_count == pixel_count && strip.leds != nullptr) {
      return &strip;
    }
    if (error) *error = "count_change_requires_reboot";
    return nullptr;
  }
  if (static_cast<int>(g_strips.size()) >= kMaxStrips) {
    if (error) *error = "too_many_strips";
    return nullptr;
  }
  StripState strip;
  strip.pin = pin;
  strip.pixel_count = pixel_count;
  strip.leds = new CRGB[pixel_count];
  if (strip.leds == nullptr) {
    if (error) *error = "alloc_failed";
    return nullptr;
  }
  for (int j = 0; j < pixel_count; ++j) strip.leds[j] = CRGB::Black;
  if (!attachStripForPin(pin, strip.leds, pixel_count)) {
    delete[] strip.leds;
    strip.leds = nullptr;
    if (error) *error = "pin_not_supported";
    return nullptr;
  }
  g_strips.push_back(strip);
  return &g_strips.back();
}

bool hasIndexOverlap(const std::vector<uint16_t>& a, const std::vector<uint16_t>& b) {
  for (size_t i = 0; i < a.size(); ++i) {
    for (size_t j = 0; j < b.size(); ++j) {
      if (a[i] == b[j]) return true;
    }
  }
  return false;
}

void applyColor(StripState* strip, const std::vector<uint16_t>& indexes, const CRGB& color, bool* applied) {
  if (!strip || !strip->leds) return;
  for (size_t i = 0; i < indexes.size(); ++i) {
    uint16_t idx = indexes[i];
    if (idx >= static_cast<uint16_t>(strip->pixel_count)) continue;
    strip->leds[idx] = color;
    if (applied) *applied = true;
  }
}

void removeEffectsForIndexes(int pin, const std::vector<uint16_t>& indexes) {
  for (size_t i = 0; i < g_effects.size();) {
    const BlinkEffect& fx = g_effects[i];
    if (fx.pin != pin || !hasIndexOverlap(fx.indexes, indexes)) {
      ++i;
      continue;
    }
    g_effects.erase(g_effects.begin() + i);
  }
}

}  // namespace

bool RgbStripDefault::writePixels(
    int pin,
    int pixel_count,
    const std::vector<uint16_t>& pixel_indexes,
    const String& mode,
    const String& color_hex,
    float brightness,
    uint16_t blink_count,
    uint32_t blink_interval_ms,
    String* error) {
  if (pixel_indexes.empty()) {
    if (error) *error = "no_pixels";
    return false;
  }
  StripState* strip = ensureStrip(pin, pixel_count, error);
  if (strip == nullptr || strip->leds == nullptr) return false;

  CRGB color;
  if (!parseHexColor(color_hex, &color)) {
    if (error) *error = "bad_color";
    return false;
  }
  if (brightness < 0.0f) brightness = 0.0f;
  if (brightness > 1.0f) brightness = 1.0f;
  color.r = scale8(brightness, color.r);
  color.g = scale8(brightness, color.g);
  color.b = scale8(brightness, color.b);

  String mode_norm = mode;
  mode_norm.trim();
  mode_norm.toLowerCase();
  if (mode_norm != "on" && mode_norm != "off" && mode_norm != "blink") mode_norm = "on";
  if (blink_count < 1) blink_count = 1;
  if (blink_count > 1000) blink_count = 1000;
  if (blink_interval_ms < 10) blink_interval_ms = 10;
  if (blink_interval_ms > 60000) blink_interval_ms = 60000;

  removeEffectsForIndexes(pin, pixel_indexes);

  bool applied = false;
  if (mode_norm == "off") {
    applyColor(strip, pixel_indexes, CRGB::Black, &applied);
  } else {
    applyColor(strip, pixel_indexes, color, &applied);
  }
  if (!applied) {
    if (error) *error = "pixel_out_of_range";
    return false;
  }

  if (mode_norm == "blink") {
    BlinkEffect fx;
    fx.pin = pin;
    fx.indexes = pixel_indexes;
    fx.on_color = color;
    fx.is_on = true;
    fx.interval_ms = blink_interval_ms;
    fx.next_toggle_ms = millis() + blink_interval_ms;
    fx.toggles_remaining = static_cast<uint32_t>(blink_count) * 2u - 1u;
    g_effects.push_back(fx);
  }

  FastLED.show();
  return true;
}

void RgbStripDefault::service(unsigned long now_ms) {
  if (g_effects.empty()) return;
  bool changed = false;
  for (size_t i = 0; i < g_effects.size();) {
    BlinkEffect& fx = g_effects[i];
    if (fx.toggles_remaining == 0) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    if (static_cast<long>(now_ms - fx.next_toggle_ms) < 0) {
      ++i;
      continue;
    }
    StripState* strip = findStrip(fx.pin);
    if (!strip || !strip->leds) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    fx.is_on = !fx.is_on;
    CRGB next = fx.is_on ? fx.on_color : CRGB::Black;
    bool applied = false;
    applyColor(strip, fx.indexes, next, &applied);
    if (applied) changed = true;
    if (fx.toggles_remaining > 0) fx.toggles_remaining -= 1;
    fx.next_toggle_ms = now_ms + fx.interval_ms;
    if (fx.toggles_remaining == 0 && !fx.is_on) {
      g_effects.erase(g_effects.begin() + i);
      continue;
    }
    ++i;
  }
  if (changed) FastLED.show();
}
