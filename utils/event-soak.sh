#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

python3 - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from statistics import mean
from uuid import uuid4

from pinballctl.bridge.state import (
    bridge_event_stats,
    commands_path,
    enqueue_command,
    read_state,
    responses_path,
    rpc_command,
)


def _bridge_pidfile() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    return Path(state_home) / "pinballctl" / "bridge.pid"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _bridge_pid_status():
    pidfile = _bridge_pidfile()
    if not pidfile.exists():
        return None, False, False
    try:
        pid = int(pidfile.read_text().strip())
    except Exception:
        return None, True, False
    return pid, True, _pid_alive(pid)


def _read_json(fp: Path):
    if not fp.exists():
        return None
    for _ in range(3):
        try:
            return json.loads(fp.read_text())
        except Exception:
            time.sleep(0.01)
    return None


def _queue_depth() -> int:
    data = _read_json(commands_path())
    if isinstance(data, list):
        return len(data)
    return 0


def _wait_queue_empty(timeout_s: float):
    start = time.monotonic()
    deadline = start + timeout_s
    while time.monotonic() < deadline:
        if _queue_depth() == 0:
            return True, (time.monotonic() - start)
        time.sleep(0.05)
    return False, (time.monotonic() - start)


def _send_wait(cmd: str, match_t: str, timeout_s: float, extra: dict | None = None):
    req_id = uuid4().hex
    payload = {"cmd": cmd, "reqId": req_id}
    if extra:
        payload.update(extra)
    start = time.monotonic()
    resp = rpc_command(payload, match_t=match_t, timeout_s=timeout_s)
    latency_s = time.monotonic() - start
    return req_id, resp, latency_s


def _enqueue_batch_rpc(items: list[dict], batch_id: str) -> bool:
    """Submit fire-and-forget commands via idempotent bridge RPC batch."""
    payload = {"cmd": "ENQUEUE_BATCH", "batchId": batch_id, "items": items}
    # Retry with same batch_id so daemon dedupe prevents duplicates.
    for _ in range(3):
        resp = rpc_command(payload, match_t="ENQUEUE_BATCH", timeout_s=4.0)
        if isinstance(resp, dict) and resp.get("ok"):
            return True
        time.sleep(0.05)
    return False


def _event_rx_total() -> int:
    metrics = bridge_event_stats(timeout_s=2.0)
    if isinstance(metrics, dict):
        try:
            return int(metrics.get("rx_evt_total", metrics.get("rx_total", 0)) or 0)
        except Exception:
            return 0
    st = read_state()
    metrics_file = st.get("event_metrics")
    if isinstance(metrics_file, dict):
        try:
            return int(metrics_file.get("rx_evt_total", metrics_file.get("rx_total", 0)) or 0)
        except Exception:
            return 0
    return 0


def _fmt_ms(sec: float) -> str:
    return f"{sec * 1000.0:.1f} ms"


def main() -> int:
    parser = argparse.ArgumentParser(description="Event throughput soak (Pi<->ESP event stubs).")
    parser.add_argument("--rpc-count", type=int, default=500, help="Pi->ESP EVENT request count")
    parser.add_argument("--rpc-timeout", type=float, default=2.0, help="Per-request timeout for EVENT_ACK")
    parser.add_argument("--rpc-delay", type=float, default=0.0, help="Delay between EVENT requests")
    parser.add_argument("--fire-count", type=int, default=5000, help="Pi->ESP fire-and-forget EVENT_FIRE count")
    parser.add_argument("--fire-batch", type=int, default=500, help="Batch size for EVENT_FIRE enqueue")
    parser.add_argument("--fire-timeout", type=float, default=90.0, help="Timeout waiting for EVENT_FIRE stats to reach target")
    parser.add_argument("--stream-count", type=int, default=5000, help="ESP->Pi EVT burst count")
    parser.add_argument("--stream-rate", type=int, default=500, help="ESP EVT target rateHz")
    parser.add_argument("--stream-timeout", type=float, default=30.0, help="Extra timeout budget in seconds")
    parser.add_argument("--stream-start-timeout", type=float, default=6.0, help="Timeout for EVT_STREAM_STATUS start ack")
    args = parser.parse_args()

    st = read_state()
    pid, pid_present, pid_alive = _bridge_pid_status()
    print("Event soak starting")
    print(f"- bridge port: {st.get('port')}")
    print(f"- bridge connected: {st.get('connected')}")
    print(f"- bridge firmware: {st.get('firmware')}")
    print(f"- bridge pidfile: {_bridge_pidfile()} ({'present' if pid_present else 'missing'})")
    print(f"- bridge pid: {pid if pid is not None else '-'} ({'alive' if pid_alive else 'not-alive'})")
    print(f"- queue depth (pre): {_queue_depth()}")
    print(f"- responses file: {responses_path()}")
    print("")
    if not pid_alive:
        print("ERROR: bridge is not running")
        return 2
    if not bool(st.get("connected")):
        print("ERROR: bridge is not connected")
        return 2

    # Phase 1: Pi -> ESP EVENT RPC throughput.
    # Warm-up: first request can occasionally hit startup queue jitter.
    _send_wait(
        "EVENT",
        "EVENT_ACK",
        args.rpc_timeout,
        extra={"name": "pi.stub.warmup", "seq": 0, "source": "pi.stub"},
    )

    rpc_ok = 0
    rpc_fail = 0
    rpc_lats: list[float] = []
    t0 = time.monotonic()
    print(f"[Phase 1] Pi->ESP EVENT x{args.rpc_count}")
    for i in range(1, args.rpc_count + 1):
        _, resp, lat = _send_wait(
            "EVENT",
            "EVENT_ACK",
            args.rpc_timeout,
            extra={"name": "pi.stub.event", "seq": i, "source": "pi.stub"},
        )
        if isinstance(resp, dict) and resp.get("t") == "EVENT_ACK" and resp.get("ok") is True:
            rpc_ok += 1
            rpc_lats.append(lat)
        else:
            rpc_fail += 1
            print(f"  FAIL i={i} lat={_fmt_ms(lat)} t={resp.get('t') if isinstance(resp, dict) else None}")
        if args.rpc_delay > 0:
            time.sleep(args.rpc_delay)
    rpc_elapsed = time.monotonic() - t0
    rpc_rate = (args.rpc_count / rpc_elapsed) if rpc_elapsed > 0 else 0.0
    print(f"  Result: ok={rpc_ok}/{args.rpc_count} fail={rpc_fail} elapsed={rpc_elapsed:.2f}s rate={rpc_rate:.2f} req/s")
    if rpc_lats:
        print(f"  Latency avg/max: {_fmt_ms(mean(rpc_lats))} / {_fmt_ms(max(rpc_lats))}")

    # Phase 1b: Pi -> ESP fire-and-forget throughput (no per-event response).
    print("")
    print(f"[Phase 1b] Pi->ESP EVENT_FIRE x{args.fire_count} batch={args.fire_batch}")
    _, reset_resp, reset_lat = _send_wait("EVENT_STATS_RESET", "EVENT_STATS", timeout_s=3.0)
    if not (isinstance(reset_resp, dict) and reset_resp.get("t") == "EVENT_STATS" and reset_resp.get("ok") is True):
        print(f"  FAIL stats reset lat={_fmt_ms(reset_lat)} payload={reset_resp}")
        return 1
    # Capture a stable zero baseline after reset to avoid prior-run spillover skew.
    baseline_fire = 0
    stable_zero = False
    for _ in range(8):
        _, baseline_resp, _ = _send_wait("EVENT_STATS", "EVENT_STATS", timeout_s=4.0)
        if isinstance(baseline_resp, dict) and baseline_resp.get("t") == "EVENT_STATS":
            try:
                baseline_fire = int(baseline_resp.get("in_fire", 0) or 0)
            except Exception:
                baseline_fire = 0
            if baseline_fire == 0:
                stable_zero = True
                break
        time.sleep(0.1)
    if not stable_zero and baseline_fire > 0:
        print(f"  WARN: EVENT_STATS baseline non-zero after reset ({baseline_fire}); using delta baseline")
    fire_start = time.monotonic()
    batched = []
    for i in range(1, args.fire_count + 1):
        batched.append({"cmd": "EVENT_FIRE", "name": "pi.stub.fire", "source": "pi.stub", "seq": i})
        if len(batched) >= max(1, args.fire_batch):
            bid = f"fire-{uuid4().hex}"
            if not _enqueue_batch_rpc(batched, bid):
                print(f"  FAIL enqueue batch (size={len(batched)})")
                return 1
            batched = []
    if batched:
        bid = f"fire-{uuid4().hex}"
        if not _enqueue_batch_rpc(batched, bid):
            print(f"  FAIL enqueue final batch (size={len(batched)})")
            return 1
    enqueue_elapsed = time.monotonic() - fire_start
    enqueue_rate = (args.fire_count / enqueue_elapsed) if enqueue_elapsed > 0 else 0.0

    # Wait for bridge command file queue to drain before polling stats.
    queue_budget = max(5.0, min(120.0, args.fire_timeout * 0.5))
    drained, drain_wait = _wait_queue_empty(queue_budget)
    if not drained:
        print(f"  WARN: command queue not empty after {drain_wait:.2f}s; stats may lag")
    else:
        print(f"  Queue drained in {drain_wait:.2f}s")

    # Serialize stats polling: use fewer requests with longer wait so stats
    # commands don't get buried behind their own retries.
    dynamic_fire_timeout = max(float(args.fire_timeout), (args.fire_count / 120.0) + 15.0)
    deadline = time.monotonic() + max(1.0, dynamic_fire_timeout)
    fire_seen = 0
    fire_stats = None
    while time.monotonic() < deadline:
        _, stats_resp, _ = _send_wait("EVENT_STATS", "EVENT_STATS", timeout_s=8.0)
        if isinstance(stats_resp, dict) and stats_resp.get("t") == "EVENT_STATS":
            fire_stats = stats_resp
            try:
                current_fire = int(stats_resp.get("in_fire", 0) or 0)
            except Exception:
                current_fire = baseline_fire
            fire_seen = max(0, current_fire - baseline_fire)
            if fire_seen >= args.fire_count:
                break
        time.sleep(0.2)
    fire_total_elapsed = time.monotonic() - fire_start
    fire_end_to_end_rate = (fire_seen / fire_total_elapsed) if fire_total_elapsed > 0 else 0.0
    fire_lost = max(0, args.fire_count - fire_seen)
    print(
        f"  Result: seen={fire_seen}/{args.fire_count} lost={fire_lost} "
        f"enqueue_rate={enqueue_rate:.2f} evt/s end_to_end_rate={fire_end_to_end_rate:.2f} evt/s "
        f"elapsed={fire_total_elapsed:.2f}s"
    )
    if not fire_stats:
        print("  WARN: no EVENT_STATS response received")

    # Phase 2: ESP -> Pi event stream throughput.
    print("")
    print(f"[Phase 2] ESP->Pi EVT stream count={args.stream_count} rateHz={args.stream_rate}")
    rx_before = _event_rx_total()
    start_req = uuid4().hex
    done_req = uuid4().hex
    t_start_rpc = time.monotonic()
    started = rpc_command(
        {
            "cmd": "EVT_STREAM_START",
            "reqId": start_req,
            "doneReqId": done_req,
            "count": int(args.stream_count),
            "rateHz": int(args.stream_rate),
            "name": "esp.stub.event",
            "source": "esp.stub",
        },
        match_t="EVT_STREAM_STATUS",
        timeout_s=max(1.0, args.stream_start_timeout),
    )
    start_lat = time.monotonic() - t_start_rpc
    started_ok = isinstance(started, dict) and started.get("t") == "EVT_STREAM_STATUS" and started.get("status") == "started"
    if not started_ok:
        # Under heavy queue pressure, the START status frame can be dropped while stream still runs.
        print(f"  WARN stream start ack missing lat={_fmt_ms(start_lat)} payload={started}; waiting for EVT_STREAM_DONE")
    expected_sec = (args.stream_count / max(1, args.stream_rate))
    done_timeout = expected_sec + max(1.0, args.stream_timeout)
    t_stream = time.monotonic()
    done = rpc_command({"cmd": "WAIT_REQ", "reqId": done_req}, match_t="EVT_STREAM_DONE", timeout_s=done_timeout)
    done_wait = time.monotonic() - t_stream
    stream_elapsed = time.monotonic() - t_stream
    rx_after = _event_rx_total()
    rx_delta = max(0, rx_after - rx_before)
    if not (isinstance(done, dict) and done.get("t") == "EVT_STREAM_DONE"):
        print(f"  FAIL stream done wait={done_wait:.2f}s payload={done}")
        return 1
    sent = int(done.get("sent", 0) or 0)
    dropped = int(done.get("dropped", 0) or 0)
    done_rate = (sent / stream_elapsed) if stream_elapsed > 0 else 0.0
    print(
        f"  Result: sent={sent} dropped={dropped} rx_delta={rx_delta} "
        f"elapsed={stream_elapsed:.2f}s rate={done_rate:.2f} evt/s"
    )
    if rx_delta < sent:
        print(f"  WARN: bridge observed fewer EVT messages than firmware sent ({rx_delta} < {sent})")

    total_fail = rpc_fail + (1 if fire_lost > 0 else 0) + (1 if (rx_delta < sent or dropped > 0) else 0)
    print("")
    print("=== Event Soak Report ===")
    print(f"RPC success: {rpc_ok}/{args.rpc_count}")
    print(f"Pi->ESP fire seen/lost: {fire_seen}/{fire_lost}")
    print(f"Stream sent/dropped: {sent}/{dropped}")
    print(f"Stream bridge rx delta: {rx_delta}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
PY
