#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
using String = std::string;
constexpr int HIGH=1, INPUT_PULLUP=2;
extern int button_level;
inline void pinMode(int, int) {}
inline int digitalRead(int) { return button_level; }
