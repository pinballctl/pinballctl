#include "protocol/ProtocolHandler.h"

#include <ArduinoJson.h>
#include <Arduino.h>

#include "drivers/DriverRegistry.h"
#include "hardware/MappingBlob.h"
#include "protocol/core/ProtocolSupport.h"

namespace {
constexpr const char* kDisplayMappingBlobPath = "/cfg/mapping.pb";
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
  uint16_t lcd_auto_off_sec = 60;

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

  MappingDriverBindingEntry binding;
  String binding_err;
  const bool has_binding =
      loadMappingDriverBindingForTarget(kDisplayMappingBlobPath, target, &binding, &binding_err);
  if (has_binding) {
    if (!driver.length() && binding.driver.length()) driver = binding.driver;
    if (sda_pin < 0 && binding.lcd_sda_pin != 0xFFFF) sda_pin = static_cast<int>(binding.lcd_sda_pin);
    if (scl_pin < 0 && binding.lcd_scl_pin != 0xFFFF) scl_pin = static_cast<int>(binding.lcd_scl_pin);
    if (!addr_var.is<int>() && !addr_var.is<const char*>()) addr = static_cast<int>(binding.lcd_i2c_addr);
    if (!cols_var.is<int>()) cols = static_cast<int>(binding.lcd_cols);
    if (!rows_var.is<int>()) rows = static_cast<int>(binding.lcd_rows);
  }

  if (sda_pin < 0 || scl_pin < 0 || sda_pin == scl_pin) {
    String payload = "{\"t\":\"LCD_STATUS\",\"ok\":false,\"error\":\"bad_pins\"";
    if (target.length()) {
      payload += ",\"target\":\"";
      payload += target;
      payload += "\"";
    }
    if (binding_err.length()) {
      payload += ",\"reason\":\"";
      payload += binding_err;
      payload += "\"";
    } else if (has_binding) {
      payload += ",\"reason\":\"mapping_missing_lcd_pins\"";
    } else {
      payload += ",\"reason\":\"binding_not_found\"";
    }
    payload += "}";
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (addr < 0x03 || addr > 0x77) addr = 0x27;
  if (cols < 8) cols = 8;
  if (cols > 40) cols = 40;
  if (rows < 1) rows = 1;
  if (rows > 4) rows = 4;
  if (line1.length() > static_cast<unsigned int>(cols)) line1 = line1.substring(0, cols);
  if (line2.length() > static_cast<unsigned int>(cols)) line2 = line2.substring(0, cols);
  String resolved_fn = "LCD Display";
  String impl_name;
  driver_registry::resolveDriverForTarget(
      kDisplayMappingBlobPath,
      target,
      driver,
      "LCD Display",
      &resolved_fn,
      &driver,
      &impl_name,
      &lcd_auto_off_sec);

  const bool ok = driver_registry::writeDisplayTextByDriver(
      driver,
      sda_pin,
      scl_pin,
      static_cast<uint8_t>(addr),
      line1,
      line2,
      static_cast<uint8_t>(cols),
      static_cast<uint8_t>(rows),
      clear_first,
      lcd_auto_off_sec);

  String payload = "{\"t\":\"LCD_STATUS\",\"ok\":";
  payload += (ok ? "true" : "false");
  payload += ",\"sdaPin\":";
  payload += sda_pin;
  payload += ",\"sclPin\":";
  payload += scl_pin;
  payload += ",\"address\":";
  payload += addr;
  if (!ok) {
    payload += ",\"error\":\"i2c_nack\"";
  }
  payload += ",\"driver\":\"";
  payload += driver;
  payload += "\"";
  payload += ",\"function\":\"";
  payload += resolved_fn;
  payload += "\"";
  payload += ",\"impl\":\"";
  payload += impl_name;
  payload += "\"";
  payload += "}";
  protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
  return true;
}
