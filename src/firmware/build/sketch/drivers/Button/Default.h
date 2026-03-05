#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/drivers/Button/Default.h"
#ifndef PINBALLCTL_BUTTON_DEFAULT_H
#define PINBALLCTL_BUTTON_DEFAULT_H

#include <Arduino.h>
#include <vector>

class ButtonDefault {
 public:
  static constexpr const char* kFunction = "Button";
  static constexpr const char* kDriver = "Default";

  enum class EventType : uint8_t {
    PRESSED = 0,
    RELEASED = 1,
    CLICKED = 2,
    DOUBLE_CLICKED = 3,
    HELD = 4,
    REPEAT_WHILE_HELD = 5,
  };

  struct Event {
    EventType type = EventType::PRESSED;
    uint32_t detail_ms = 0;
  };

  struct Config {
    bool enable_double_click = false;
    uint32_t double_click_window_ms = 280;
    unsigned long debounce_ms = 25;
    std::vector<uint32_t> held_thresholds_ms;
    std::vector<uint32_t> repeat_intervals_ms;
  };

  class Instance {
   public:
    void bindPin(int pin);
    void configure(const Config& config);
    void service(unsigned long now_ms, std::vector<Event>* out_events);
    void reset();

   private:
    void emit(EventType type, uint32_t detail_ms, std::vector<Event>* out_events);
    static void normalizeConfig(Config* cfg);

    Config cfg_;
    int pin_ = -1;
    bool initialized_ = false;
    bool stable_high_ = false;
    bool raw_high_ = false;
    bool idle_high_ = false;
    bool active_ = false;
    bool held_emitted_ = false;
    unsigned long raw_changed_ms_ = 0;
    unsigned long press_start_ms_ = 0;
    uint8_t click_count_ = 0;
    size_t next_hold_index_ = 0;
    unsigned long first_release_ms_ = 0;
    unsigned long click_deadline_ms_ = 0;
    std::vector<unsigned long> repeat_next_ms_;
  };
};

#endif  // PINBALLCTL_BUTTON_DEFAULT_H
