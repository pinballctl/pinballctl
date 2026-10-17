#!/usr/bin/env python3
"""Bounded diagnostic event load in either direction, with no matching rules.
Run with .venv/bin/python utils/bridge-load-test.py --output /tmp/bridge-load.json.
RTT probes measure host IPC + serial + ESP response, not physical switch latency.
"""
import threading
import argparse
import json
import platform
import math
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pinballctl.bridge.state import bridge_event_stats, read_state, rpc_command, enqueue_command
from pinballctl.rules.runtime import _rule_matches_event


def percentile(values, percent):
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)] if values else None


def probe():
    start = time.perf_counter()
    reply = rpc_command({'cmd': 'ECHO'}, 'ECHO', timeout_s=2)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed if isinstance(reply, dict) and reply.get('ok') else None


def latency_summary(values, failures):
    return dict(samples=len(values), timeouts=failures, p50_ms=percentile(values, 50),
                p95_ms=percentile(values, 95), p99_ms=percentile(values, 99), max_ms=max(values, default=None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['stream', 'fire'], default='stream')
    parser.add_argument('--rates', default='50,200,500,1000')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rates = [int(v) for v in args.rates.split(',')]
    if not 1 <= args.seconds <= 30 or not rates or any(not 1 <= r <= 2000 for r in rates):
        parser.error('Use rates 1..2000 and duration 1..30 seconds')
    name = 'diagnostic.bridge.' + uuid4().hex[:12]
    source = 'diagnostic.bridge'
    rules = json.loads((ROOT / 'src/instance/rules/rules.json').read_text())
    if any(_rule_matches_event(rule, name, source, {}) for rule in rules):
        raise RuntimeError('Diagnostic event matches a configured rule; refusing load test')
    state = read_state()
    if state.get('blob_status', {}).get('state') in ('queued', 'begin'):
        raise RuntimeError('A file sync is active; finish it before testing')
    baseline = [probe() for _ in range(20)]
    if any(value is None for value in baseline):
        raise RuntimeError('Baseline probes failed; no load started')
    from pinballctl.bridge.daemon import _current_log_level
    report = dict(firmware=state.get('firmware'), port=state.get('port'), event=name,
                  host=platform.platform(), python=sys.version.split()[0], logging=_current_log_level(),
                  scope='ESP synthetic events -> bridge workers, with host-to-ESP ECHO probes',
                  baseline=latency_summary(baseline, 0), stages=[])
    print('Baseline:', json.dumps(report['baseline']), flush=True)
    if args.mode == 'fire':
        return fire_test(args, rates, name, source, report)
    for rate in rates:
        before = bridge_event_stats()
        if not before or before.get('exec_pending', 0):
            raise RuntimeError('Bridge metrics unavailable or workers already busy')
        count = int(rate * args.seconds)
        latencies, failures, peak = [], 0, 0
        start = time.perf_counter()
        stopped = None
        try:
            reply = rpc_command({'cmd': 'EVT_STREAM_START', 'count': count, 'rateHz': rate,
                                 'name': name, 'source': source}, 'EVT_STREAM_STATUS', timeout_s=2)
            if not reply or reply.get('status') != 'started':
                raise RuntimeError('Stream did not confirm start')
            while time.perf_counter() - start < args.seconds:
                value = probe()
                if value is None:
                    failures += 1
                else:
                    latencies.append(value)
                metrics = bridge_event_stats()
                if not metrics:
                    raise RuntimeError('Lost bridge metrics during test')
                peak = max(peak, metrics.get('exec_pending', 0))
                if peak > 500 or failures >= 2:
                    break
                time.sleep(.15)
        finally:
            stopped = rpc_command({'cmd': 'EVT_STREAM_STOP'}, 'EVT_STREAM_STATUS', timeout_s=3)
        elapsed = time.perf_counter() - start
        if not stopped or stopped.get('status') != 'stopped':
            raise RuntimeError('Stream stop not confirmed; finite stream will expire at its configured count')
        drain_start = time.perf_counter()
        after = bridge_event_stats()
        while after and after.get('exec_pending', 0) and time.perf_counter() - drain_start < 10:
            time.sleep(.1)
            after = bridge_event_stats()
        if not after:
            raise RuntimeError('Final bridge metrics unavailable')
        received = after['rx_evt_total'] - before['rx_evt_total']
        completed = after['exec_completed'] - before['exec_completed']
        row = dict(target_eps=rate, requested=count, elapsed_s=elapsed,
                   esp_sent=stopped.get('sent'), esp_dropped=stopped.get('dropped'),
                   bridge_received=received, worker_completed=completed,
                   observed_eps=received / elapsed, peak_pending=peak,
                   pending_after=after.get('exec_pending'), drain_s=time.perf_counter()-drain_start,
                   latency=latency_summary(latencies, failures))
        report['stages'].append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if failures or peak > 500 or after.get('exec_pending'):
            print('Stopped escalation because latency or backlog crossed the test guard.', flush=True)
            break
        time.sleep(.5)
    recovery = [probe() for _ in range(10)]
    report['recovery'] = latency_summary([v for v in recovery if v is not None], sum(v is None for v in recovery))
    args.output.write_text(json.dumps(report, indent=2)+'\n')


def fire_test(args, rates, name, source, report):
    report['scope'] = 'Host command IPC -> EVENT_FIRE -> ESP rules lookup -> EVT -> bridge workers'
    for rate in rates:
        perf_before = rpc_command({'cmd': 'BRIDGE_PERF'}, 'BRIDGE_PERF', timeout_s=2) or {}
        if perf_before.get('overload'):
            raise RuntimeError('Bridge overload is latched; reset it explicitly before testing')
        before = bridge_event_stats()
        esp_before = rpc_command({'cmd': 'EVENT_STATS'}, 'EVENT_STATS', timeout_s=2)
        if not before or not esp_before or before.get('exec_pending', 0):
            raise RuntimeError('Missing counters or pre-existing backlog')
        stop = threading.Event()
        sent, errors = [], []
        start = time.perf_counter()
        def producer():
            for i in range(int(rate * args.seconds)):
                if stop.wait(max(0, start + i/rate - time.perf_counter())):
                    return
                try:
                    enqueue_command({'cmd': 'EVENT_FIRE', 'name': name, 'source': source}, wait_for_startup=False)
                    sent.append(time.perf_counter())
                except Exception as exc:
                    errors.append(str(exc)); return
        thread = threading.Thread(target=producer)
        thread.start()
        values, failures, peak = [], 0, 0
        try:
            while thread.is_alive():
                value = probe()
                if value is None: failures += 1
                else: values.append(value)
                metrics = bridge_event_stats()
                peak = max(peak, metrics.get('exec_pending', 0))
                perf = rpc_command({'cmd': 'BRIDGE_PERF'}, 'BRIDGE_PERF', timeout_s=2) or {}
                if failures or peak > 500 or not metrics or perf.get('overload'):
                    break
                time.sleep(.15)
        finally:
            stop.set()
            thread.join(timeout=3)
        drain_start = time.perf_counter()
        after = bridge_event_stats()
        while time.perf_counter() - drain_start < 30:
            perf = rpc_command({'cmd': 'BRIDGE_PERF'}, 'BRIDGE_PERF', timeout_s=2) or {}
            rejected = perf.get('rejected', 0) - perf_before.get('rejected', 0)
            if after and after.get('exec_completed', 0) - before['exec_completed'] + rejected >= len(sent) and not after.get('exec_pending'):
                break
            time.sleep(.1)
            after = bridge_event_stats()
        esp_after = rpc_command({'cmd': 'EVENT_STATS'}, 'EVENT_STATS', timeout_s=3)
        if not esp_after or not after:
            raise RuntimeError('Final counters unavailable')
        delivery = rpc_command({'cmd': 'BRIDGE_PERF'}, 'BRIDGE_PERF', timeout_s=2) or {}
        latest = delivery.get('latest') or {}
        row = dict(overload=delivery.get('overload'), rejected_by_bridge=delivery.get('rejected', 0)-perf_before.get('rejected', 0),
                   sampled_queue=latest.get('queued'), sampled_awaiting=latest.get('awaiting'),
                   sampled_at=latest.get('at'),
                   target_eps=rate, submitted=len(sent), send_errors=errors,
                   elapsed_s=time.perf_counter()-start, drain_s=time.perf_counter()-drain_start,
                   esp_received=esp_after['in_fire']-esp_before['in_fire'],
                   esp_stale_drops=esp_after['in_stale_drop']-esp_before['in_stale_drop'],
                   bridge_received=after['rx_evt_total']-before['rx_evt_total'],
                   worker_completed=after['exec_completed']-before['exec_completed'],
                   peak_pending=peak, pending_after=after['exec_pending'],
                   latency=latency_summary(values, failures))
        report['stages'].append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if row['overload'] or failures or errors or after['exec_pending'] or row['worker_completed'] < len(sent):
            print('Stopped escalation after overload, an incomplete drain, send error, or timeout.', flush=True)
            break
        time.sleep(.5)
    recovery = [probe() for _ in range(10)]
    report['recovery'] = latency_summary([v for v in recovery if v is not None], sum(v is None for v in recovery))
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
