import unittest
from pinballctl.bridge.performance import EventDelivery


class RecoveryTests(unittest.TestCase):
    def paused(self, armed=True):
        d = EventDelivery()
        d.observe_coil_status({'armed': armed}, 10)
        self.assertTrue(d.check_overload(10.2, 10))
        d.disable_req_id = 'pause'
        self.status(d, 10.3)
        return d

    def status(self, d, now, **changes):
        status = dict(armed=False, reqId='pause', recoverySupported=True,
                      runtimePaused=True, recoveryQuietMs=2000, fault='none', ready=True, generation=4)
        status.update(changes)
        d.observe_coil_status(status, now)

    def test_cooldown_quiet_period_and_matching_resume_confirmation(self):
        d = self.paused()
        self.status(d, 11.5)
        self.assertFalse(d.recovery_ready(11.5))
        self.status(d, 12.3)
        self.assertFalse(d.recovery_ready(12.3))
        self.status(d, 12.6)
        self.assertTrue(d.recovery_ready(12.6))
        self.assertTrue(d.restore_armed)
        d.resume_req_id = 'resume'
        self.status(d, 12.7, reqId='old', armed=True, runtimePaused=False, ok=True)
        self.assertIsNotNone(d.overload_reason)
        self.status(d, 12.8, reqId='resume', armed=True, runtimePaused=False, ok=True)
        self.assertIsNone(d.overload_reason)
        self.assertTrue(d.recovered)

    def test_busy_queues_and_activity_restart_quiet_period(self):
        d = self.paused(False)
        for now, args in [(12, {}), (12.5, {'queued': 1}), (13, {}), (13.5, {'worker_pending': 1}), (14, {})]:
            self.status(d, now)
            self.assertFalse(d.recovery_ready(now, **args))
        self.status(d, 15.1)
        self.assertTrue(d.recovery_ready(15.1))
        d.last_rejected_at = 15.1
        self.assertFalse(d.recovery_ready(15.2))
        self.assertFalse(d.restore_armed)

    def test_fault_disconnect_or_old_firmware_never_auto_rearms(self):
        for change in [{'fault': 'host_watchdog'}, {'recoverySupported': False}, {'runtimePaused': False}, {'ready': False}]:
            d = self.paused()
            self.status(d, 12, **change)
            self.assertFalse(d.recovery_ready(12))
            self.status(d, 14, **change)
            self.assertFalse(d.recovery_ready(14))
        d = self.paused()
        self.assertFalse(d.recovery_ready(20))  # stale status

    def test_explicit_disable_cancels_restoring_armed_state(self):
        d = self.paused()
        self.assertFalse(d.rejects({'cmd': 'DISABLE'}))
        self.assertFalse(d.restore_armed)
        self.assertTrue(d.rejects({'cmd': 'EVENT_RESUME'}))

    def test_resume_timeout_latches_fault_and_requires_disarm_again(self):
        d = self.paused()
        d.resume_req_id = 'lost'; d.resume_at = 12
        self.assertFalse(d.recovery_ready(13.1))
        self.assertEqual(d.lockout, 'recovery_unconfirmed')
        self.assertFalse(d.disabled_confirmed)

    def test_three_overloads_in_one_minute_latch(self):
        d = EventDelivery()
        for now in [10, 20, 30]:
            self.assertTrue(d.check_overload(now, now - .2))
            if now != 30:
                d.overload_reason = None
        self.assertEqual(d.lockout, 'repeated_overload')
        self.status(d, 35)
        self.assertFalse(d.recovery_ready(35))

    def test_pending_deliveries_and_minimum_cooldown(self):
        d = self.paused()
        e = dict(seq=1, name='a', source='b')
        d.track(e, 11)
        self.status(d, 12)
        self.assertFalse(d.recovery_ready(12))
        d.receive(dict(t='EVT', **e), 12)
        self.status(d, 12.1)
        self.assertFalse(d.recovery_ready(12.1))
        self.status(d, 13.2)
        self.assertTrue(d.recovery_ready(13.2))

    def test_reconnecting_to_paused_firmware_requires_explicit_diagnostic_reset(self):
        d = EventDelivery()
        self.status(d, 10)
        self.assertEqual(d.lockout, 'runtime_paused_after_reconnect')
        self.assertFalse(d.restore_armed)
        self.assertFalse(d.recovery_ready(12))
        d.disable_req_id = 'pause'
        self.status(d, 12)
        self.assertTrue(d.reset_overload())
        self.assertIsNone(d.lockout)
        self.assertIsNotNone(d.overload_reason)
        self.assertFalse(d.restore_armed)
