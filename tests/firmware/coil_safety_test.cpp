#include <cassert>
#include <cstdint>
#include <initializer_list>
#include "safety/CoilSafetyCore.h"
using namespace coil_safety;
bool levels[kPins];
void level(int pin,bool high) { levels[pin]=high; }
Core configured(uint32_t now=1000) {
  Core c(level);
  c.pins[1].limit={100,200,false,true};
  c.pins[2].limit={100,200,true,true};
  c.host_seen=true; c.host_at=now; c.loop_at=now;
  return c;
}
void alive(Core& c,uint32_t now) { c.host_at=now; c.loop_at=now; c.tick(now); }
int main() {
  auto c=configured();
  c.pins[1].limit.enabled=false; c.pins[2].limit.enabled=false;
  assert(!c.enable(c.generation,1000));
  c.pins[2].limit.enabled=true; assert(c.enable(c.generation,1000));
  assert(!c.write(1,true,1000));
  c=configured();
  assert(!c.write(1,true,1000)); assert(!c.write(3,true,1000));
  assert(!c.enable(c.generation+1,1000)); assert(c.enable(c.generation,1000));
  assert(c.write(1,true,1000) && levels[1]);
  assert(c.write(2,true,1000) && !levels[2]);
  c.tick(1010); // Default pulse terminates normally, including active-low output.
  assert(c.armed && c.fault==Fault::None && !levels[1] && levels[2]);
  assert(!c.write(1,true,1011) && c.fault==Fault::Cooldown);
  c.fault=Fault::None; assert(!c.enable(c.generation,1011));
  alive(c,1300); assert(c.enable(c.generation,1300));
  assert(!c.pulse(1,101,1300) && c.fault==Fault::InvalidRequest && !levels[1]);

  c=configured(); assert(c.enable(c.generation,1000));
  assert(c.pulse(1,100,1000)); assert(c.pulse(1,100,1099));
  c.tick(1100); assert(!levels[1] && c.armed); // Repeat does not extend pulse.
  c=configured(); assert(c.enable(c.generation,1000)); c.pulse(1,100,1000);
  c.tick(1101); assert(c.fault==Fault::MaxOn && !levels[1]); // Overdue ISR trips.

  c=configured(); assert(c.enable(c.generation,1000));
  c.loop_at=1900; c.tick(2000); assert(c.fault==Fault::HostLost);
  c=configured(); assert(c.enable(c.generation,1000));
  c.host_at=1499; c.tick(1500); assert(c.fault==Fault::LoopStalled);

  // PWM: full-power kick, reduced duty, immediate release, finite hold deadline.
  c=configured(); c.pins[1].limit.mode=Mode::Pwm; c.pins[1].limit.hold_duty=25;
  c.pins[1].limit.max_hold_ms=50;
  assert(c.enable(c.generation,1000)); assert(c.write(1,true,1000));
  c.tick(1009); assert(levels[1]); c.tick(1010); assert(c.pins[1].holding);
  c.pwmTick(1010000); assert(levels[1]);
  c.pwmTick(1012500); assert(!levels[1]);
  c.pwmTick(1019900); assert(!levels[1]);
  assert(c.write(1,true,1050)); c.tick(1060);
  assert(c.fault==Fault::MaxHold && !levels[1]);
  // Every supported PWM frequency/duty has the intended number of ON ticks.
  for (uint32_t hz : {50U,100U,250U,500U}) {
    for (uint32_t duty=5; duty<=95; duty+=5) {
      c=configured(); c.pins[1].limit.mode=Mode::Pwm;
      c.pins[1].limit.pwm_hz=hz; c.pins[1].limit.hold_duty=duty;
      assert(c.enable(c.generation,1000)); c.write(1,true,1000); c.tick(1010);
      unsigned on=0, ticks=1000000/hz/100;
      for (unsigned t=0;t<ticks;++t) {c.pwmTick(t*100); on+=levels[1];}
      assert(on==ticks*duty/100);
      c.write(1,false,1011); c.pwmTick(0); assert(!levels[1]);
    }
  }
  // Explicit PULSE never switches to PWM hold.
  c=configured(); c.pins[1].limit.mode=Mode::Pwm; c.pins[1].limit.hold_duty=50;
  assert(c.enable(c.generation,1000)); c.pulse(1,20,1000); c.tick(1020); c.pwmTick(0);
  assert(!levels[1] && !c.pins[1].active && c.armed);

  // Paired winding: main switches off before hold is driven, release either
  // endpoint shuts down the entire assembly; direct hold activation is denied.
  c=configured(); c.pins[1].limit.mode=Mode::Dual; c.pins[1].limit.hold_pin=2;
  c.pins[1].limit.max_hold_ms=50; c.pins[2].limit.mode=Mode::Hold;
  assert(c.enable(c.generation,1000)); assert(!c.write(2,true,1000));
  assert(c.write(1,true,1000)); assert(levels[1] && levels[2]);
  c.tick(1010); assert(!levels[1] && !levels[2]);
  c.write(2,false,1011); assert(!levels[1] && levels[2] && !c.pins[1].active);
  assert(!c.write(1,true,1012)); assert(c.fault==Fault::Cooldown);
  c.fault=Fault::None; alive(c,1300); assert(c.enable(c.generation,1300));
  c.write(1,true,1300); c.tick(1310); c.tick(1360);
  assert(c.fault==Fault::MaxHold && !levels[1] && levels[2]);

  // Watchdog during a paired hold releases both electrical polarities.
  c.fault=Fault::None; alive(c,1600); assert(c.enable(c.generation,1600));
  c.write(1,true,1600); c.tick(1610); c.host_at=2100; c.tick(2100);
  assert(c.fault==Fault::LoopStalled && !levels[1] && levels[2]);
  // Active-low PWM has the same duty policy and always releases HIGH.
  c=configured(); c.pins[2].limit.mode=Mode::Pwm; c.pins[2].limit.hold_duty=50;
  assert(c.enable(c.generation,1000)); c.write(2,true,1000); c.tick(1010);
  c.pwmTick(0); assert(!levels[2]); c.pwmTick(5000); assert(levels[2]);
  c.disable(1011); c.pwmTick(0); assert(levels[2]);

  c=configured(); c.pins[1].limit.mode=Mode::Continuous; c.pins[1].limit.max_hold_ms=300;
  assert(c.enable(c.generation,1000)); c.write(1,true,1000); c.tick(1100);
  assert(levels[1]); c.write(1,true,1299); c.tick(1300);
  assert(!levels[1] && c.fault==Fault::MaxHold);

  c=configured(); assert(c.enable(c.generation,1000)); c.write(1,true,1000);
  auto token=c.generation; c.disable(1001);
  assert(!levels[1] && levels[2] && !c.armed && c.generation!=token);
  assert(!c.enable(token,1400));
  // Recovery re-arming does not replay an output or clear a safety fault.
  c=configured(); assert(c.enable(c.generation,1000)); c.write(1,true,1000);
  c.disable(1001); alive(c,4000);
  assert(c.enable(c.generation,4000));
  assert(!levels[1] && levels[2] && !c.pins[1].active);
  assert(c.write(1,true,4001));  // only a fresh action can energize
  c.trip(Fault::MaxHold,4002); alive(c,7000);
  assert(!c.enable(c.generation,7000) && !levels[1]);
  // Elapsed-time arithmetic works over millis() rollover.
  c=configured(UINT32_MAX-50); assert(c.enable(c.generation,UINT32_MAX-50));
  c.pulse(1,100,UINT32_MAX-50); c.tick(48); assert(levels[1]);
  c.tick(49); assert(!levels[1] && c.armed);
  c=configured(); assert(c.enable(c.generation,1000));
  assert(!c.write(1,true,2000) && !levels[1]);
}
