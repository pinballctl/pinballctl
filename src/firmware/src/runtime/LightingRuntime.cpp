#include "runtime/LightingRuntime.h"

#include <LittleFS.h>
#include <cstdio>

#include "drivers/DriverRegistry.h"

namespace lighting_runtime_internal {
constexpr size_t kBlobHeaderSize = 44;
constexpr const char* kPayloadMagic = "LPD2";
constexpr const char* kMappingBlobPath = "/cfg/mapping.pb";
constexpr uint16_t kWildcardFixture = 0xFFFFu;
constexpr uint32_t kYieldInterval = 8;
constexpr uint16_t kMaxStringLen = 512;
constexpr uint16_t kMaxFixtureCount = 4096;
constexpr uint16_t kMaxSceneCount = 1024;
constexpr uint32_t kMaxFrameCount = 500000;
constexpr uint16_t kMaxChangeCount = 20000;

inline void maybeYield(uint32_t counter);

uint16_t readU16Le(const uint8_t* buf) {
  return static_cast<uint16_t>(buf[0]) | (static_cast<uint16_t>(buf[1]) << 8);
}

int16_t readI16Le(const uint8_t* buf) {
  return static_cast<int16_t>(readU16Le(buf));
}

uint32_t readU32Le(const uint8_t* buf) {
  return static_cast<uint32_t>(buf[0]) |
         (static_cast<uint32_t>(buf[1]) << 8) |
         (static_cast<uint32_t>(buf[2]) << 16) |
         (static_cast<uint32_t>(buf[3]) << 24);
}

float clamp01(float v) {
  if (v < 0.0f) return 0.0f;
  if (v > 1.0f) return 1.0f;
  return v;
}

bool parseTargetGpio(const String& target, int* pin_out) {
  if (!pin_out) return false;
  int idx = target.lastIndexOf("__GPIO__");
  if (idx < 0) return false;
  String tail = target.substring(idx + 8);
  tail.trim();
  if (!tail.length()) return false;
  for (size_t i = 0; i < tail.length(); ++i) {
    char c = tail[i];
    if (c < '0' || c > '9') return false;
  }
  int pin = tail.toInt();
  if (pin < 0) return false;
  *pin_out = pin;
  return true;
}

bool readExact(fs::File& file, uint8_t* out, size_t len) {
  if (!out || len == 0) return true;
  size_t got = 0;
  while (got < len) {
    maybeYield(static_cast<uint32_t>(got + 1));
    int n = file.read(out + got, len - got);
    if (n <= 0) return false;
    got += static_cast<size_t>(n);
  }
  return true;
}

String colorHexFromRgb(uint8_t r, uint8_t g, uint8_t b) {
  char buf[8];
  std::snprintf(buf, sizeof(buf), "#%02x%02x%02x", r, g, b);
  return String(buf);
}

inline void maybeYield(uint32_t counter) {
  if ((counter % kYieldInterval) == 0) {
    yield();
  }
}
}  // namespace lighting_runtime_internal

bool LightingRuntime::readBlobHeader(const char* path, uint16_t* version_out, uint32_t* payload_len, String* error) {
  if (!path || !path[0]) {
    if (error) *error = "bad_path";
    return false;
  }
  fs::File file = LittleFS.open(path, "r");
  if (!file) {
    if (error) *error = "open_failed";
    return false;
  }
  const size_t size = file.size();
  if (size < lighting_runtime_internal::kBlobHeaderSize) {
    if (error) *error = "bad_size";
    return false;
  }
  uint8_t header[lighting_runtime_internal::kBlobHeaderSize];
  if (!lighting_runtime_internal::readExact(file, header, sizeof(header))) {
    if (error) *error = "read_failed";
    return false;
  }
  if (memcmp(header, "PLT1", 4) != 0) {
    if (error) *error = "bad_magic";
    return false;
  }
  const uint16_t version = lighting_runtime_internal::readU16Le(header + 4);
  const uint16_t flags = lighting_runtime_internal::readU16Le(header + 6);
  const uint32_t payload = lighting_runtime_internal::readU32Le(header + 8);
  if (version != 2 && version != 3 && version != 4) {
    if (error) *error = "bad_version";
    return false;
  }
  if ((flags & 0x1u) != 0u) {
    if (error) *error = "compressed_not_supported";
    return false;
  }
  if (size != lighting_runtime_internal::kBlobHeaderSize + payload) {
    if (error) *error = "size_mismatch";
    return false;
  }
  if (version_out) *version_out = version;
  if (payload_len) *payload_len = payload;
  return true;
}

bool LightingRuntime::readString(fs::File& file, String* out, String* error) {
  if (!out) return false;
  uint8_t len_buf[2];
  if (!lighting_runtime_internal::readExact(file, len_buf, sizeof(len_buf))) {
    if (error) *error = "read_failed";
    return false;
  }
  const uint16_t len = lighting_runtime_internal::readU16Le(len_buf);
  if (len == 0) {
    *out = "";
    return true;
  }
  if (len > lighting_runtime_internal::kMaxStringLen) {
    if (error) *error = "string_too_long";
    return false;
  }
  std::vector<uint8_t> bytes;
  bytes.resize(len);
  if (!lighting_runtime_internal::readExact(file, bytes.data(), len)) {
    if (error) *error = "read_failed";
    return false;
  }
  out->reserve(len);
  *out = "";
  for (size_t i = 0; i < bytes.size(); ++i) *out += static_cast<char>(bytes[i]);
  return true;
}

bool LightingRuntime::loadFromLightingBlob(const char* path, String* error) {
  clear();

  uint16_t blob_version = 0;
  uint32_t payload_len = 0;
  if (!readBlobHeader(path, &blob_version, &payload_len, error)) return false;

  fs::File file = LittleFS.open(path, "r");
  if (!file) {
    if (error) *error = "open_failed";
    return false;
  }
  file.seek(lighting_runtime_internal::kBlobHeaderSize, SeekSet);

  uint8_t magic[4];
  if (!lighting_runtime_internal::readExact(file, magic, sizeof(magic))) {
    if (error) *error = "read_failed";
    return false;
  }
  if (memcmp(magic, lighting_runtime_internal::kPayloadMagic, 4) != 0) {
    if (error) *error = "bad_payload_magic";
    return false;
  }

  uint8_t u16_buf[2];
  uint8_t u32_buf[4];

  if (!lighting_runtime_internal::readExact(file, u16_buf, sizeof(u16_buf))) {
    if (error) *error = "read_failed";
    return false;
  }
  const uint16_t fixture_count = lighting_runtime_internal::readU16Le(u16_buf);
  if (fixture_count > lighting_runtime_internal::kMaxFixtureCount) {
    if (error) *error = "fixture_count_too_large";
    return false;
  }

  fixtures_.clear();
  fixtures_.reserve(fixture_count);
  for (uint16_t i = 0; i < fixture_count; ++i) {
    lighting_runtime_internal::maybeYield(static_cast<uint32_t>(i + 1));
    Fixture fx;
    if (!readString(file, &fx.id, error)) return false;
    if (!lighting_runtime_internal::readExact(file, u16_buf, sizeof(u16_buf))) {
      if (error) *error = "read_failed";
      return false;
    }
    fx.pixel_count = static_cast<int>(lighting_runtime_internal::readU16Le(u16_buf));
    if (fx.pixel_count < 1) fx.pixel_count = 1;

    uint8_t kind = 0;
    if (!lighting_runtime_internal::readExact(file, &kind, 1)) {
      if (error) *error = "read_failed";
      return false;
    }
    fx.is_rgb = kind == 1;
    fixtures_.push_back(fx);
  }

  if (!lighting_runtime_internal::readExact(file, u16_buf, sizeof(u16_buf))) {
    if (error) *error = "read_failed";
    return false;
  }
  const uint16_t scene_count = lighting_runtime_internal::readU16Le(u16_buf);
  if (scene_count > lighting_runtime_internal::kMaxSceneCount) {
    if (error) *error = "scene_count_too_large";
    return false;
  }
  scenes_.clear();
  scenes_.reserve(scene_count);

  for (uint16_t i = 0; i < scene_count; ++i) {
    lighting_runtime_internal::maybeYield(static_cast<uint32_t>(i + 1));
    SceneMeta meta;
    if (!readString(file, &meta.id, error)) return false;

    uint8_t end_behavior = 0;
    if (!lighting_runtime_internal::readExact(file, &end_behavior, 1)) {
      if (error) *error = "read_failed";
      return false;
    }
    meta.end_behavior = (end_behavior == 1) ? "repeat" : "stop";

    if (blob_version >= 3) {
      // v3+ scene metadata includes a signed priority after endBehavior.
      if (!lighting_runtime_internal::readExact(file, u16_buf, sizeof(u16_buf))) {
        if (error) *error = "read_failed";
        return false;
      }
    }
    if (blob_version >= 4) {
      // v4 adds blendMode code byte after priority.
      uint8_t blend_mode = 0;
      if (!lighting_runtime_internal::readExact(file, &blend_mode, 1)) {
        if (error) *error = "read_failed";
        return false;
      }
      (void)blend_mode;
    }

    if (!lighting_runtime_internal::readExact(file, u32_buf, sizeof(u32_buf))) {
      if (error) *error = "read_failed";
      return false;
    }
    meta.duration_ms = lighting_runtime_internal::readU32Le(u32_buf);

    if (!lighting_runtime_internal::readExact(file, u32_buf, sizeof(u32_buf))) {
      if (error) *error = "read_failed";
      return false;
    }
    meta.frame_count = lighting_runtime_internal::readU32Le(u32_buf);
    if (meta.frame_count > lighting_runtime_internal::kMaxFrameCount) {
      if (error) *error = "frame_count_too_large";
      return false;
    }
    meta.frames_offset = static_cast<uint32_t>(file.position());

    for (uint32_t fi = 0; fi < meta.frame_count; ++fi) {
      lighting_runtime_internal::maybeYield(fi + 1);
      if (!lighting_runtime_internal::readExact(file, u32_buf, sizeof(u32_buf))) {
        if (error) *error = "read_failed";
        return false;
      }
      if (!lighting_runtime_internal::readExact(file, u16_buf, sizeof(u16_buf))) {
        if (error) *error = "read_failed";
        return false;
      }
      const uint16_t change_count = lighting_runtime_internal::readU16Le(u16_buf);
      if (change_count > lighting_runtime_internal::kMaxChangeCount) {
        if (error) *error = "change_count_too_large";
        return false;
      }
      for (uint16_t ci = 0; ci < change_count; ++ci) {
        lighting_runtime_internal::maybeYield(static_cast<uint32_t>(ci + 1));
        uint8_t head[5];
        if (!lighting_runtime_internal::readExact(file, head, sizeof(head))) {
          if (error) *error = "read_failed";
          return false;
        }
        const uint8_t flags = head[4];
        size_t extra = 0;
        if (flags & 0x02u) extra += 3;  // color
        if (flags & 0x04u) extra += 1;  // brightness
        if (flags & 0x08u) extra += 1;  // intensity
        while (extra > 0) {
          uint8_t skip[8];
          size_t n = extra > sizeof(skip) ? sizeof(skip) : extra;
          if (!lighting_runtime_internal::readExact(file, skip, n)) {
            if (error) *error = "read_failed";
            return false;
          }
          extra -= n;
        }
      }
    }
    scenes_.push_back(meta);
  }

  blob_path_ = path;
  loaded_ = true;
  // Safety: start from a known-off state after loading fixtures/runtime.
  clearFixtures();
  (void)payload_len;
  return true;
}

bool LightingRuntime::readNextFrameHeader(ActiveFrame* out, String* error) {
  if (!out) return false;
  if (!active_file_) {
    if (error) *error = "stream_not_open";
    return false;
  }
  if (active_frame_idx_ >= active_scene_->frame_count) {
    out->loaded = false;
    return true;
  }
  uint8_t u32_buf[4];
  uint8_t u16_buf[2];
  if (!lighting_runtime_internal::readExact(active_file_, u32_buf, sizeof(u32_buf))) {
    if (error) *error = "read_failed";
    return false;
  }
  if (!lighting_runtime_internal::readExact(active_file_, u16_buf, sizeof(u16_buf))) {
    if (error) *error = "read_failed";
    return false;
  }
  out->at_ms = lighting_runtime_internal::readU32Le(u32_buf);
  out->change_count = lighting_runtime_internal::readU16Le(u16_buf);
  out->loaded = true;
  return true;
}

bool LightingRuntime::readAndApplyFrameChanges(uint16_t change_count, String* error) {
  if (!active_file_) {
    if (error) *error = "stream_not_open";
    return false;
  }
  driver_registry::beginRgbBatch();
  bool ok = true;
  for (uint16_t i = 0; i < change_count; ++i) {
    uint8_t head[5];
    if (!lighting_runtime_internal::readExact(active_file_, head, sizeof(head))) {
      if (error) *error = "read_failed";
      ok = false;
      break;
    }
    const uint16_t fixture_idx = lighting_runtime_internal::readU16Le(head);
    const int16_t pixel_index = lighting_runtime_internal::readI16Le(head + 2);
    const uint8_t flags = head[4];

    Change ch;
    ch.pixel_index = static_cast<int>(pixel_index);
    ch.off = (flags & 0x01u) != 0u;
    ch.color = "#ffffff";
    ch.brightness = 1.0f;
    ch.intensity = 1.0f;

    if (flags & 0x02u) {
      uint8_t rgb[3];
      if (!lighting_runtime_internal::readExact(active_file_, rgb, sizeof(rgb))) {
        if (error) *error = "read_failed";
        ok = false;
        break;
      }
      ch.color = lighting_runtime_internal::colorHexFromRgb(rgb[0], rgb[1], rgb[2]);
    }
    if (flags & 0x04u) {
      uint8_t b = 255;
      if (!lighting_runtime_internal::readExact(active_file_, &b, 1)) {
        if (error) *error = "read_failed";
        ok = false;
        break;
      }
      ch.brightness = static_cast<float>(b) / 255.0f;
    }
    if (flags & 0x08u) {
      uint8_t in = 255;
      if (!lighting_runtime_internal::readExact(active_file_, &in, 1)) {
        if (error) *error = "read_failed";
        ok = false;
        break;
      }
      ch.intensity = static_cast<float>(in) / 255.0f;
    }

    if (fixture_idx == lighting_runtime_internal::kWildcardFixture) {
      for (size_t fi = 0; fi < fixtures_.size(); ++fi) {
        if (ch.pixel_index >= fixtures_[fi].pixel_count) continue;
        applyChangeToFixture(ch, fixtures_[fi]);
      }
      continue;
    }
    if (fixture_idx >= fixtures_.size()) {
      continue;
    }
    const Fixture& fx = fixtures_[fixture_idx];
    if (ch.pixel_index >= fx.pixel_count) continue;
    applyChangeToFixture(ch, fx);
  }
  driver_registry::endRgbBatch();
  return ok;
}

bool LightingRuntime::applyChangeToFixture(const Change& change, const Fixture& fixture) {
  int pin = -1;
  if (!lighting_runtime_internal::parseTargetGpio(fixture.id, &pin)) return false;
  String fn;
  String dn;
  String impl;
  const bool has_binding = driver_registry::resolveDriverForTarget(
      lighting_runtime_internal::kMappingBlobPath,
      fixture.id,
      "Default",
      "RGB Strip",
      &fn,
      &dn,
      &impl);
  if (!has_binding) {
    return false;
  }
  const String fn_norm = driver_registry::normalizeFunctionName(fn);
  const bool is_rgb_target = fn_norm.equalsIgnoreCase("RgbStrip");
  const bool is_led_target = fn_norm.equalsIgnoreCase("Led");
  if (!is_rgb_target && !is_led_target) return false;

  const float strength = lighting_runtime_internal::clamp01(change.brightness) * lighting_runtime_internal::clamp01(change.intensity);

  if (is_rgb_target || fixture.is_rgb) {
    std::vector<uint16_t> indexes;
    if (change.pixel_index >= 0) {
      if (change.pixel_index < fixture.pixel_count) {
        indexes.push_back(static_cast<uint16_t>(change.pixel_index));
      }
    } else {
      indexes.reserve(fixture.pixel_count);
      for (int i = 0; i < fixture.pixel_count; ++i) indexes.push_back(static_cast<uint16_t>(i));
    }
    if (indexes.empty()) return false;

    String mode;
    if (change.off || strength <= 0.0f) {
      mode = change.force_clear ? "off_force" : "off";
    } else {
      mode = "on";
    }
    String error;
    bool ok = driver_registry::writeRgbPixelsForTarget(
        lighting_runtime_internal::kMappingBlobPath,
        fixture.id,
        dn,
        pin,
        fixture.pixel_count,
        indexes,
        mode,
        change.color,
        strength,
        1,
        50,
        nullptr,
        nullptr,
        nullptr,
        &error);
    if (ok) return true;
  }

  return is_led_target && driver_registry::writeOutputForTarget(
      lighting_runtime_internal::kMappingBlobPath,
      fixture.id,
      dn,
      pin,
      !change.off && strength > 0.0f,
      nullptr,
      nullptr,
      nullptr);
}

void LightingRuntime::setPixelsOverride(
    const String& target,
    const String& driver,
    int pin,
    int pixel_count,
    const std::vector<uint16_t>& indexes,
    const String& mode,
    const String& color,
    float brightness,
    uint16_t blink_count,
    uint32_t blink_interval_ms) {
  if (!target.length() || indexes.empty()) return;
  String normalized_mode = mode;
  normalized_mode.toLowerCase();
  if (normalized_mode != "on" && normalized_mode != "off" && normalized_mode != "blink") return;
  const int safe_pixel_count = pixel_count < 1 ? 1 : pixel_count;
  const float safe_brightness = lighting_runtime_internal::clamp01(brightness);
  for (size_t i = 0; i < indexes.size(); ++i) {
    const uint16_t idx = indexes[i];
    bool replaced = false;
    for (size_t oi = 0; oi < pixel_overrides_.size(); ++oi) {
      PixelOverride& row = pixel_overrides_[oi];
      if (row.target == target && row.pixel_index == idx) {
        row.driver = driver;
        row.pin = pin;
        row.pixel_count = safe_pixel_count;
        row.mode = normalized_mode;
        row.color = color;
        row.brightness = safe_brightness;
        row.blink_count = blink_count < 1 ? 1 : blink_count;
        row.blink_interval_ms = blink_interval_ms < 50 ? 50 : blink_interval_ms;
        row.last_apply_ms = 0;
        if (normalized_mode == "blink") {
          const unsigned long duration_ms = static_cast<unsigned long>(row.blink_count) *
                                            static_cast<unsigned long>(row.blink_interval_ms) * 2UL + 20UL;
          row.expires_at_ms = millis() + duration_ms;
        } else {
          row.expires_at_ms = 0;
        }
        replaced = true;
        break;
      }
    }
    if (replaced) continue;
    PixelOverride row;
    row.target = target;
    row.driver = driver;
    row.pin = pin;
    row.pixel_count = safe_pixel_count;
    row.pixel_index = idx;
    row.mode = normalized_mode;
    row.color = color;
    row.brightness = safe_brightness;
    row.blink_count = blink_count < 1 ? 1 : blink_count;
    row.blink_interval_ms = blink_interval_ms < 50 ? 50 : blink_interval_ms;
    row.last_apply_ms = 0;
    if (normalized_mode == "blink") {
      const unsigned long duration_ms = static_cast<unsigned long>(row.blink_count) *
                                        static_cast<unsigned long>(row.blink_interval_ms) * 2UL + 20UL;
      row.expires_at_ms = millis() + duration_ms;
    } else {
      row.expires_at_ms = 0;
    }
    pixel_overrides_.push_back(row);
  }
}

void LightingRuntime::setOutputOverride(const String& target, const String& driver, int pin, bool high) {
  if (!target.length()) return;
  for (size_t i = 0; i < output_overrides_.size(); ++i) {
    OutputOverride& row = output_overrides_[i];
    if (row.target == target && row.pin == pin) {
      row.driver = driver;
      row.high = high;
      row.last_apply_ms = 0;
      return;
    }
  }
  OutputOverride row;
  row.target = target;
  row.driver = driver;
  row.pin = pin;
  row.high = high;
  row.last_apply_ms = 0;
  output_overrides_.push_back(row);
}

void LightingRuntime::clearOutputOverride(const String& target, int pin) {
  if (!target.length()) return;
  for (size_t i = output_overrides_.size(); i > 0; --i) {
    OutputOverride& row = output_overrides_[i - 1];
    if (row.target == target && row.pin == pin) {
      output_overrides_.erase(output_overrides_.begin() + static_cast<long>(i - 1));
    }
  }
}

bool LightingRuntime::applyPixelOverride(PixelOverride& ov, unsigned long now_ms) {
  if (ov.mode == "blink" && ov.last_apply_ms != 0) return true;
  const unsigned long min_interval_ms = (ov.mode == "blink")
      ? (ov.blink_interval_ms < 50 ? 50 : ov.blink_interval_ms)
      : 25;
  if (ov.last_apply_ms != 0 && (now_ms - ov.last_apply_ms) < min_interval_ms) return true;
  std::vector<uint16_t> indexes;
  indexes.push_back(ov.pixel_index);
  String mode = ov.mode;
  if (mode != "on" && mode != "off" && mode != "blink") mode = "on";
  String write_error;
  const bool ok = driver_registry::writeRgbPixelsForTarget(
      lighting_runtime_internal::kMappingBlobPath,
      ov.target,
      ov.driver.length() ? ov.driver : String("Default"),
      ov.pin,
      ov.pixel_count < 1 ? 1 : ov.pixel_count,
      indexes,
      mode,
      ov.color.length() ? ov.color : String("#ffffff"),
      lighting_runtime_internal::clamp01(ov.brightness),
      ov.blink_count < 1 ? 1 : ov.blink_count,
      ov.blink_interval_ms < 50 ? 50 : ov.blink_interval_ms,
      nullptr,
      nullptr,
      nullptr,
      &write_error);
  if (ok) ov.last_apply_ms = now_ms;
  return ok;
}

void LightingRuntime::applyPixelOverrides(unsigned long now_ms) {
  if (pixel_overrides_.empty()) return;
  for (size_t i = 0; i < pixel_overrides_.size();) {
    PixelOverride& ov = pixel_overrides_[i];
    if (ov.mode == "blink" && ov.expires_at_ms != 0 && now_ms >= ov.expires_at_ms) {
      pixel_overrides_.erase(pixel_overrides_.begin() + static_cast<long>(i));
      continue;
    }
    applyPixelOverride(ov, now_ms);
    ++i;
  }
}

bool LightingRuntime::applyOutputOverride(OutputOverride& ov, unsigned long now_ms) {
  if (ov.last_apply_ms != 0 && (now_ms - ov.last_apply_ms) < 25) return true;
  const bool ok = driver_registry::writeOutputForTarget(
      lighting_runtime_internal::kMappingBlobPath,
      ov.target,
      ov.driver,
      ov.pin,
      ov.high,
      nullptr,
      nullptr,
      nullptr);
  if (ok) ov.last_apply_ms = now_ms;
  return ok;
}

void LightingRuntime::applyOutputOverrides(unsigned long now_ms) {
  if (output_overrides_.empty()) return;
  for (size_t i = 0; i < output_overrides_.size(); ++i) {
    applyOutputOverride(output_overrides_[i], now_ms);
  }
}

bool LightingRuntime::playScene(const String& scene_id, String* reason) {
  if (!loaded_) {
    if (reason) *reason = "not_loaded";
    return false;
  }
  if (!scene_id.length()) {
    if (reason) *reason = "missing_scene";
    return false;
  }

  const SceneMeta* found = nullptr;
  for (size_t i = 0; i < scenes_.size(); ++i) {
    if (scenes_[i].id == scene_id) {
      found = &scenes_[i];
      break;
    }
  }
  if (!found) {
    if (reason) *reason = "scene_not_found";
    return false;
  }

  fs::File file = LittleFS.open(blob_path_, "r");
  if (!file) {
    if (reason) *reason = "open_failed";
    return false;
  }
  if (!file.seek(found->frames_offset, SeekSet)) {
    file.close();
    if (reason) *reason = "seek_failed";
    return false;
  }

  stopScene("*");
  active_file_ = file;
  active_scene_ = found;
  active_started_ms_ = millis();
  last_service_ms_ = active_started_ms_;
  active_frame_idx_ = 0;
  cycle_count_ = 0;
  active_next_frame_ = ActiveFrame{};
  active_next_frame_.loaded = false;
  return true;
}

bool LightingRuntime::stopScene(const String& scene_id) {
  if (!active_scene_) return true;
  if (scene_id.length() && scene_id != "*" && active_scene_->id != scene_id) return true;
  clearFixtures();
  if (active_file_) active_file_.close();
  active_scene_ = nullptr;
  active_started_ms_ = 0;
  last_service_ms_ = 0;
  active_frame_idx_ = 0;
  active_next_frame_ = ActiveFrame{};
  return true;
}

void LightingRuntime::service(unsigned long now_ms) {
  if (last_service_ms_ == 0) last_service_ms_ = now_ms;
  const bool has_high_prio_overrides = !pixel_overrides_.empty() || !output_overrides_.empty();
  if (active_scene_ && has_high_prio_overrides && now_ms > last_service_ms_) {
    // Keep scene timeline stable while higher-priority overrides are active.
    active_started_ms_ += (now_ms - last_service_ms_);
  }
  last_service_ms_ = now_ms;

  if (!active_scene_) {
    applyPixelOverrides(now_ms);
    applyOutputOverrides(now_ms);
    return;
  }

  if (active_scene_->frame_count == 0) {
    String ended = active_scene_->id;
    stopScene(ended);
    EmittedEvent evt;
    evt.event_name = "LIGHT_SCENE_ENDED";
    evt.source = ended;
    evt.event_type = "ENDED";
    evt.ts_ms = now_ms;
    emitted_events_.push_back(evt);
    applyPixelOverrides(now_ms);
    applyOutputOverrides(now_ms);
    return;
  }

  uint32_t elapsed = static_cast<uint32_t>(now_ms - active_started_ms_);
  const uint32_t duration_ms = active_scene_->duration_ms;

  if (active_scene_->end_behavior == "repeat" && duration_ms > 0) {
    const uint32_t current_cycle = elapsed / duration_ms;
    if (current_cycle != cycle_count_) {
      cycle_count_ = current_cycle;
      active_frame_idx_ = 0;
      active_next_frame_ = ActiveFrame{};
      if (active_file_) {
        active_file_.seek(active_scene_->frames_offset, SeekSet);
      }
    }
    elapsed = elapsed % duration_ms;
  } else if (duration_ms > 0 && elapsed > duration_ms) {
    String ended = active_scene_->id;
    stopScene(ended);
    EmittedEvent evt;
    evt.event_name = "LIGHT_SCENE_ENDED";
    evt.source = ended;
    evt.event_type = "ENDED";
    evt.ts_ms = now_ms;
    emitted_events_.push_back(evt);
    applyPixelOverrides(now_ms);
    applyOutputOverrides(now_ms);
    return;
  }

  if (!active_next_frame_.loaded) {
    String read_error;
    if (!readNextFrameHeader(&active_next_frame_, &read_error)) {
      String ended = active_scene_->id;
      stopScene(ended);
      applyPixelOverrides(now_ms);
      applyOutputOverrides(now_ms);
      return;
    }
    if (!active_next_frame_.loaded) {
      if (active_scene_->end_behavior == "repeat") {
        if (active_file_) {
          active_file_.seek(active_scene_->frames_offset, SeekSet);
        }
        active_frame_idx_ = 0;
        active_next_frame_ = ActiveFrame{};
        if (active_scene_->duration_ms == 0) {
          active_started_ms_ = now_ms;
          cycle_count_ += 1;
        }
        applyPixelOverrides(now_ms);
        applyOutputOverrides(now_ms);
        return;
      }
      String ended = active_scene_->id;
      stopScene(ended);
      EmittedEvent evt;
      evt.event_name = "LIGHT_SCENE_ENDED";
      evt.source = ended;
      evt.event_type = "ENDED";
      evt.ts_ms = now_ms;
      emitted_events_.push_back(evt);
      applyPixelOverrides(now_ms);
      applyOutputOverrides(now_ms);
      return;
    }
  }

  if (active_next_frame_.at_ms > elapsed) {
    applyPixelOverrides(now_ms);
    applyOutputOverrides(now_ms);
    return;
  }

  String apply_error;
  if (!readAndApplyFrameChanges(active_next_frame_.change_count, &apply_error)) {
    String ended = active_scene_->id;
    stopScene(ended);
    applyPixelOverrides(now_ms);
    applyOutputOverrides(now_ms);
    return;
  }
  active_frame_idx_ += 1;
  active_next_frame_.loaded = false;

  applyPixelOverrides(now_ms);
  applyOutputOverrides(now_ms);
}

void LightingRuntime::clearFixtures() {
  for (size_t i = 0; i < fixtures_.size(); ++i) {
    Change off;
    off.off = true;
    off.force_clear = true;
    off.brightness = 0.0f;
    off.intensity = 0.0f;
    off.pixel_index = -1;
    applyChangeToFixture(off, fixtures_[i]);
  }
}

bool LightingRuntime::popEmittedEvent(EmittedEvent* out) {
  if (!out) return false;
  if (emitted_events_.empty()) return false;
  *out = emitted_events_.front();
  emitted_events_.erase(emitted_events_.begin());
  return true;
}

void LightingRuntime::clear() {
  stopScene("*");
  blob_path_ = "";
  fixtures_.clear();
  scenes_.clear();
  emitted_events_.clear();
  output_overrides_.clear();
  loaded_ = false;
  active_scene_ = nullptr;
  active_started_ms_ = 0;
  active_frame_idx_ = 0;
  cycle_count_ = 0;
  last_service_ms_ = 0;
  active_next_frame_ = ActiveFrame{};
  pixel_overrides_.clear();
}
