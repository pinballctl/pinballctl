#include "drivers/Button/Default.h"

void ButtonDefault::Instance::normalizeConfig(Config* cfg) {
  if (!cfg) return;
  if (cfg->double_click_window_ms == 0) cfg->double_click_window_ms = 280;
  if (cfg->debounce_ms == 0) cfg->debounce_ms = 25;

  auto dedupe_sort = [](std::vector<uint32_t>* values) {
    if (!values) return;
    std::vector<uint32_t> out;
    out.reserve(values->size());
    for (size_t i = 0; i < values->size(); ++i) {
      uint32_t v = (*values)[i];
      if (v == 0) continue;
      bool exists = false;
      for (size_t j = 0; j < out.size(); ++j) {
        if (out[j] == v) {
          exists = true;
          break;
        }
      }
      if (!exists) out.push_back(v);
    }
    if (out.size() > 1) {
      for (size_t i = 0; i + 1 < out.size(); ++i) {
        for (size_t j = i + 1; j < out.size(); ++j) {
          if (out[j] < out[i]) {
            uint32_t t = out[i];
            out[i] = out[j];
            out[j] = t;
          }
        }
      }
    }
    values->swap(out);
  };

  dedupe_sort(&cfg->held_thresholds_ms);
  dedupe_sort(&cfg->repeat_intervals_ms);
}

void ButtonDefault::Instance::bindPin(int pin) {
  if (pin_ == pin) return;
  pin_ = pin;
  initialized_ = false;
}

void ButtonDefault::Instance::reset() {
  initialized_ = false;
  active_ = false;
  held_emitted_ = false;
  click_count_ = 0;
  next_hold_index_ = 0;
  first_release_ms_ = 0;
  click_deadline_ms_ = 0;
  repeat_next_ms_.clear();
}

void ButtonDefault::Instance::configure(const Config& config) {
  cfg_ = config;
  normalizeConfig(&cfg_);
  reset();
}

void ButtonDefault::Instance::emit(EventType type, uint32_t detail_ms, std::vector<Event>* out_events) {
  if (!out_events) return;
  Event evt;
  evt.type = type;
  evt.detail_ms = detail_ms;
  out_events->push_back(evt);
}

void ButtonDefault::Instance::service(unsigned long now_ms, std::vector<Event>* out_events) {
  if (pin_ < 0) return;

  if (!initialized_) {
    pinMode(pin_, INPUT_PULLUP);
    bool initial_high = (digitalRead(pin_) == HIGH);
    initialized_ = true;
    stable_high_ = initial_high;
    raw_high_ = initial_high;
    idle_high_ = initial_high;
    active_ = false;
    held_emitted_ = false;
    raw_changed_ms_ = now_ms;
    press_start_ms_ = now_ms;
    click_count_ = 0;
    next_hold_index_ = 0;
    first_release_ms_ = 0;
    click_deadline_ms_ = 0;
    repeat_next_ms_.assign(cfg_.repeat_intervals_ms.size(), 0);
    return;
  }

  bool raw_high = (digitalRead(pin_) == HIGH);
  if (raw_high != raw_high_) {
    raw_high_ = raw_high;
    raw_changed_ms_ = now_ms;
  }

  if (raw_high_ != stable_high_ && static_cast<unsigned long>(now_ms - raw_changed_ms_) >= cfg_.debounce_ms) {
    stable_high_ = raw_high_;
    bool is_active_now = (stable_high_ != idle_high_);
    if (is_active_now != active_) {
      active_ = is_active_now;
      if (active_) {
        press_start_ms_ = now_ms;
        held_emitted_ = false;
        next_hold_index_ = 0;
        repeat_next_ms_.assign(cfg_.repeat_intervals_ms.size(), 0);
        for (size_t ri = 0; ri < cfg_.repeat_intervals_ms.size(); ++ri) {
          repeat_next_ms_[ri] = now_ms + static_cast<unsigned long>(cfg_.repeat_intervals_ms[ri]);
        }
        emit(EventType::PRESSED, 0, out_events);
      } else {
        emit(EventType::RELEASED, 0, out_events);
        if (!held_emitted_) {
          if (!cfg_.enable_double_click) {
            emit(EventType::CLICKED, 0, out_events);
            click_count_ = 0;
            first_release_ms_ = 0;
            click_deadline_ms_ = 0;
          } else {
            if (click_count_ == 0) {
              click_count_ = 1;
              first_release_ms_ = now_ms;
              click_deadline_ms_ = now_ms + cfg_.double_click_window_ms;
            } else {
              uint32_t gap_ms = static_cast<uint32_t>(now_ms - first_release_ms_);
              if (static_cast<long>(now_ms - click_deadline_ms_) <= 0) {
                emit(EventType::DOUBLE_CLICKED, gap_ms, out_events);
                click_count_ = 0;
                first_release_ms_ = 0;
                click_deadline_ms_ = 0;
              } else {
                emit(EventType::CLICKED, 0, out_events);
                click_count_ = 1;
                first_release_ms_ = now_ms;
                click_deadline_ms_ = now_ms + cfg_.double_click_window_ms;
              }
            }
          }
        } else {
          click_count_ = 0;
          first_release_ms_ = 0;
          click_deadline_ms_ = 0;
        }
      }
    }
  }

  if (active_) {
    unsigned long held_ms = static_cast<unsigned long>(now_ms - press_start_ms_);
    while (next_hold_index_ < cfg_.held_thresholds_ms.size() && held_ms >= cfg_.held_thresholds_ms[next_hold_index_]) {
      held_emitted_ = true;
      uint32_t threshold_ms = cfg_.held_thresholds_ms[next_hold_index_];
      emit(EventType::HELD, threshold_ms, out_events);
      next_hold_index_++;
    }
    for (size_t ri = 0; ri < cfg_.repeat_intervals_ms.size(); ++ri) {
      unsigned long due_ms = (ri < repeat_next_ms_.size()) ? repeat_next_ms_[ri] : 0;
      unsigned long interval_ms = static_cast<unsigned long>(cfg_.repeat_intervals_ms[ri]);
      if (interval_ms == 0) continue;
      if (due_ms == 0) {
        if (ri >= repeat_next_ms_.size()) repeat_next_ms_.resize(ri + 1, 0);
        repeat_next_ms_[ri] = now_ms + interval_ms;
        due_ms = repeat_next_ms_[ri];
      }
      while (static_cast<long>(now_ms - due_ms) >= 0) {
        held_emitted_ = true;
        emit(EventType::REPEAT_WHILE_HELD, static_cast<uint32_t>(interval_ms), out_events);
        due_ms += interval_ms;
      }
      repeat_next_ms_[ri] = due_ms;
    }
  }

  if (!active_ && cfg_.enable_double_click && click_count_ == 1 && click_deadline_ms_ != 0 &&
      static_cast<long>(now_ms - click_deadline_ms_) >= 0) {
    emit(EventType::CLICKED, 0, out_events);
    click_count_ = 0;
    first_release_ms_ = 0;
    click_deadline_ms_ = 0;
  }
}
