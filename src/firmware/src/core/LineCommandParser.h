#ifndef PINBALLCTL_LINE_COMMAND_PARSER_H
#define PINBALLCTL_LINE_COMMAND_PARSER_H

// LineCommandParser: newline-delimited command buffer for serial input.

#include <Arduino.h>

class LineCommandParser {
 public:
  LineCommandParser();

  bool feed(char c);
  const String& line() const;
  void clearLine();

 private:
  String buffer_;
  String last_line_;
};

#endif  // PINBALLCTL_LINE_COMMAND_PARSER_H
