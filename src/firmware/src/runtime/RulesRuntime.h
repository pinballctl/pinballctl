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
  void applyEvent(const String& event_name, const String& source, const String& event_type);
  void clear();

 private:
  struct RuleAction {
    int pin = -1;
    bool value_high = false;
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

  std::vector<EventRule> rules_;
};

#endif  // PINBALLCTL_RULES_RUNTIME_H
