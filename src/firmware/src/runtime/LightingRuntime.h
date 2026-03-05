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
  void service(unsigned long now_ms);
  bool popEmittedEvent(EmittedEvent* out);
  void clear();

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

  bool readBlobHeader(const char* path, uint32_t* payload_len, String* error);
  bool readString(fs::File& file, String* out, String* error);
  bool readNextFrameHeader(ActiveFrame* out, String* error);
  bool readAndApplyFrameChanges(uint16_t change_count, String* error);
  bool applyChangeToFixture(const Change& change, const Fixture& fixture);
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
};

#endif  // PINBALLCTL_LIGHTING_RUNTIME_H
