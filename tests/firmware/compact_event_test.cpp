#include <cassert>
#include "protocol/core/CompactEvent.h"

int main() {
  using namespace compact_event;
  Encoder event("B__GPIO__1_CLOSED", "B__GPIO__1", "CLOSED", 0xfffffffe, 0x01020304, 500, 3, true, 0);
  event.addState("B__GPIO__1", "B__GPIO__2", Open);
  event.addState("B__GPIO__1", "coil", Active);
  const std::vector<uint8_t> expected = {
    0x39, 3, 0xff, 0xff, 0xff, 0xfe, 1, 2, 3, 4, 0, 0, 1, 0xf4,
    0, 10, 'B', '_', '_', 'G', 'P', 'I', 'O', '_', '_', '1',
    0, 6, 'C', 'L', 'O', 'S', 'E', 'D',
    9, Open, 0, 1, '2', 0, Active, 0, 4, 'c', 'o', 'i', 'l',
  };
  assert(event.bytes == expected);
  Encoder diagnostic("probe", "diagnostic", "", 1, 50, 0, 0, false, -1);
  assert(diagnostic.bytes.front() == 0);
}
