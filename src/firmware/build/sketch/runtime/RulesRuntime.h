#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/runtime/RulesRuntime.h"
#ifndef PINBALLCTL_RULES_RUNTIME_H
#define PINBALLCTL_RULES_RUNTIME_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

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
    enum Kind : uint8_t { SET_OUTPUT = 0, PULSE = 1, LCD_TEXT = 2 } kind = SET_OUTPUT;
    int pin = -1;
    bool value_high = false;
    uint32_t duration_ms = 0;
    int sda_pin = -1;
    int scl_pin = -1;
    uint8_t lcd_addr = 0x27;
    uint8_t lcd_cols = 16;
    uint8_t lcd_rows = 2;
    bool lcd_clear_first = false;
    String lcd_line1;
    String lcd_line2;
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
  };

  struct ReleasePair {
    String source;
    int pin = -1;
  };

  struct HeldOutput {
    String source;
    int pin = -1;
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
    std::vector<uint32_t> held_thresholds_ms;
    std::vector<uint32_t> repeat_intervals_ms;
    std::vector<unsigned long> repeat_next_ms;
    bool enable_double_click = false;
    unsigned long double_click_window_ms = 280;
    bool initialized = false;
    bool stable_high = false;
    bool raw_high = false;
    bool idle_high = false;
    bool active = false;
    bool held_emitted = false;
    unsigned long raw_changed_ms = 0;
    unsigned long press_start_ms = 0;
    uint8_t click_count = 0;
    size_t next_hold_index = 0;
    unsigned long first_release_ms = 0;
    unsigned long click_deadline_ms = 0;
  };

  static constexpr unsigned long kInputDebounceMs = 25;
  static constexpr unsigned long kInputHoldMs = 450;
  static constexpr unsigned long kInputDoubleClickMs = 280;

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
  void markHeldOutput(const String& source, int pin);
  void clearHeldOutput(const String& source, int pin);
  void clearHeldOutputsForSource(const String& source);
  void forceReleasePairsForSource(const String& source);
  void restoreSafeStateForStaleEvent(const String& source);
  static bool loadMappingSafeStatesCached(std::vector<PinSafeState>* out_states);
  static bool lookupSafeStateForPin(const std::vector<PinSafeState>& safe_states, int pin, bool* safe_high_out);
  void drivePinToMappedSafe(int pin, const std::vector<PinSafeState>& safe_states);

  void stopPulseForPin(int pin);
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
