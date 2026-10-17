#include <cassert>
#include "core/FramedSerial.h"
FakeSerial Serial;
int main() {
  FramedSerial frames;
  assert(frames.enqueue("one"));
  assert(frames.enqueue("two"));
  Serial.space = 0;
  frames.pump();
  assert(Serial.bytes.empty());
  Serial.space = 100;
  Serial.write_limit = 3;
  frames.pump();
  std::vector<uint8_t> expected = {0,0,0,4,1,'o','n','e',0,0,0,4,1,'t','w','o'};
  assert(Serial.bytes == expected);
  assert(frames.queueFree() == FramedSerial::kQueueMax);
  Serial.bytes.clear();
  Serial.space = 4096;
  Serial.write_limit = 8192;
  assert(frames.enqueue(String(1500, 'x')));
  frames.pump();
  assert(Serial.bytes.size() == 1024);
  assert(frames.queueFree() == FramedSerial::kQueueMax - 1);
  Serial.write_limit = 0;
  frames.pump();
  assert(Serial.bytes.size() == 1024);
  Serial.write_limit = 8192;
  frames.pump();
  assert(Serial.bytes.size() == 1505);
  assert(frames.queueFree() == FramedSerial::kQueueMax);
}
