#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
using String = std::string;
constexpr int LOW=0, HIGH=1, INPUT_PULLUP=2, INPUT_PULLDOWN=3;
extern int button_level;
extern int button_mode;
inline void pinMode(int, int mode) { button_mode = mode; }
inline int digitalRead(int) { return button_level; }
