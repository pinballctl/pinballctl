#ifndef PINBALLCTL_LIGHTING_RUNTIME_H
#define PINBALLCTL_LIGHTING_RUNTIME_H

#include <Arduino.h>
#include <FS.h>
#include <vector>

class LightingRuntime {
 public:
  struct EmittedEvent {
    String event_name;
    String source;
    String event_type;
    uint32_t ts_ms = 0;
  };

  bool loadFromLightingBlob(const char* path, String* error);
  bool playScene(const String& scene_id, String* reason = nullptr);
  bool stopScene(const String& scene_id);
  bool isSceneActive() const { return active_scene_ != nullptr; }
  String activeSceneId() const { return active_scene_ ? active_scene_->id : String(""); }
  void setPixelsOverride(
      const String& target,
      const String& driver,
      int pin,
      int pixel_count,
      const std::vector<uint16_t>& indexes,
      const String& mode,
      const String& color,
      float brightness,
      uint16_t blink_count,
      uint32_t blink_interval_ms);
  void setOutputOverride(const String& target, const String& driver, int pin, bool high);
  void clearOutputOverride(const String& target, int pin);
  void service(unsigned long now_ms);
  bool popEmittedEvent(EmittedEvent* out);
  void clear();
  size_t overrideCount() const { return pixel_overrides_.size(); }

 private:
  struct Change {
    int pixel_index = -1;
    bool off = false;
    bool force_clear = false;
    String color = "#ffffff";
    float brightness = 1.0f;
    float intensity = 1.0f;
  };

  struct Fixture {
    String id;
    int pixel_count = 1;
    bool is_rgb = false;
  };

  struct SceneMeta {
    String id;
    String end_behavior = "stop";
    uint32_t duration_ms = 0;
    uint32_t frame_count = 0;
    uint32_t frames_offset = 0;
  };

  struct ActiveFrame {
    uint32_t at_ms = 0;
    uint16_t change_count = 0;
    bool loaded = false;
  };

  struct PixelOverride {
    String target;
    String driver;
    int pin = -1;
    int pixel_count = 1;
    uint16_t pixel_index = 0;
    String mode = "on";
    String color = "#ffffff";
    float brightness = 1.0f;
    uint16_t blink_count = 1;
    uint32_t blink_interval_ms = 50;
    unsigned long last_apply_ms = 0;
    unsigned long expires_at_ms = 0;
  };

  struct OutputOverride {
    String target;
    String driver;
    int pin = -1;
    bool high = false;
    unsigned long last_apply_ms = 0;
  };

  bool readBlobHeader(const char* path, uint16_t* version, uint32_t* payload_len, String* error);
  bool readString(fs::File& file, String* out, String* error);
  bool readNextFrameHeader(ActiveFrame* out, String* error);
  bool readAndApplyFrameChanges(uint16_t change_count, String* error);
  bool applyChangeToFixture(const Change& change, const Fixture& fixture);
  bool applyPixelOverride(PixelOverride& ov, unsigned long now_ms);
  void applyPixelOverrides(unsigned long now_ms);
  bool applyOutputOverride(OutputOverride& ov, unsigned long now_ms);
  void applyOutputOverrides(unsigned long now_ms);
  void clearFixtures();

  bool loaded_ = false;
  String blob_path_;
  std::vector<Fixture> fixtures_;
  std::vector<SceneMeta> scenes_;
  std::vector<EmittedEvent> emitted_events_;

  fs::File active_file_;
  const SceneMeta* active_scene_ = nullptr;
  unsigned long active_started_ms_ = 0;
  uint32_t active_frame_idx_ = 0;
  ActiveFrame active_next_frame_;
  uint32_t cycle_count_ = 0;
  unsigned long last_service_ms_ = 0;
  std::vector<PixelOverride> pixel_overrides_;
  std::vector<OutputOverride> output_overrides_;
};

#endif  // PINBALLCTL_LIGHTING_RUNTIME_H
