"""Bridge-owned event delivery accounting and bounded performance history."""
from collections import deque
import math
import time
from uuid import uuid4


class EventDelivery:
    def __init__(self, window=8, timeout=2.0):
        self.window = window
        self.timeout = timeout
        self.pending = {}
        self.contexts = {}
        self.sent = self.confirmed = self.dropped = self.timed_out = 0
        self.latencies = deque(maxlen=256)
        self.delivery_latencies = deque(maxlen=256)
        self.history = deque(maxlen=300)
        self.session = uuid4().hex
        self.previous = None
        self.overload_reason = None
        self.overload_count = 0
        self.rejected = 0
        self.disabled_confirmed = False
        self.disable_req_id = None
        self.queue_limit_s = 0.1
        self.confirmation_limit_s = 0.25
        self.coil_status = {}
        self.status_at = 0.0
        self.overload_at = 0.0
        self.healthy_since = None
        self.last_rejected_at = 0.0
        self.restore_armed = False
        self.lockout = None
        self.recent_overloads = deque()
        self.resume_req_id = None
        self.resume_at = 0.0
        self.recovered = False


    def check_overload(self, now, oldest_queued_at=None):
        if self.overload_reason:
            return False
        reason = None
        if oldest_queued_at is not None and now - oldest_queued_at > self.queue_limit_s:
            reason = 'event_queue_delay'
        elif any(now - started > self.confirmation_limit_s for started, _ in self.pending.values()):
            reason = 'event_confirmation_delay'
        if reason:
            self.overload_reason = reason
            self.overload_count += 1
            self.disabled_confirmed = False
            self.overload_at = now
            self.healthy_since = None
            self.restore_armed = self.coil_status.get('armed') is True and now - self.status_at < 1.0
            self.recent_overloads.append(now)
            while self.recent_overloads and now - self.recent_overloads[0] > 60:
                self.recent_overloads.popleft()
            self.lockout = 'repeated_overload' if len(self.recent_overloads) >= 3 else None
            return True
        return False

    def rejects(self, payload):
        if not self.overload_reason:
            return False
        command = str(payload.get('cmd') or '').upper()
        if command in {'DISABLE', 'COIL_RESET', 'COIL_CONFIG', 'BLOB_PUT', 'HELLO', 'SET_RULES', 'GET_HW', 'SET_ACCEL_CONFIG', 'MOUNT_FS', 'FS_MANIFEST_UPDATE'}:
            self.restore_armed = False

        # Release edges must still reach runtime rules; DISABLE and other
        # maintenance/status commands are never trapped behind activation work.
        params = payload.get('params')
        nested_type = params.get('eventType') if isinstance(params, dict) else None
        release = str(payload.get('eventType') or nested_type or '').upper() == 'RELEASED'
        rejected = command in {'ENABLE', 'EVENT_RESUME'} or (command == 'EVENT_FIRE' and not release)
        if rejected:
            self.rejected += 1
            self.last_rejected_at = time.monotonic()
        return rejected

    def observe_coil_status(self, payload, now=None):
        now = time.monotonic() if now is None else now
        if isinstance(payload.get('armed'), bool):
            self.coil_status = dict(payload)
            self.status_at = now
        if not self.overload_reason and payload.get('runtimePaused') is True:
            # A bridge restart must not silently resume a latched ESP pause.
            self.overload_reason = 'recovery_interrupted'
            self.lockout = 'runtime_paused_after_reconnect'
            self.overload_at = now
            self.restore_armed = False
            self.disabled_confirmed = False
        if not self.overload_reason:
            return
        if payload.get('armed') is True:
            self.disabled_confirmed = False
        elif (self.disable_req_id and payload.get('reqId') == self.disable_req_id
              and payload.get('armed') is False):
            self.disabled_confirmed = True
        if self.resume_req_id and payload.get('reqId') == self.resume_req_id:
            self.resume_req_id = None
            if (payload.get('ok') is True and payload.get('runtimePaused') is False
                    and payload.get('armed') is self.restore_armed and payload.get('fault') == 'none'):
                self.overload_reason = None
                self.recovered = True
                self.healthy_since = None
            else:
                self.lockout = 'recovery_failed'
                self.disabled_confirmed = False
        elif payload.get('fault') not in (None, 'none'):
            self.lockout = 'firmware_fault'

    def recovery_ready(self, now, queued=0, worker_pending=0, blocked=False):
        if not self.overload_reason:
            return False
        if self.resume_req_id:
            if now - self.resume_at > 1.0:
                self.resume_req_id = None
                self.lockout = 'recovery_unconfirmed'
                self.disabled_confirmed = False
            return False
        status = self.coil_status
        healthy = (not self.lockout and not blocked and not self.pending and not queued
                   and not worker_pending and self.disabled_confirmed
                   and status.get('runtimePaused') is True
                   and status.get('recoverySupported') is True
                   and status.get('fault') == 'none' and status.get('ready') is True
                   and now - self.status_at < 1.0
                   and now - self.last_rejected_at >= 1.0
                   and status.get('recoveryQuietMs', 0) >= 1000)
        if not healthy:
            self.healthy_since = None
            return False
        if self.healthy_since is None:
            self.healthy_since = now
        return now - self.overload_at >= 2.0 and now - self.healthy_since >= 1.0

    def reset_overload(self):
        # A diagnostic reset requests the same safe firmware handshake. It
        # never bypasses cooldown or restores power after a persistent fault.
        if self.pending or not self.disabled_confirmed:
            return False
        if self.overload_reason:
            if self.coil_status.get('recoverySupported') is not True:
                return False
            self.lockout = None
            self.restore_armed = False
            self.recent_overloads.clear()
        return True

    @staticmethod
    def tracks(payload):
        # Legacy accelerometer queries return metrics, not EVENT_FIRE echoes.
        return (str(payload.get('cmd') or '').upper() == 'EVENT_FIRE'
                and str(payload.get('name') or '').upper() not in ('ACCEL_STATUS_REQUEST', 'ACCEL_QUERY'))

    @staticmethod
    def supported_window(info):
        value = info.get('eventWindow')
        return max(1, min(16, value)) if type(value) is int else 8

    @staticmethod
    def key(payload):
        return (payload.get('seq'), payload.get('name'), payload.get('source') or '')

    def expire(self, now):
        for key, (started, queued_at) in list(self.pending.items()):
            if now - started >= self.timeout:
                del self.pending[key]
                self.timed_out += 1

    def available(self):
        return len(self.pending) < self.window

    def track(self, payload, now, queued_at=None, context=None):
        self.pending[self.key(payload)] = (now, now if queued_at is None else queued_at)
        if context is not None:
            self.contexts[self.key(payload)] = context
            # Retain context for late confirmations, with bounded memory.
            while len(self.contexts) > 256:
                del self.contexts[next(iter(self.contexts))]
        self.sent += 1

    def receive(self, payload, now):
        if payload.get('t') not in ('EVT', 'EVENT_DROP'):
            return
        context = self.contexts.pop(self.key(payload), None)
        timing = self.pending.pop(self.key(payload), None)
        if timing is None:
            return context
        started, queued_at = timing
        if payload['t'] == 'EVENT_DROP':
            self.dropped += 1
        else:
            self.confirmed += 1
            self.latencies.append((now - started) * 1000)
            self.delivery_latencies.append((now - queued_at) * 1000)
        return context

    def sample(self, now, rx, completed, worker_pending, queued, oldest_queued_at=None):
        if self.previous and now - self.previous[0] < 1:
            return
        previous = self.previous
        counters = (now, rx, completed, self.confirmed)
        self.previous = counters
        dt = now - previous[0] if previous else 0
        rate = lambda index: max(0, (counters[index] - previous[index]) / dt) if dt else 0
        values = sorted(self.latencies)
        p95 = values[max(0, math.ceil(len(values) * .95) - 1)] if values else None
        delivery_values = sorted(self.delivery_latencies)
        delivery_p95 = delivery_values[max(0, math.ceil(len(delivery_values) * .95) - 1)] if delivery_values else None
        self.history.append(dict(at=time.time(),
                                 delivery_p95_ms=delivery_p95,
                                 oldest_queued_ms=max(0, (now-oldest_queued_at)*1000) if oldest_queued_at is not None else 0,
                                 window=self.window, overload=self.overload_reason,
                                 overload_count=self.overload_count, rejected=self.rejected, rx_rate=rate(1), completed_rate=rate(2),
                                 confirmed_rate=rate(3), queued=queued, awaiting=len(self.pending),
                                 worker_pending=worker_pending, latency_p95_ms=p95,
                                 latency_samples=len(values), sent=self.sent, confirmed=self.confirmed,
                                 dropped=self.dropped, timed_out=self.timed_out))

    def snapshot(self):
        return dict(session=self.session, overload=self.overload_reason,
                    recovery_state=self.lockout or ("resuming" if self.resume_req_id else "cooldown" if self.overload_reason else "ready"),
                    disabled_confirmed=self.disabled_confirmed, rejected=self.rejected,
                    latest=self.history[-1] if self.history else None,
                    history=list(self.history), latency_scope='Last 256 confirmed host-to-ESP event round trips')
