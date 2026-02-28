#include "protocol/ProtocolHandler.h"

#include <ArduinoJson.h>
#include <Arduino.h>

#include "components/Lcd1602I2C.h"
#include "hw/MappingBlob.h"
#include "protocol/core/ProtocolSupport.h"

namespace {
constexpr const char* kDisplayMappingBlobPath = "/cfg/mapping.pb";

String normalizeDriverName(const String& raw) {
  String d = raw;
  d.trim();
  if (!d.length()) return String("LCD1602I2C");
  if (d.equalsIgnoreCase("Default")) return String("LCD1602I2C");
  return d;
}

bool writeLcdByDriver(
    const String& driver,
    int sda_pin,
    int scl_pin,
    int addr,
    const String& line1,
    const String& line2,
    int cols,
    int rows,
    bool clear_first) {
  String d = normalizeDriverName(driver);
  if (d.equalsIgnoreCase("Default") || d.equalsIgnoreCase("LCD1602I2C") || d.equalsIgnoreCase("LEDDisplay1602")) {
    return Lcd1602I2C::writeText(
        sda_pin,
        scl_pin,
        static_cast<uint8_t>(addr),
        line1,
        line2,
        static_cast<uint8_t>(cols),
        static_cast<uint8_t>(rows),
        clear_first);
  }
  return false;
}
}  // namespace

bool ProtocolHandler::handleDisplayCommands(const String& line, const String& req_id, const String& cmd) {
  if (!protocol_support::isCmd(line, cmd, "LCD_SET")) return false;

  DynamicJsonDocument doc(2048);
  auto err = deserializeJson(doc, line);
  if (err || !doc.is<JsonObject>()) {
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"LCD_STATUS\",\"ok\":false,\"error\":\"bad_json\"}", req_id));
    return true;
  }

  JsonObject obj = doc.as<JsonObject>();
  JsonVariant sda_var = obj["sdaPin"];
  JsonVariant scl_var = obj["sclPin"];
  JsonVariant addr_var = obj["address"];
  JsonVariant cols_var = obj["cols"];
  JsonVariant rows_var = obj["rows"];
  String target = obj["target"].is<const char*>() ? String(obj["target"].as<const char*>()) : String("");
  String driver = obj["driver"].is<const char*>() ? String(obj["driver"].as<const char*>()) : String("");
  String line1 = obj["line1"].is<const char*>() ? String(obj["line1"].as<const char*>()) : String("");
  String line2 = obj["line2"].is<const char*>() ? String(obj["line2"].as<const char*>()) : String("");
  bool clear_first = obj["clearFirst"].is<bool>() ? obj["clearFirst"].as<bool>() : false;

  int sda_pin = -1;
  int scl_pin = -1;
  int addr = 0x27;
  int cols = 16;
  int rows = 2;

  if (sda_var.is<int>()) sda_pin = sda_var.as<int>();
  if (scl_var.is<int>()) scl_pin = scl_var.as<int>();
  if (addr_var.is<int>()) addr = addr_var.as<int>();
  if (addr_var.is<const char*>()) {
    String s = String(addr_var.as<const char*>());
    s.trim();
    addr = strtol(s.c_str(), nullptr, 0);
  }
  if (cols_var.is<int>()) cols = cols_var.as<int>();
  if (rows_var.is<int>()) rows = rows_var.as<int>();

  if (sda_pin < 0 || scl_pin < 0 || sda_pin == scl_pin) {
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"LCD_STATUS\",\"ok\":false,\"error\":\"bad_pins\"}", req_id));
    return true;
  }
  if (addr < 0x03 || addr > 0x77) addr = 0x27;
  if (cols < 8) cols = 8;
  if (cols > 40) cols = 40;
  if (rows < 1) rows = 1;
  if (rows > 4) rows = 4;
  if (line1.length() > static_cast<unsigned int>(cols)) line1 = line1.substring(0, cols);
  if (line2.length() > static_cast<unsigned int>(cols)) line2 = line2.substring(0, cols);
  driver = normalizeDriverName(driver);
  if (!target.isEmpty() && (driver.equalsIgnoreCase("Default") || !driver.length())) {
    String mapped_driver;
    String map_error;
    if (loadMappingLcdDriverForTarget(kDisplayMappingBlobPath, target, &mapped_driver, &map_error) && mapped_driver.length()) {
      driver = mapped_driver;
    }
  }

  auto tryWrite = [&](int sda, int scl, int attempts) -> bool {
    if (attempts < 1) attempts = 1;
    for (int i = 0; i < attempts; ++i) {
      if (writeLcdByDriver(
              driver,
              sda,
              scl,
              addr,
              line1,
              line2,
              cols,
              rows,
              clear_first)) {
        return true;
      }
      delay(8);
    }
    return false;
  };

  // Retry on the declared pin order first; boot-time I2C can be transient.
  bool ok = tryWrite(sda_pin, scl_pin, 2);
  bool used_swapped_pins = false;
  if (!ok) {
    ok = tryWrite(scl_pin, sda_pin, 2);
    used_swapped_pins = ok;
  }

  String payload = "{\"t\":\"LCD_STATUS\",\"ok\":";
  payload += (ok ? "true" : "false");
  payload += ",\"sdaPin\":";
  payload += (used_swapped_pins ? scl_pin : sda_pin);
  payload += ",\"sclPin\":";
  payload += (used_swapped_pins ? sda_pin : scl_pin);
  payload += ",\"address\":";
  payload += addr;
  if (!ok) {
    payload += ",\"error\":\"i2c_nack\"";
  }
  payload += ",\"driver\":\"";
  payload += driver;
  payload += "\"";
  if (used_swapped_pins) {
    payload += ",\"swappedPins\":true";
  }
  payload += "}";
  protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
  return true;
}
