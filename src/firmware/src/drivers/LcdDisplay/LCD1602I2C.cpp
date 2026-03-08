#include "drivers/LcdDisplay/LCD1602I2C.h"

#include <Wire.h>

namespace {
constexpr uint8_t kRs = 0x01;
constexpr uint8_t kEn = 0x04;
constexpr uint8_t kBacklight = 0x08;

bool g_cfg_valid = false;
int g_cfg_sda = -1;
int g_cfg_scl = -1;
uint8_t g_cfg_addr = 0x27;
uint8_t g_cfg_cols = 16;
uint8_t g_cfg_rows = 2;

int g_lcd_wire_sda = -1;
int g_lcd_wire_scl = -1;
bool g_init_needed = false;
bool g_inited = false;
bool g_has_display = false;
bool g_backlight_on = true;
bool g_backlight_sync_needed = false;
unsigned long g_next_init_attempt_ms = 0;

unsigned long g_last_activity_ms = 0;
unsigned long g_auto_backlight_off_ms = LcdDisplayLCD1602I2C::kAutoBacklightOffMs;

String g_desired_line1;
String g_desired_line2;
String g_rendered_line1;
String g_rendered_line2;
bool g_pending_render = false;

String normalizeLine(const String& text, uint8_t cols) {
  String out = text;
  if (out.length() > cols) out = out.substring(0, cols);
  while (out.length() < cols) out += ' ';
  return out;
}

bool expanderWrite(uint8_t addr, uint8_t data) {
  Wire.beginTransmission(addr);
  const uint8_t backlight_bit = g_backlight_on ? kBacklight : 0;
  Wire.write(static_cast<uint8_t>(data | backlight_bit));
  return Wire.endTransmission() == 0;
}

bool pulseEnable(uint8_t addr, uint8_t data) {
  if (!expanderWrite(addr, static_cast<uint8_t>(data | kEn))) return false;
  delayMicroseconds(1);
  if (!expanderWrite(addr, static_cast<uint8_t>(data & static_cast<uint8_t>(~kEn)))) return false;
  delayMicroseconds(50);
  return true;
}

bool write4Bits(uint8_t addr, uint8_t nibble, uint8_t mode) {
  uint8_t data = static_cast<uint8_t>((nibble & 0xF0) | mode);
  if (!expanderWrite(addr, data)) return false;
  return pulseEnable(addr, data);
}

bool sendByte(uint8_t addr, uint8_t value, uint8_t mode) {
  if (!write4Bits(addr, static_cast<uint8_t>(value & 0xF0), mode)) return false;
  return write4Bits(addr, static_cast<uint8_t>((value << 4) & 0xF0), mode);
}

bool command(uint8_t addr, uint8_t value) {
  return sendByte(addr, value, 0);
}

bool writeChar(uint8_t addr, char c) {
  return sendByte(addr, static_cast<uint8_t>(c), kRs);
}

bool setCursor(uint8_t addr, uint8_t col, uint8_t row) {
  static const uint8_t row_offsets[] = {0x00, 0x40, 0x14, 0x54};
  const uint8_t row_idx = row > 3 ? 3 : row;
  return command(addr, static_cast<uint8_t>(0x80 | (col + row_offsets[row_idx])));
}

bool initDisplay(uint8_t addr, uint8_t cols, uint8_t rows) {
  g_backlight_on = true;
  // Avoid large blocking delays in the main loop; the display is already powered.
  delayMicroseconds(2000);
  if (!write4Bits(addr, 0x30, 0)) return false;
  delayMicroseconds(4500);
  if (!write4Bits(addr, 0x30, 0)) return false;
  delayMicroseconds(4500);
  if (!write4Bits(addr, 0x30, 0)) return false;
  delayMicroseconds(150);
  if (!write4Bits(addr, 0x20, 0)) return false;

  uint8_t function = 0x20;
  if (rows > 1) function |= 0x08;
  if (!command(addr, static_cast<uint8_t>(function | 0x00))) return false;
  if (!command(addr, 0x06)) return false;  // entry mode set
  if (!command(addr, 0x0C)) return false;  // display on, cursor off
  return true;
}

bool writePaddedLine(uint8_t addr, uint8_t row, const String& text, uint8_t cols) {
  if (!setCursor(addr, 0, row)) return false;
  for (uint8_t i = 0; i < cols; ++i) {
    char ch = ' ';
    if (i < text.length()) ch = text[i];
    if (!writeChar(addr, ch)) return false;
  }
  return true;
}

bool writeDiffLine(uint8_t addr, uint8_t row, const String& previous, const String& next, uint8_t cols) {
  if (previous.length() != cols || next.length() != cols) return writePaddedLine(addr, row, next, cols);
  uint8_t col = 0;
  while (col < cols) {
    if (previous[col] == next[col]) {
      ++col;
      continue;
    }
    if (!setCursor(addr, col, row)) return false;
    while (col < cols && previous[col] != next[col]) {
      if (!writeChar(addr, next[col])) return false;
      ++col;
    }
  }
  return true;
}

void markNeedsInit() {
  g_init_needed = true;
  g_inited = false;
  g_has_display = false;
}
}  // namespace

bool LcdDisplayLCD1602I2C::writeText(
    int sda_pin,
    int scl_pin,
    uint8_t i2c_addr,
    const String& line1,
    const String& line2,
    uint8_t cols,
    uint8_t rows,
    bool clear_first,
    uint16_t auto_off_seconds) {
  (void)clear_first;  // Runtime uses in-place updates only to avoid flicker.

  if (sda_pin < 0 || scl_pin < 0 || sda_pin == scl_pin) return false;
  if (i2c_addr < 0x03 || i2c_addr > 0x77) return false;
  if (cols < 8) cols = 8;
  if (cols > 40) cols = 40;
  if (rows < 1) rows = 1;
  if (rows > 4) rows = 4;

  if (!g_cfg_valid ||
      g_cfg_sda != sda_pin ||
      g_cfg_scl != scl_pin ||
      g_cfg_addr != i2c_addr ||
      g_cfg_cols != cols ||
      g_cfg_rows != rows) {
    g_cfg_valid = true;
    g_cfg_sda = sda_pin;
    g_cfg_scl = scl_pin;
    g_cfg_addr = i2c_addr;
    g_cfg_cols = cols;
    g_cfg_rows = rows;
    markNeedsInit();
  }

  if (auto_off_seconds == 0) {
    g_auto_backlight_off_ms = 0;
  } else {
    const unsigned long max_secs = 0xFFFFFFFFUL / 1000UL;
    const unsigned long secs = auto_off_seconds > max_secs ? max_secs : auto_off_seconds;
    g_auto_backlight_off_ms = secs * 1000UL;
  }

  const String next1 = normalizeLine(line1, cols);
  const String next2 = normalizeLine(line2, cols);
  const bool changed = (next1 != g_desired_line1) || (next2 != g_desired_line2);

  // Strict duplicate fast-path: same text means no LCD/backlight write activity.
  // Only refresh the inactivity timer for auto-off bookkeeping.
  // If backlight is currently off, wake it without scheduling text writes.
  if (!changed) {
    if (!g_backlight_on) {
      g_backlight_on = true;
      g_backlight_sync_needed = true;
    }
    g_last_activity_ms = millis();
    return true;
  }

  g_desired_line1 = next1;
  g_desired_line2 = next2;
  g_pending_render = true;

  if (!g_backlight_on) {
    g_backlight_on = true;
    g_backlight_sync_needed = true;
  }
  g_last_activity_ms = millis();
  return true;
}

void LcdDisplayLCD1602I2C::service(unsigned long now_ms) {
  if (!g_cfg_valid) return;

  if (g_lcd_wire_sda != g_cfg_sda || g_lcd_wire_scl != g_cfg_scl) {
    Wire.begin(g_cfg_sda, g_cfg_scl);
    g_lcd_wire_sda = g_cfg_sda;
    g_lcd_wire_scl = g_cfg_scl;
    markNeedsInit();
  }

  if (g_init_needed) {
    if (now_ms < g_next_init_attempt_ms) return;
    if (!initDisplay(g_cfg_addr, g_cfg_cols, g_cfg_rows)) {
      // Back off and retry init later, but do not busy-loop.
      g_next_init_attempt_ms = now_ms + 250;
      return;
    }
    g_init_needed = false;
    g_next_init_attempt_ms = 0;
    g_inited = true;
    g_has_display = true;
    g_rendered_line1 = "";
    g_rendered_line2 = "";
    g_pending_render = true;
    g_backlight_sync_needed = true;
  }

  if (!g_inited || !g_has_display) return;

  if (g_backlight_sync_needed) {
    if (!expanderWrite(g_cfg_addr, 0x00)) {
      // Keep requested state and try again on next service pass.
      return;
    }
    g_backlight_sync_needed = false;
  }

  if (g_pending_render) {
    if (g_rendered_line1 != g_desired_line1) {
      if (!writeDiffLine(g_cfg_addr, 0, g_rendered_line1, g_desired_line1, g_cfg_cols)) {
        // Preserve pending render; retry later without forcing re-init.
        return;
      }
      g_rendered_line1 = g_desired_line1;
      return;
    }
    if (g_cfg_rows > 1 && g_rendered_line2 != g_desired_line2) {
      if (!writeDiffLine(g_cfg_addr, 1, g_rendered_line2, g_desired_line2, g_cfg_cols)) {
        // Preserve pending render; retry later without forcing re-init.
        return;
      }
      g_rendered_line2 = g_desired_line2;
      return;
    }
    g_pending_render = false;
  }

  if (g_auto_backlight_off_ms == 0 || !g_backlight_on) return;
  const unsigned long elapsed = now_ms - g_last_activity_ms;
  if (elapsed < g_auto_backlight_off_ms) return;

  g_backlight_on = false;
  if (!expanderWrite(g_cfg_addr, 0x00)) {
    // Keep trying to switch backlight off on later service passes.
    return;
  }
  g_backlight_sync_needed = false;
}
