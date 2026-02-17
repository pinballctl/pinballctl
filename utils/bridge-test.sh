#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

python3 - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from uuid import uuid4

from pinballctl.bridge.state import commands_path, enqueue_command, read_state, responses_path


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


def _read_json_file(fp: Path):
    if not fp.exists():
        return None
    for _ in range(3):
        try:
            return json.loads(fp.read_text())
        except Exception:
            time.sleep(0.01)
    return None


def _read_responses() -> dict:
    data = _read_json_file(responses_path())
    return data if isinstance(data, dict) else {}


def _queue_depth() -> int:
    data = _read_json_file(commands_path())
    if isinstance(data, list):
        return len(data)
    return 0


def _wait_for_response(req_id: str, timeout_s: float):
    start = time.monotonic()
    deadline = start + timeout_s
    while time.monotonic() < deadline:
        entry = _read_responses().get(req_id)
        if isinstance(entry, dict) and entry.get("done") is True:
            return entry.get("payload"), (time.monotonic() - start)
        time.sleep(0.03)
    return None, (time.monotonic() - start)


def _send_and_wait(cmd: str, match_t: str, timeout_s: float, extra: dict | None = None):
    req_id = uuid4().hex
    payload = {"cmd": cmd, "reqId": req_id, "match_t": match_t}
    if extra:
        payload.update(extra)
    enqueue_command(payload)
    response, latency_s = _wait_for_response(req_id, timeout_s)
    return req_id, response, latency_s


def _parse_stages(raw: str):
    stages = []
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Invalid stage '{part}'. Use count:delay format (example: 10:0.5)")
        count_s, delay_s = part.split(":", 1)
        count = int(count_s.strip())
        delay = float(delay_s.strip())
        if count <= 0 or delay < 0:
            raise ValueError(f"Invalid stage '{part}'. Count must be >0 and delay must be >=0")
        stages.append((count, delay))
    if not stages:
        raise ValueError("No valid stages provided")
    return stages


def _fmt_ms(seconds: float):
    return f"{seconds * 1000.0:.1f} ms"


@dataclass
class OpStats:
    total: int = 0
    ok: int = 0
    fail: int = 0
    latencies: list[float] = field(default_factory=list)
    first_fail_request: int | None = None
    failure_reasons: Counter = field(default_factory=Counter)

    def record(self, success: bool, latency_s: float, req_num: int, reason: str | None = None):
        self.total += 1
        if success:
            self.ok += 1
            self.latencies.append(latency_s)
            return
        self.fail += 1
        if self.first_fail_request is None:
            self.first_fail_request = req_num
        self.failure_reasons[reason or "unknown"] += 1


def _validate_echo(resp: dict | None):
    if not isinstance(resp, dict):
        return False, "timeout/no-response"
    if resp.get("t") != "ECHO":
        return False, f"unexpected-t:{resp.get('t')}"
    if resp.get("ok") is not True:
        return False, "echo-not-ok"
    return True, None


def _validate_fs_status(resp: dict | None):
    if not isinstance(resp, dict):
        return False, "timeout/no-response"
    if resp.get("t") != "FS_STATUS":
        return False, f"unexpected-t:{resp.get('t')}"
    return True, None


def _validate_fs_list(resp: dict | None):
    if not isinstance(resp, dict):
        return False, "timeout/no-response"
    if resp.get("t") != "FS_LIST":
        return False, f"unexpected-t:{resp.get('t')}"
    files = resp.get("files")
    if not isinstance(files, list):
        return False, "fs-list-no-files-array"
    return True, None


def main():
    parser = argparse.ArgumentParser(
        description="Bridge reliability ramp test (direct bridge queue/responses; no web UI)."
    )
    parser.add_argument(
        "--stages",
        default="10:1.0,20:0.5,40:0.2,80:0.1,120:0.05",
        help="Comma-separated stages as count:delay_seconds (default: %(default)s)",
    )
    parser.add_argument("--echo-timeout", type=float, default=4.0, help="ECHO timeout seconds")
    parser.add_argument("--fs-timeout", type=float, default=6.0, help="FS_STATUS/FS_LIST timeout seconds")
    parser.add_argument("--path", default="/", help="Path for FS_LIST (default: /)")
    parser.add_argument(
        "--mode",
        choices=("full", "echo"),
        default="full",
        help="Test mode: full (echo+fs) or echo-only (default: full)",
    )
    parser.add_argument("--echo-gate-cycles", type=int, default=5, help="Preflight echo-only cycles before full mode")
    parser.add_argument("--echo-gate-delay", type=float, default=0.25, help="Delay between preflight echo cycles")
    parser.add_argument("--continue-after-echo-gate-fail", action="store_true", help="In full mode, continue even if echo preflight fails")
    parser.add_argument("--stop-on-first-failure", action="store_true", help="Abort immediately on first request failure")
    parser.add_argument("--json-report", default="", help="Optional path to write JSON report")
    args = parser.parse_args()

    try:
        stages = _parse_stages(args.stages)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    state = read_state()
    bridge_pid, bridge_pidfile_present, bridge_pid_alive = _bridge_pid_status()
    print("Bridge test starting")
    print(f"- state file: {responses_path().parent / 'bridge_state.json'}")
    print(f"- bridge port: {state.get('port')}")
    print(f"- bridge connected: {state.get('connected')}")
    print(f"- bridge pidfile: {_bridge_pidfile()} ({'present' if bridge_pidfile_present else 'missing'})")
    print(f"- bridge pid: {bridge_pid if bridge_pid is not None else '-'} ({'alive' if bridge_pid_alive else 'not-alive'})")
    print(f"- bridge firmware: {state.get('firmware')}")
    print(f"- bridge chip: {state.get('chip')}")
    print(f"- queue depth (pre): {_queue_depth()}")
    print(f"- responses file: {responses_path()}")
    print(f"- stages: {', '.join([f'{c}x@{d:.3f}s' for c, d in stages])}")
    print("")

    if bridge_pidfile_present and not bridge_pid_alive:
        print("ERROR: bridge pidfile is stale (bridge process is not running).")
        print("Restart bridge, then re-run this test.")
        return 2

    tests = [("ECHO", "ECHO", args.echo_timeout, {}, _validate_echo)]
    if args.mode == "full":
        tests.extend([
            ("GET_FS_STATUS", "FS_STATUS", args.fs_timeout, {}, _validate_fs_status),
            ("FS_LIST", "FS_LIST", args.fs_timeout, {"path": args.path}, _validate_fs_list),
        ])
    stats = {name: OpStats() for name, *_ in tests}

    req_num = 0
    first_failure_req = None
    longest_success_streak = 0
    current_success_streak = 0
    stage_summaries = []
    overall_start = time.monotonic()

    if args.mode == "full" and args.echo_gate_cycles > 0:
        print(f"[Echo Gate] {args.echo_gate_cycles} cycles at {args.echo_gate_delay:.3f}s delay")
        gate_fail = 0
        for gate_i in range(1, args.echo_gate_cycles + 1):
            req_num += 1
            req_id, resp, latency_s = _send_and_wait("ECHO", "ECHO", args.echo_timeout)
            ok, reason = _validate_echo(resp)
            stats["ECHO"].record(ok, latency_s, req_num, reason)
            if ok:
                current_success_streak += 1
                if current_success_streak > longest_success_streak:
                    longest_success_streak = current_success_streak
            else:
                gate_fail += 1
                current_success_streak = 0
                if first_failure_req is None:
                    first_failure_req = req_num
                t_val = resp.get("t") if isinstance(resp, dict) else None
                print(
                    f"  FAIL req#{req_num} cycle={gate_i} cmd=ECHO reqId={req_id} "
                    f"lat={_fmt_ms(latency_s)} reason={reason} t={t_val}"
                )
                if args.stop_on_first_failure:
                    break
            if args.echo_gate_delay > 0:
                time.sleep(args.echo_gate_delay)
        gate_ok = args.echo_gate_cycles - gate_fail
        print(f"  Echo gate result: ok={gate_ok}/{args.echo_gate_cycles} fail={gate_fail}")
        if gate_fail > 0 and not args.continue_after_echo_gate_fail:
            print("  Echo gate failed; stopping before FS tests. Use --continue-after-echo-gate-fail to override.")
            elapsed_total = time.monotonic() - overall_start
            total_fail = sum(s.fail for s in stats.values())
            total_ok = sum(s.ok for s in stats.values())
            total_req = total_ok + total_fail
            success_pct = (100.0 * total_ok / total_req) if total_req else 0.0
            print("\n=== Bridge Test Report ===")
            print(f"Total requests: {total_req}")
            print(f"Successes: {total_ok}")
            print(f"Failures: {total_fail}")
            print(f"Success rate: {success_pct:.2f}%")
            print(f"Elapsed: {elapsed_total:.2f}s")
            return 1

    for stage_index, (count, delay_s) in enumerate(stages, start=1):
        stage_total = 0
        stage_fail = 0
        stage_start_req = req_num + 1
        stage_start = time.monotonic()

        print(f"[Stage {stage_index}] {count} cycles at {delay_s:.3f}s delay")
        for cycle in range(1, count + 1):
            for name, match_t, timeout_s, extra, validator in tests:
                req_num += 1
                stage_total += 1
                req_id, resp, latency_s = _send_and_wait(name, match_t, timeout_s, extra=extra)
                ok, reason = validator(resp)
                stats[name].record(ok, latency_s, req_num, reason)
                if ok:
                    current_success_streak += 1
                    if current_success_streak > longest_success_streak:
                        longest_success_streak = current_success_streak
                else:
                    stage_fail += 1
                    current_success_streak = 0
                    if first_failure_req is None:
                        first_failure_req = req_num
                    t_val = resp.get("t") if isinstance(resp, dict) else None
                    print(
                        f"  FAIL req#{req_num} cycle={cycle} cmd={name} reqId={req_id} "
                        f"lat={_fmt_ms(latency_s)} reason={reason} t={t_val}"
                    )
                    if args.stop_on_first_failure:
                        break
            if args.stop_on_first_failure and stage_fail > 0:
                break
            if delay_s > 0:
                time.sleep(delay_s)

        stage_elapsed = time.monotonic() - stage_start
        stage_end_req = req_num
        stage_ok = stage_total - stage_fail
        stage_rate = (stage_total / stage_elapsed) if stage_elapsed > 0 else 0.0
        stage_summaries.append(
            {
                "stage": stage_index,
                "cycles": count,
                "delay_s": delay_s,
                "request_start": stage_start_req,
                "request_end": stage_end_req,
                "total_requests": stage_total,
                "ok_requests": stage_ok,
                "fail_requests": stage_fail,
                "elapsed_s": stage_elapsed,
                "requests_per_s": stage_rate,
            }
        )
        print(
            f"  Stage result: ok={stage_ok}/{stage_total} fail={stage_fail} "
            f"elapsed={stage_elapsed:.2f}s rate={stage_rate:.2f} req/s"
        )
        if args.stop_on_first_failure and stage_fail > 0:
            break

    elapsed_total = time.monotonic() - overall_start
    total_fail = sum(s.fail for s in stats.values())
    total_ok = sum(s.ok for s in stats.values())
    total_req = total_ok + total_fail
    success_pct = (100.0 * total_ok / total_req) if total_req else 0.0

    print("\n=== Bridge Test Report ===")
    print(f"Total requests: {total_req}")
    print(f"Successes: {total_ok}")
    print(f"Failures: {total_fail}")
    print(f"Success rate: {success_pct:.2f}%")
    print(f"Elapsed: {elapsed_total:.2f}s")
    print(f"Average request rate: {(total_req / elapsed_total) if elapsed_total > 0 else 0.0:.2f} req/s")
    print(f"Longest success streak: {longest_success_streak} requests")
    print(f"Requests before first failure: {(first_failure_req - 1) if first_failure_req else total_req}")

    for name, _, _, _, _ in tests:
        st = stats[name]
        lat_avg = mean(st.latencies) if st.latencies else None
        lat_max = max(st.latencies) if st.latencies else None
        print(f"\n{name}:")
        print(f"- ok/fail: {st.ok}/{st.fail}")
        if lat_avg is not None:
            print(f"- latency avg/max: {_fmt_ms(lat_avg)} / {_fmt_ms(lat_max)}")
        else:
            print("- latency avg/max: n/a")
        print(f"- first failure request#: {st.first_fail_request if st.first_fail_request is not None else 'none'}")
        if st.failure_reasons:
            print("- top failure reasons:")
            for reason, cnt in st.failure_reasons.most_common(5):
                print(f"  - {reason}: {cnt}")

    print("\nStage summaries:")
    for ss in stage_summaries:
        print(
            f"- stage {ss['stage']}: req {ss['request_start']}..{ss['request_end']} "
            f"ok={ss['ok_requests']}/{ss['total_requests']} fail={ss['fail_requests']} "
            f"rate={ss['requests_per_s']:.2f} req/s"
        )

    report = {
        "totals": {
            "requests": total_req,
            "ok": total_ok,
            "fail": total_fail,
            "success_rate_pct": success_pct,
            "elapsed_s": elapsed_total,
            "avg_req_per_s": (total_req / elapsed_total) if elapsed_total > 0 else 0.0,
            "longest_success_streak_requests": longest_success_streak,
            "requests_before_first_failure": (first_failure_req - 1) if first_failure_req else total_req,
        },
        "bridge_state_start": state,
        "per_command": {
            name: {
                "total": stats[name].total,
                "ok": stats[name].ok,
                "fail": stats[name].fail,
                "first_fail_request": stats[name].first_fail_request,
                "latency_avg_ms": (mean(stats[name].latencies) * 1000.0) if stats[name].latencies else None,
                "latency_max_ms": (max(stats[name].latencies) * 1000.0) if stats[name].latencies else None,
                "failure_reasons": dict(stats[name].failure_reasons),
            }
            for name, _, _, _, _ in tests
        },
        "stages": stage_summaries,
        "args": {
            "stages": args.stages,
            "echo_timeout": args.echo_timeout,
            "fs_timeout": args.fs_timeout,
            "path": args.path,
            "stop_on_first_failure": args.stop_on_first_failure,
        },
    }

    if args.json_report:
        out_path = Path(args.json_report).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nJSON report written: {out_path}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
PY
