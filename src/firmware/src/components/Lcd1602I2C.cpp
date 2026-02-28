#include "components/Lcd1602I2C.h"

#include <Wire.h>

namespace {
constexpr uint8_t kRs = 0x01;
constexpr uint8_t kRw = 0x02;
constexpr uint8_t kEn = 0x04;
constexpr uint8_t kBacklight = 0x08;

int g_last_sda = -1;
int g_last_scl = -1;
uint8_t g_last_addr = 0;
bool g_inited = false;
bool g_has_display = false;
uint8_t g_last_cols = 16;
uint8_t g_last_rows = 2;

void expanderWrite(uint8_t addr, uint8_t data) {
  Wire.beginTransmission(addr);
  Wire.write(static_cast<uint8_t>(data | kBacklight));
  Wire.endTransmission();
}

void pulseEnable(uint8_t addr, uint8_t data) {
  expanderWrite(addr, static_cast<uint8_t>(data | kEn));
  delayMicroseconds(1);
  expanderWrite(addr, static_cast<uint8_t>(data & static_cast<uint8_t>(~kEn)));
  delayMicroseconds(50);
}

void write4Bits(uint8_t addr, uint8_t nibble, uint8_t mode) {
  uint8_t data = static_cast<uint8_t>((nibble & 0xF0) | mode);
  expanderWrite(addr, data);
  pulseEnable(addr, data);
}

void sendByte(uint8_t addr, uint8_t value, uint8_t mode) {
  write4Bits(addr, static_cast<uint8_t>(value & 0xF0), mode);
  write4Bits(addr, static_cast<uint8_t>((value << 4) & 0xF0), mode);
}

void command(uint8_t addr, uint8_t value) {
  sendByte(addr, value, 0);
}

void writeChar(uint8_t addr, char c) {
  sendByte(addr, static_cast<uint8_t>(c), kRs);
}

void setCursor(uint8_t addr, uint8_t col, uint8_t row) {
  static const uint8_t row_offsets[] = {0x00, 0x40, 0x14, 0x54};
  const uint8_t row_idx = row > 3 ? 3 : row;
  command(addr, static_cast<uint8_t>(0x80 | (col + row_offsets[row_idx])));
}

void clear(uint8_t addr) {
  command(addr, 0x01);
  delayMicroseconds(2000);
}

void initDisplay(uint8_t addr, uint8_t cols, uint8_t rows) {
  delayMicroseconds(50000);
  write4Bits(addr, 0x30, 0);
  delayMicroseconds(4500);
  write4Bits(addr, 0x30, 0);
  delayMicroseconds(4500);
  write4Bits(addr, 0x30, 0);
  delayMicroseconds(150);
  write4Bits(addr, 0x20, 0);

  uint8_t function = 0x20;  // 4-bit
  if (rows > 1) function |= 0x08;  // 2-line
  command(addr, static_cast<uint8_t>(function | 0x00));  // 5x8 font
  command(addr, 0x08);  // display off
  clear(addr);
  command(addr, 0x06);  // entry mode set
  command(addr, 0x0C);  // display on, cursor off
  g_last_cols = cols;
  g_last_rows = rows;
}

void writePaddedLine(uint8_t addr, uint8_t row, const String& text, uint8_t cols) {
  setCursor(addr, 0, row);
  for (uint8_t i = 0; i < cols; ++i) {
    char ch = ' ';
    if (i < text.length()) ch = text[i];
    writeChar(addr, ch);
  }
}
}  // namespace

bool Lcd1602I2C::writeText(
    int sda_pin,
    int scl_pin,
    uint8_t i2c_addr,
    const String& line1,
    const String& line2,
    uint8_t cols,
    uint8_t rows,
    bool clear_first) {
  if (sda_pin < 0 || scl_pin < 0 || sda_pin == scl_pin) return false;
  if (i2c_addr < 0x03 || i2c_addr > 0x77) return false;
  if (cols < 8) cols = 8;
  if (cols > 40) cols = 40;
  if (rows < 1) rows = 1;
  if (rows > 4) rows = 4;

  if (sda_pin != g_last_sda || scl_pin != g_last_scl || !g_has_display) {
    Wire.begin(sda_pin, scl_pin);
    g_last_sda = sda_pin;
    g_last_scl = scl_pin;
    g_inited = false;
  }
  if (!g_inited || i2c_addr != g_last_addr || cols != g_last_cols || rows != g_last_rows) {
    initDisplay(i2c_addr, cols, rows);
    g_inited = true;
    g_last_addr = i2c_addr;
    g_has_display = true;
  }
  if (clear_first) clear(i2c_addr);

  String l1 = line1;
  String l2 = line2;
  if (l1.length() > cols) l1 = l1.substring(0, cols);
  if (l2.length() > cols) l2 = l2.substring(0, cols);

  writePaddedLine(i2c_addr, 0, l1, cols);
  if (rows > 1) {
    writePaddedLine(i2c_addr, 1, l2, cols);
  }
  return true;
}
