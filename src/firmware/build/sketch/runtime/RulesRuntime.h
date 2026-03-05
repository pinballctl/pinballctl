#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/runtime/RulesRuntime.h"
#ifndef PINBALLCTL_RULES_RUNTIME_H
#define PINBALLCTL_RULES_RUNTIME_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

#include "drivers/Button/Default.h"

class RulesRuntime {
 public:
  struct EmittedEvent {
    String event_name;
    String source;
    String event_type;
    uint32_t seq = 0;
    unsigned long ts_ms = 0;
    uint32_t detail_ms = 0;
  };

  RulesRuntime();

  bool loadFromSetRulesCommand(const String& payload_line, String* error);
  bool loadFromRulesBlob(const char* path, String* error);
  bool applyEvent(
      const String& event_name,
      const String& source,
      const String& event_type,
      uint32_t seq,
      unsigned long now_ms,
      uint32_t detail_ms = 0);
  void service(unsigned long now_ms);
  bool popEmittedEvent(EmittedEvent* out_event);
  void clear();

 private:
  struct RuleAction {
    enum Kind : uint8_t { SET_OUTPUT = 0, PULSE = 1, LCD_TEXT = 2, LIGHT_PIXELS = 3 } kind = SET_OUTPUT;
    int pin = -1;
    bool value_high = false;
    uint32_t duration_ms = 0;
    String target;
    String driver;
    int sda_pin = -1;
    int scl_pin = -1;
    uint8_t lcd_addr = 0x27;
    uint8_t lcd_cols = 16;
    uint8_t lcd_rows = 2;
    bool lcd_clear_first = false;
    String lcd_target;
    String lcd_driver;
    String lcd_line1;
    String lcd_line2;
    std::vector<uint16_t> pixel_indexes;
    uint16_t pixel_count = 1;
    String pixels_mode;
    String pixels_color;
    float pixels_brightness = 1.0f;
    uint16_t pixels_blink_count = 2;
    uint32_t pixels_blink_interval_ms = 150;
  };

  struct EventRule {
    String event_name;
    String source;
    String event_type;
    uint32_t min_ms = 0;
    uint32_t repeat_ms = 0;
    uint32_t window_ms = 0;
    std::vector<RuleAction> actions;
  };

  bool compileFromRulesArray(JsonVariant rules_var, String* error);
  bool parseRuleActions(JsonObject rule, std::vector<RuleAction>* actions_out);
  void appendTriggers(JsonObject rule, const std::vector<RuleAction>& actions, std::vector<EventRule>* out_rules);
  static bool parseTargetGpio(const String& target, int* pin_out);
  static bool parseOutputValue(const String& action_type, const String& value, bool* out_high);
  static String upper(const String& s);
  static bool extractGzipDeflatePayload(const std::vector<uint8_t>& in, const uint8_t** deflate_ptr, size_t* deflate_len);

  struct ActivePulse {
    int pin = -1;
    unsigned long end_ms = 0;
    String target;
    String driver;
  };

  struct ReleasePair {
    String source;
    int pin = -1;
    String target;
    String driver;
  };

  struct HeldOutput {
    String source;
    int pin = -1;
    String target;
    String driver;
    unsigned long auto_release_at_ms = 0;
  };

  struct EventSeqState {
    String event_name;
    String source;
    uint32_t last_seq = 0;
  };

  struct PinSafeState {
    int pin = -1;
    bool safe_high = false;
  };

  struct SourceWatch {
    String source;
    int pin = -1;
    std::vector<String> event_names;
    ButtonDefault::Config button_cfg;
    ButtonDefault::Instance button;
  };

  bool acceptEventSeq(const String& event_name, const String& source, uint32_t seq);
  void rebuildSourceWatches(const std::vector<EventRule>& compiled_rules);
  SourceWatch* findOrCreateWatch(const String& source, int pin);
  void appendWatchEventNameUnique(SourceWatch* watch, const String& event_name);
  void serviceInputWatches(unsigned long now_ms);
  void dispatchWatchEvent(SourceWatch& watch, const String& event_type, unsigned long now_ms, uint32_t detail_ms = 0);
  void enqueueEmittedEvent(
      const String& event_name,
      const String& source,
      const String& event_type,
      unsigned long ts_ms,
      uint32_t detail_ms = 0);
  bool hasReleasePair(const String& source, int pin) const;
  unsigned long computeHeldAutoReleaseAt(const String& target, const String& driver, int pin, unsigned long now_ms) const;
  void markHeldOutput(const String& source, int pin, const String& target, const String& driver);
  void clearHeldOutput(const String& source, int pin);
  void clearHeldOutputsForSource(const String& source);
  void forceReleasePairsForSource(const String& source);
  void restoreSafeStateForStaleEvent(const String& source);
  static bool loadMappingSafeStatesCached(std::vector<PinSafeState>* out_states);
  static bool lookupSafeStateForPin(const std::vector<PinSafeState>& safe_states, int pin, bool* safe_high_out);
  void drivePinToMappedSafe(const String& target, const String& driver, int pin, const std::vector<PinSafeState>& safe_states);

  void stopPulseForPin(int pin);
  bool driveOutputTarget(const String& target, const String& driver, int pin, bool high);
  std::vector<EventRule> rules_;
  std::vector<ActivePulse> active_pulses_;
  std::vector<ReleasePair> release_pairs_;
  std::vector<HeldOutput> held_outputs_;
  std::vector<EventSeqState> event_seq_state_;
  std::vector<SourceWatch> source_watches_;
  std::vector<EmittedEvent> emitted_events_;
  uint32_t emitted_event_seq_ = 0;
};

#endif  // PINBALLCTL_RULES_RUNTIME_H
