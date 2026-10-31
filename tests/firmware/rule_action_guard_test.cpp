#include <cassert>
#include "runtime/RuleActionGuard.h"
int main() {
  using rule_action_guard::accept;
  assert(accept(1000,750,true,false,false,false,true,true));
  assert(!accept(1001,750,true,false,false,false,true,true));
  assert(!accept(1000,900,false,false,false,false,false,true));
  assert(!accept(1000,900,true,true,false,false,false,true));
  assert(!accept(1000,900,true,false,true,false,false,true));
  assert(!accept(1000,900,true,false,false,true,false,true));
  assert(!accept(1000,900,true,false,false,false,true,false)); // Released while Pi was deciding.
  assert(accept(1000,900,true,false,false,false,false,false)); // Release/off action allowed.
  assert(accept(20,0xfffffff0U,true,false,false,false,true,true));
  assert(!accept(1000,1001,true,false,false,false,false,true)); // Future/foreign timestamp.
}
