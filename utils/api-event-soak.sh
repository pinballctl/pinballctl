#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

python3 - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.client import HTTPConnection
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from pinballctl.bridge.state import bridge_event_stats
except Exception:  # pragma: no cover
    bridge_event_stats = None


@dataclass
class WorkerResult:
    sent: int = 0
    ok: int = 0
    fail: int = 0
    min_ms: float = math.inf
    max_ms: float = 0.0
    total_ms: float = 0.0
    latencies_ms: list[float] | None = None


class RateLimiter:
    def __init__(self, rate_per_s: float) -> None:
        self._rate = max(0.0, float(rate_per_s))
        self._lock = threading.Lock()
        self._next_at = time.perf_counter()

    def wait(self) -> None:
        if self._rate <= 0:
            return
        step = 1.0 / self._rate
        while True:
            with self._lock:
                now = time.perf_counter()
                if now >= self._next_at:
                    self._next_at = now + step
                    return
                sleep_for = self._next_at - now
            if sleep_for > 0:
                time.sleep(sleep_for)


def _http_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout_s: float,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body: bytes | None = None
    headers = {"Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError(
                f"401 Unauthorized for {path}. Provide auth via --username/--password, --cookie, or --auth-header."
            ) from exc
        raise
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed for {path}: {exc}") from exc


def _pick_default_event(base_url: str, timeout_s: float, extra_headers: dict[str, str] | None = None) -> str:
    try:
        reg = _http_json(base_url, "GET", "/api/events/registry", None, timeout_s, extra_headers=extra_headers)
        triggers = reg.get("triggers") if isinstance(reg, dict) else {}
        system = triggers.get("system") if isinstance(triggers, dict) else {}
        categories = system.get("categories") if isinstance(system, dict) else {}
        for cat in categories.values() if isinstance(categories, dict) else []:
            events = cat.get("events") if isinstance(cat, dict) else []
            for ev in events if isinstance(events, list) else []:
                if isinstance(ev, str) and ev.strip():
                    return ev.strip()
    except Exception:
        pass
    return "GAME_STARTED"


def _parse_params_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"--params-json is not valid JSON: {exc}")
    if not isinstance(parsed, dict):
        raise SystemExit("--params-json must be a JSON object")
    return parsed


def _cookie_from_login(base_url: str, username: str, password: str, timeout_s: float) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or not parsed.hostname or not parsed.port:
        raise RuntimeError("--base-url must include http://host:port")
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=timeout_s)
    try:
        form = urlencode({"username": username, "password": password, "next": "/"}).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "close",
        }
        conn.request("POST", "/login", body=form, headers=headers)
        resp = conn.getresponse()
        _ = resp.read()
        set_cookie_headers = [v for (k, v) in resp.getheaders() if k.lower() == "set-cookie"]
        if not set_cookie_headers:
            raise RuntimeError("login did not return Set-Cookie; auth may be disabled or credentials invalid")
        pairs: list[str] = []
        for raw in set_cookie_headers:
            first = (raw or "").split(";", 1)[0].strip()
            if first and "=" in first:
                pairs.append(first)
        if not pairs:
            raise RuntimeError("could not parse session cookie from login response")
        return "; ".join(pairs)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _bridge_stats_safe(timeout_s: float) -> dict[str, Any]:
    if bridge_event_stats is None:
        return {}
    try:
        data = bridge_event_stats(timeout_s=timeout_s)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _fire_worker(
    worker_idx: int,
    worker_count: int,
    total_count: int,
    parsed_url,
    fire_path: str,
    timeout_s: float,
    payload_base: dict[str, Any],
    extra_headers: dict[str, str],
    rate_limiter: RateLimiter | None,
    shared_counter: dict[str, int],
    counter_lock: threading.Lock,
    capture_latencies: bool,
) -> WorkerResult:
    result = WorkerResult(latencies_ms=[] if capture_latencies else None)
    conn: HTTPConnection | None = None
    try:
        conn = HTTPConnection(parsed_url.hostname, parsed_url.port, timeout=timeout_s)
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Connection": "keep-alive"}
        headers.update(extra_headers)
        for i in range(worker_idx, total_count, worker_count):
            if rate_limiter is not None:
                rate_limiter.wait()
            payload = dict(payload_base)
            # seq is only included when params already exist; avoids invalid params
            # for strict system events that don't accept arbitrary payloads.
            if payload.get("params"):
                payload["params"] = dict(payload["params"])
                payload["params"]["seq"] = i + 1
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            result.sent += 1
            ok = False
            last_err: Exception | None = None
            for _attempt in range(2):
                try:
                    t0 = time.perf_counter()
                    conn.request("POST", fire_path, body=body, headers=headers)
                    resp = conn.getresponse()
                    raw = resp.read().decode("utf-8", errors="replace")
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    if resp.status == 200:
                        ok = True
                        result.ok += 1
                        result.total_ms += dt_ms
                        if dt_ms < result.min_ms:
                            result.min_ms = dt_ms
                        if dt_ms > result.max_ms:
                            result.max_ms = dt_ms
                        if result.latencies_ms is not None:
                            result.latencies_ms.append(dt_ms)
                    else:
                        result.fail += 1
                    # Endpoint returns JSON with ok flag; treat non-ok as fail.
                    if ok:
                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, dict) and parsed.get("ok") is not True:
                                result.fail += 1
                                result.ok -= 1
                                ok = False
                        except Exception:
                            pass
                    break
                except Exception as exc:
                    last_err = exc
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = HTTPConnection(parsed_url.hostname, parsed_url.port, timeout=timeout_s)
            if not ok:
                result.fail += 1
                if last_err is not None and (i % max(100, worker_count) == 0):
                    print(f"[worker {worker_idx}] request failure at #{i + 1}: {last_err}")
            with counter_lock:
                shared_counter["done"] = shared_counter.get("done", 0) + 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return result


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(round((len(s) - 1) * p))
    return s[max(0, min(len(s) - 1, idx))]


def main() -> int:
    parser = argparse.ArgumentParser(description="API event fire soak test for /api/events/fire.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8888", help="Pinball CTL base URL")
    parser.add_argument("--count", type=int, default=5000, help="Total /api/events/fire requests")
    parser.add_argument("--concurrency", type=int, default=16, help="Concurrent client workers")
    parser.add_argument("--name", default="", help="Event name to fire (default: first registry system event)")
    parser.add_argument("--source", default="", help="Optional source field")
    parser.add_argument("--params-json", default="", help="Optional params JSON object")
    parser.add_argument("--username", default="admin", help="Login username for session auth (default: admin)")
    parser.add_argument("--password", default="password", help="Login password for session auth (default: password)")
    parser.add_argument("--cookie", default="", help="Raw Cookie header value (e.g. session=...)")
    parser.add_argument("--auth-header", default="", help="Raw Authorization header value (e.g. Bearer ...)")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-request timeout (seconds)")
    parser.add_argument(
        "--rate",
        type=float,
        default=500.0,
        help="Target send rate in req/s across all workers (0 = unlimited, default: 500)",
    )
    parser.add_argument("--drain-timeout", type=float, default=60.0, help="Wait for post-fire drain (seconds)")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Drain poll interval (seconds)")
    parser.add_argument("--no-latency-stats", action="store_true", help="Skip p50/p95 latency stats")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    if args.rate < 0:
        raise SystemExit("--rate must be >= 0")

    parsed_url = urlparse(args.base_url)
    if parsed_url.scheme != "http" or not parsed_url.hostname or not parsed_url.port:
        raise SystemExit("--base-url must include http://host:port")

    extra_headers: dict[str, str] = {}
    if args.auth_header.strip():
        extra_headers["Authorization"] = args.auth_header.strip()
    if args.cookie.strip():
        extra_headers["Cookie"] = args.cookie.strip()
    elif args.username.strip():
        cookie = _cookie_from_login(
            args.base_url,
            username=args.username.strip(),
            password=args.password,
            timeout_s=max(1.0, args.timeout),
        )
        extra_headers["Cookie"] = cookie
        print("  auth=login session cookie acquired")

    event_name = args.name.strip() or _pick_default_event(
        args.base_url,
        timeout_s=max(1.0, args.timeout),
        extra_headers=extra_headers,
    )
    event_source = args.source.strip()
    event_params = _parse_params_json(args.params_json)

    fire_payload: dict[str, Any] = {"name": event_name}
    if event_source:
        fire_payload["source"] = event_source
    if event_params:
        fire_payload["params"] = event_params

    print("API Event Soak starting")
    print(f"  target={args.base_url}/api/events/fire")
    print(f"  event={event_name} source={event_source or '—'} params={'yes' if event_params else 'no'}")
    print(f"  count={args.count} concurrency={args.concurrency}")
    print(f"  target rate={args.rate:.1f} req/s" if args.rate > 0 else "  target rate=unlimited")

    perf_before = _http_json(
        args.base_url,
        "GET",
        "/api/events/perf",
        None,
        timeout_s=max(1.0, args.timeout),
        extra_headers=extra_headers,
    )
    pf_before = perf_before.get("postFire") if isinstance(perf_before, dict) else {}
    sub_before = int((pf_before or {}).get("submitted", 0) or 0)
    comp_before = int((pf_before or {}).get("completed", 0) or 0)
    bridge_before = _bridge_stats_safe(timeout_s=0.6)
    bridge_rx_before = int(bridge_before.get("rx_evt_total", 0) or 0) if bridge_before else 0

    shared_counter = {"done": 0}
    counter_lock = threading.Lock()
    rate_limiter = RateLimiter(args.rate) if args.rate > 0 else None
    start_t = time.perf_counter()
    futures = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for worker_idx in range(args.concurrency):
            futures.append(
                pool.submit(
                    _fire_worker,
                    worker_idx,
                    args.concurrency,
                    args.count,
                    parsed_url,
                    "/api/events/fire",
                    args.timeout,
                    fire_payload,
                    extra_headers,
                    rate_limiter,
                    shared_counter,
                    counter_lock,
                    not args.no_latency_stats,
                )
            )

        last_print = 0.0
        while True:
            done = sum(1 for f in futures if f.done())
            now = time.perf_counter()
            if now - last_print >= 0.5:
                with counter_lock:
                    sent_done = int(shared_counter.get("done", 0))
                elapsed = max(0.001, now - start_t)
                print(
                    f"  progress: {sent_done}/{args.count} sent "
                    f"({sent_done / elapsed:.1f} req/s), workers_done={done}/{len(futures)}"
                )
                last_print = now
            if done >= len(futures):
                break
            time.sleep(0.05)

    elapsed_send = time.perf_counter() - start_t
    worker_results = [f.result() for f in as_completed(futures)]
    sent = sum(r.sent for r in worker_results)
    ok = sum(r.ok for r in worker_results)
    fail = sum(r.fail for r in worker_results)
    mean_ms = (sum(r.total_ms for r in worker_results) / ok) if ok > 0 else 0.0
    min_ms = min((r.min_ms for r in worker_results if r.min_ms < math.inf), default=0.0)
    max_ms = max((r.max_ms for r in worker_results), default=0.0)
    all_lat: list[float] = []
    if not args.no_latency_stats:
        for r in worker_results:
            if r.latencies_ms:
                all_lat.extend(r.latencies_ms)
    p50_ms = _pct(all_lat, 0.50) if all_lat else 0.0
    p95_ms = _pct(all_lat, 0.95) if all_lat else 0.0
    p99_ms = _pct(all_lat, 0.99) if all_lat else 0.0

    print(f"  send phase done in {elapsed_send:.2f}s ({sent / max(0.001, elapsed_send):.1f} req/s)")

    print("  waiting for post-fire drain...")
    drain_start = time.perf_counter()
    drained = False
    drained_mode = ""
    latest_pf: dict[str, Any] = {}
    drained_worker_totals: dict[int, int] = {}
    zero_streak = 0
    seen_activity = False
    best_sub_delta = 0
    while time.perf_counter() - drain_start <= args.drain_timeout:
        perf_now = _http_json(
            args.base_url,
            "GET",
            "/api/events/perf",
            None,
            timeout_s=max(1.0, args.timeout),
            extra_headers=extra_headers,
        )
        latest_pf = perf_now.get("postFire") if isinstance(perf_now, dict) else {}
        sub_now = int((latest_pf or {}).get("submitted", 0) or 0)
        comp_now = int((latest_pf or {}).get("completed", 0) or 0)
        sub_delta = max(0, sub_now - sub_before)
        comp_delta = max(0, comp_now - comp_before)
        pending_delta = max(0, sub_delta - comp_delta)
        inflight = int((latest_pf or {}).get("inflight", 0) or 0)
        queued = int((latest_pf or {}).get("queued", 0) or 0)
        if sub_delta > 0 or comp_delta > 0 or pending_delta > 0 or inflight > 0:
            seen_activity = True
        if sub_delta > best_sub_delta:
            best_sub_delta = sub_delta
        if sub_delta > 0 and comp_delta >= sub_delta and pending_delta == 0:
            # In multi-worker mode, /api/events/perf is per-process. Capture each
            # worker's fully drained subtotal so we can detect global completion.
            prior = drained_worker_totals.get(sub_delta, 0)
            if comp_delta > prior:
                drained_worker_totals[sub_delta] = comp_delta
        drained_known = sum(v for k, v in drained_worker_totals.items() if v >= k)
        if pending_delta == 0 and inflight == 0 and queued == 0:
            zero_streak += 1
        else:
            zero_streak = 0
        print(
            f"    perf: submitted={sub_delta}/{args.count} completed={comp_delta}/{args.count} "
            f"pending={pending_delta} inflight={inflight} queued={queued}"
        )
        if (sub_delta >= args.count and comp_delta >= args.count and pending_delta == 0) or drained_known >= args.count:
            drained = True
            drained_mode = "counted"
            break
        # Heuristic fallback: if sampled workers are consistently idle after activity,
        # treat as drained even when per-worker counters cannot be fully observed.
        if seen_activity and zero_streak >= 8:
            drained = True
            drained_mode = "idle_heuristic"
            break
        time.sleep(max(0.1, args.poll_interval))

    drain_elapsed = time.perf_counter() - drain_start
    bridge_after = _bridge_stats_safe(timeout_s=0.6)
    bridge_rx_after = int(bridge_after.get("rx_evt_total", 0) or 0) if bridge_after else 0

    print("")
    print("=== API Event Soak Report ===")
    print(f"requests sent:     {sent}")
    print(f"ack ok / fail:     {ok} / {fail}")
    print(f"send rate:         {sent / max(0.001, elapsed_send):.2f} req/s")
    print(f"ack latency ms:    min={min_ms:.2f} mean={mean_ms:.2f} max={max_ms:.2f}")
    if all_lat:
        print(f"ack percentiles:   p50={p50_ms:.2f} p95={p95_ms:.2f} p99={p99_ms:.2f}")
    print(f"drain completed:   {'yes' if drained else 'no'} (waited {drain_elapsed:.2f}s)")
    if drained and drained_mode == "idle_heuristic":
        print("drain method:      idle heuristic (sampled workers stayed at pending=0)")
    if drained_worker_totals and len(drained_worker_totals) > 1:
        parts = ", ".join(str(k) for k in sorted(drained_worker_totals.keys()))
        print(f"drain split:       multi-worker subtotals observed [{parts}]")
    elif best_sub_delta > 0 and best_sub_delta < args.count:
        print(f"drain split:       partial worker view observed (max submitted sample {best_sub_delta})")

    if latest_pf:
        sub_now = int(latest_pf.get("submitted", 0) or 0)
        comp_now = int(latest_pf.get("completed", 0) or 0)
        pending_now = max(0, sub_now - comp_now)
        print(f"api perf now:      submitted={sub_now} completed={comp_now} pending={pending_now}")

    if bridge_after:
        bridge_delta = max(0, bridge_rx_after - bridge_rx_before)
        print(
            "bridge evt rx:     "
            f"delta={bridge_delta} total={bridge_rx_after} "
            f"(worker_count={bridge_after.get('worker_count', '—')} "
            f"exec_pending={bridge_after.get('exec_pending', '—')} "
            f"exec_inflight={bridge_after.get('exec_inflight', '—')} "
            f"exec_queued={bridge_after.get('exec_queued', '—')})"
        )
    else:
        print("bridge evt rx:     unavailable (bridge RPC not reachable)")

    return 0 if fail == 0 and drained else 1


if __name__ == "__main__":
    raise SystemExit(main())
PY
