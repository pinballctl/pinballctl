// LineCommandParser: newline-delimited command buffer for serial input.

#include "core/LineCommandParser.h"

LineCommandParser::LineCommandParser() : buffer_(), last_line_() {}

bool LineCommandParser::feed(char c) {
  if (c == '\n' || c == '\r') {
    if (buffer_.length() > 0) {
      last_line_ = buffer_;
      buffer_ = "";
      return true;
    }
    buffer_ = "";
    return false;
  }

  buffer_ += c;
  if (buffer_.length() > 256) {
    buffer_ = "";
  }
  return false;
}

const String& LineCommandParser::line() const {
  return last_line_;
}

void LineCommandParser::clearLine() {
  last_line_ = "";
}
