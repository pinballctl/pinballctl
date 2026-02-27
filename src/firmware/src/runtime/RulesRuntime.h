#ifndef PINBALLCTL_RULES_RUNTIME_H
#define PINBALLCTL_RULES_RUNTIME_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

class RulesRuntime {
 public:
  RulesRuntime();

  bool loadFromSetRulesCommand(const String& payload_line, String* error);
  bool loadFromRulesBlob(const char* path, String* error);
  bool applyEvent(const String& event_name, const String& source, const String& event_type, uint32_t seq, unsigned long now_ms);
  void service(unsigned long now_ms);
  void clear();

 private:
  struct RuleAction {
    enum Kind : uint8_t { SET_OUTPUT = 0, PULSE = 1 } kind = SET_OUTPUT;
    int pin = -1;
    bool value_high = false;
    uint32_t duration_ms = 0;
  };

  struct EventRule {
    String event_name;
    String source;
    String event_type;
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

  bool acceptEventSeq(const String& event_name, const String& source, uint32_t seq);
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
};

#endif  // PINBALLCTL_RULES_RUNTIME_H
