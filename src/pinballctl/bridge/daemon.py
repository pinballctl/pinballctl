"""Minimal serial daemon that forwards ESP32 messages into Flask handlers."""

import sys, json, time, os, struct, zlib, hashlib, socket, selectors
import fcntl
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import serial
from .events import handle_event
from .state import (
    write_state,
    commands_path,
    write_hardware_snapshot,
    read_state,
    responses_path,
    command_socket_path,
    rpc_socket_path,
)
from pinballctl.events import EventContext, get_bus, get_event_manager
from pinballctl.events.audit_log import append_event_log
from pinballctl.log_maintenance import rotate_if_needed, prune_archives
from pinballctl.rules.runtime import apply_rules_for_event
from pinballctl.scoring.runtime import ensure_scoring_bus_worker
from pinballctl.audio.runtime import ensure_audio_bus_worker

def _now_iso():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def _log_ts():
    """Compact UTC timestamp for bridge log lines."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _log_err(msg):
    line = f"[bridge {_log_ts()}] {msg}"
    if not line.endswith("\n"):
        line += "\n"
    sys.stderr.write(line)
    sys.stderr.flush()

def _log(msg):
    """Always log (stderr) a notable bridge event."""
    line = f"[bridge {_log_ts()}] {msg}"
    if not line.endswith("\n"):
        line += "\n"
    sys.stderr.write(line)
    sys.stderr.flush()

def _log_in(msg: dict):
    """Emit a single inbound log line to stdout or stderr (no duplicates)."""
    try:
        # LOG_LEVEL behavior:
        # - INFO/Normal: only key status frames.
        # - DEBUG: detailed bridge traffic.
        # - VERBOSE: full traffic including event flood.
        t = msg.get("t") if isinstance(msg, dict) else None
        lvl = (_current_log_level() or "").upper()
        if lvl not in {"DEBUG", "VERBOSE"}:
            important = {"INFO", "FS_STATUS", "MAP_APPLY", "MANIFEST", "TIME", "REBOOT"}
            if t not in important:
                return
        if t in ("EVT", "EVENT", "EVENT_ACK", "EVT_STREAM_STATUS", "EVT_STREAM_DONE"):
            if lvl != "VERBOSE":
                return
    except Exception:
        pass
    line = f"RX: {json.dumps(msg)}"
    if os.environ.get("PINBALLCTL_BRIDGE_STDOUT") == "1":
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    else:
        _log(line)

def _log_in_text(text: str):
    """Emit a single inbound log line for non-JSON payloads."""
    # Raw text RX is verbose-only.
    lvl = (_current_log_level() or "").upper()
    if lvl != "VERBOSE":
        return
    line = f"RX: {text}"
    if os.environ.get("PINBALLCTL_BRIDGE_STDOUT") == "1":
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    else:
        _log(line)


def _parse_info_state_fields(msg: dict) -> dict:
    """Normalize INFO payload fields into bridge-state keys."""
    if not isinstance(msg, dict):
        return {}
    fw = msg.get("fw") or msg.get("version")
    chip = msg.get("chip") or msg.get("chip_model")
    profile = msg.get("profile")
    chip_model = msg.get("chipModel") or msg.get("chip_model")
    chip_revision = msg.get("chipRev") if msg.get("chipRev") is not None else msg.get("chip_revision")
    chip_cores = msg.get("chipCores") if msg.get("chipCores") is not None else msg.get("chip_cores")
    controller = msg.get("controller") or msg.get("controller_id")
    proto = msg.get("proto")
    out = {}
    if fw is not None:
        out["firmware"] = str(fw)
    if chip is not None:
        out["chip"] = str(chip)
    if profile is not None:
        out["profile"] = str(profile)
    if chip_model is not None:
        out["chip_model"] = str(chip_model)
    if chip_revision is not None:
        try:
            out["chip_revision"] = int(chip_revision)
        except Exception:
            pass
    if chip_cores is not None:
        try:
            out["chip_cores"] = int(chip_cores)
        except Exception:
            pass
    if controller is not None:
        out["controller"] = str(controller)
    if proto is not None:
        try:
            out["proto"] = int(proto)
        except Exception:
            pass
    return out


_raw_log_path = None
_raw_log_last_maint = 0.0
_bridge_lock_fd = None


def _raw_log_write(kind: str, payload) -> None:
    """Write inbound raw serial payloads/errors to esp-raw.log."""
    global _raw_log_last_maint  # noqa: PLW0603
    path = _raw_log_path
    if path is None:
        return
    try:
        if isinstance(payload, (bytes, bytearray)):
            text = payload.decode("utf-8", errors="replace")
        else:
            text = str(payload)
        line = f"[bridge {_log_ts()}] {kind}: {text}"
        if not line.endswith("\n"):
            line += "\n"
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
        now = time.time()
        if now - _raw_log_last_maint >= 5.0:
            rotate_if_needed("espraw", path)
            prune_archives("espraw")
            _raw_log_last_maint = now
    except Exception:
        pass


def _bridge_lock_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "pinballctl" / "bridge.lock"


def _acquire_bridge_lock(port: str) -> bool:
    """Acquire a process lock so only one bridge instance runs at a time."""
    global _bridge_lock_fd  # noqa: PLW0603
    try:
        p = _bridge_lock_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(p), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = ""
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    holder = f.read().strip()
            except Exception:
                holder = ""
            os.close(fd)
            if holder:
                _log_err(f"bridge lock busy ({p}); another bridge appears active: {holder}")
            else:
                _log_err(f"bridge lock busy ({p}); another bridge appears active")
            return False
        os.ftruncate(fd, 0)
        os.write(fd, f"pid={os.getpid()} port={port} started={_now_iso()}\n".encode("utf-8"))
        _bridge_lock_fd = fd
        return True
    except Exception as e:
        _log_err(f"failed to acquire bridge lock: {e}")
        return False


def _release_bridge_lock() -> None:
    global _bridge_lock_fd  # noqa: PLW0603
    fd = _bridge_lock_fd
    _bridge_lock_fd = None
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        os.close(fd)
    except Exception:
        pass

_cached_level = None
_cached_level_mtime = None

def _current_log_level():
    """Return current log level, reloading from instance settings file when it changes."""
    global _cached_level, _cached_level_mtime  # noqa: PLW0603
    lvl = os.environ.get("PINBALLCTL_LOG_LEVEL")
    try:
        # Canonical settings path: instance/settings/settings.json.
        # commands_path is now instance/bridge/bridge_commands.json
        instance_dir = commands_path().parent.parent
        settings_fp = instance_dir / "settings" / "settings.json"
        # Legacy fallback for older installs.
        if not settings_fp.exists():
            settings_fp = instance_dir / "settings.json"
        st = settings_fp.stat()
        if _cached_level_mtime != st.st_mtime:
            _cached_level_mtime = st.st_mtime
            try:
                data = json.loads(settings_fp.read_text())
                lvl = data.get("LOG_LEVEL", lvl)
                _cached_level = lvl
            except Exception:
                pass
        elif _cached_level is not None:
            lvl = _cached_level
    except Exception:
        pass
    return lvl

def _debug(msg):
    """Emit a log line when PINBALLCTL_LOG_LEVEL=DEBUG/VERBOSE."""
    try:
        lvl = _current_log_level()
        if lvl and lvl.upper() in {"DEBUG", "VERBOSE"}:
            sys.stderr.write(f"[bridge {_log_ts()}] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _verbose(msg):
    """Emit a log line only when PINBALLCTL_LOG_LEVEL=VERBOSE."""
    try:
        lvl = _current_log_level()
        if lvl and lvl.upper() == "VERBOSE":
            _log(msg)
    except Exception:
        pass

def _sha256_file(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _fmt_raw(raw) -> str:
    """Format raw bytes as clean JSON text when possible."""
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8", errors="replace").strip()
    return str(raw)

def _esp_port_candidates(preferred: str | None = None) -> list[str]:
    """Best-effort ESP USB serial candidates, preferred path first when present."""
    candidates = []
    if preferred:
        candidates.append(preferred)
    try:
        from serial.tools import list_ports
        known_usb_ids = {
            (0x10C4, 0xEA60), (0x1A86, 0x7523), (0x1A86, 0x55D4),
            (0x0403, 0x6001), (0x303A, 0x1001), (0x303A, 0x4001), (0x303A, 0x4002),
        }
        for p in list_ports.comports():
            dev = p.device or ""
            if not dev:
                continue
            vid_pid_ok = p.vid is not None and p.pid is not None and (p.vid, p.pid) in known_usb_ids
            path_ok = any(x in dev for x in ("/dev/ttyUSB", "/dev/ttyACM", "/dev/cu.usb", "/dev/cu.SLAB_USB"))
            desc = " ".join(filter(None, [p.manufacturer, p.product, p.description])).lower()
            desc_ok = any(x in desc for x in ("espressif", "cp210", "ch340", "ch910", "ftdi", "silicon labs", "usb"))
            if vid_pid_ok or path_ok or desc_ok:
                candidates.append(dev)
    except Exception:
        pass
    out = []
    seen = set()
    for dev in candidates:
        if dev in seen:
            continue
        seen.add(dev)
        out.append(dev)
    return out

def _drain_info(ser, port, timeout_sec=3.0):
    """Length-prefixed drain for INFO/STATE during startup."""
    end = time.time() + timeout_sec
    got_info = False
    saw_v2 = False
    while time.time() < end:
        try:
            raw = _read_frame(ser)
        except ValueError as e:
            _log_err(f"drain frame error: {e}")
            _raw_log_write("DRAIN_FRAME_ERROR", str(e))
            break
        except Exception as e:
            _log_err(f"drain error: {e}")
            _raw_log_write("DRAIN_ERROR", str(e))
            break
        if not raw:
            time.sleep(0.005)
            continue
        typed, frame_type, payload = _decode_frame(raw)
        if typed:
            saw_v2 = True
        if frame_type == 3:
            try:
                raw_txt = payload.decode("utf-8", errors="replace").strip()
            except Exception:
                raw_txt = None
            if raw_txt:
                _raw_log_write("RX_TEXT", raw_txt)
                _log_in_text(raw_txt)
            continue
        raw_txt = None
        try:
            raw_txt = payload.decode("utf-8", errors="replace").strip()
            if raw_txt:
                _raw_log_write("RX_JSON", raw_txt)
            msg = json.loads(raw_txt)
            _log_in(msg)
            if msg.get("t") == "INFO" and msg.get("proto") == 2:
                use_v2 = True
            if msg.get("t") == "INFO" and msg.get("proto") == 2:
                saw_v2 = True
            info_fields = _parse_info_state_fields(msg)
            if info_fields:
                write_state(port=port, connected=True, **info_fields)
                got_info = True
            if msg.get("t") == "TIME":
                ts = msg.get("ts")
                status = msg.get("status")
                iso = None
                try:
                    if ts is not None:
                        iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
                except Exception:
                    iso = None
                write_state(
                    port=port,
                    time_value=iso or (str(ts) if ts is not None else None),
                    time_in_sync=(status == "ok"),
                )
                got_info = True
            if msg.get("t") in ("HW", "SCAN"):
                payload = {
                    "controller": msg.get("controller"),
                    "pins": msg.get("pins", []),
                    "reloadedAt": _now_iso(),
                    "source": "esp",
                    "usingDefaults": False,
                }
                write_hardware_snapshot(payload, append=bool(msg.get("append")))
                got_info = True
            # Keep raw RX only; omit parsed JSON to reduce log noise.
        except Exception:
            if raw_txt:
                _raw_log_write("DRAIN_PARSE_FALLBACK", raw_txt)
                _log_in_text(raw_txt)
    if not got_info:
        _debug("No INFO received during drain")
    return got_info, saw_v2

def _send_cmd(ser, payload: dict, use_v2: bool = False):
    """Send a JSON command to ESP (framed JSON)."""
    try:
        send_payload = payload
        body = json.dumps(send_payload, separators=(",", ":")).encode("utf-8")
        if use_v2:
            data = struct.pack(">I", len(body) + 1) + bytes([1]) + body
        else:
            data = struct.pack(">I", len(body)) + body
        view = memoryview(data)
        total = 0
        while total < len(data):
            wrote = ser.write(view[total:])
            if wrote is None:
                wrote = 0
            if wrote <= 0:
                raise RuntimeError(f"short write sending cmd {send_payload.get('cmd')}")
            total += int(wrote)
        ser.flush()
        lvl = (_current_log_level() or "").upper()
        if lvl in {"DEBUG", "VERBOSE"}:
            cmd_name = str(send_payload.get("cmd") or "").upper()
            event_cmds = {"EVENT", "EVENT_FIRE", "EVENT_STATS", "EVENT_STATS_RESET", "EVT_STREAM_START", "EVT_STREAM_STOP"}
            if cmd_name in event_cmds and lvl != "VERBOSE":
                pass
            else:
                _log(f"TX: {json.dumps(send_payload)}")
    except Exception as e:
        _log_err(f"failed to send cmd {payload}: {e}")


def _next_event_fire_seq(last_seq: int) -> int:
    now_ms = int(time.time() * 1000) & 0xFFFFFFFF
    if now_ms <= 0:
        now_ms = 1
    if now_ms <= int(last_seq or 0):
        now_ms = int(last_seq or 0) + 1
        if now_ms > 0xFFFFFFFF:
            now_ms = 1
    return int(now_ms)

def _bridge_req_id() -> str:
    return uuid4().hex

def _send_raw_frame(ser, data: bytes, use_v2: bool = False, frame_type: int = 2):
    """Send a raw framed payload (length-prefixed binary)."""
    if use_v2:
        header = struct.pack(">I", len(data) + 1)
        packet = header + bytes([frame_type]) + data
    else:
        header = struct.pack(">I", len(data))
        packet = header + data
    view = memoryview(packet)
    total = 0
    while total < len(packet):
        wrote = ser.write(view[total:])
        if wrote is None:
            wrote = 0
        if wrote <= 0:
            raise RuntimeError(f"short write sending raw frame ({len(data)} bytes payload)")
        total += int(wrote)
    ser.flush()

def _decode_frame(raw: bytes) -> tuple[bool, int, bytes]:
    if not raw:
        return False, 0, b""
    first = raw[0]
    if first in (1, 2, 3):
        if first == 1 and len(raw) > 1 and raw[1:2] not in (b"{",):
            return False, 1, raw
        return True, first, raw[1:]
    return False, 1, raw

def _wait_for_json(ser, timeout_sec: float, match_fn=None):
    """Read framed payloads until JSON matches (or timeout)."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            raw = _read_frame(ser)
        except Exception as e:
            _log_err(f"wait_for_json read error: {e}")
            _raw_log_write("WAIT_JSON_READ_ERROR", str(e))
            time.sleep(0.05)
            continue
        if not raw:
            time.sleep(0.05)
            continue
        typed, frame_type, payload = _decode_frame(raw)
        if frame_type == 3:
            _raw_log_write("RX_TEXT", _fmt_raw(payload))
            _log_in_text(_fmt_raw(payload))
            continue
        if frame_type == 2:
            continue
        try:
            raw_txt = payload.decode("utf-8", errors="replace").strip()
            if raw_txt:
                _raw_log_write("RX_JSON", raw_txt)
            msg = json.loads(raw_txt)
        except Exception:
            _raw_log_write("WAIT_JSON_PARSE_FALLBACK", _fmt_raw(payload))
            _log_in_text(_fmt_raw(payload))
            continue
        _log_in(msg)
        if match_fn is None or match_fn(msg):
            return msg
    return None

def _crc32_file(path: str, chunk_size: int = 4096) -> tuple[int, int]:
    """Return (size, crc32) for a file path."""
    size = 0
    crc = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
    return size, crc & 0xFFFFFFFF


def _crc32_bytes(data: bytes) -> int:
    """Return crc32 for an in-memory payload."""
    return zlib.crc32(data) & 0xFFFFFFFF

def _handle_blob_put(ser, payload: dict):
    """Deprecated: blob uploads are now handled in the main loop state machine."""
    _log_err("BLOB_PUT handler invoked outside main loop")
    return
def _read_frame(
    ser,
    body_timeout: float = 3.0,
    header_timeout: float = 1.0,
    idle_timeout: float = 0.005,
):
    """Read a single length-prefixed frame; return bytes or None on timeout."""
    hdr = b""
    discarded = bytearray()

    def _flush_discarded(tag: str = "RX_UNFRAMED") -> None:
        nonlocal discarded
        if not discarded:
            return
        _raw_log_write(tag, bytes(discarded))
        discarded = bytearray()

    start_hdr = time.time()
    partial_hdr_start = None
    # Keep host framing limits aligned with firmware FramedSerial::kFrameMax.
    try:
        max_len = int(os.environ.get("PINBALLCTL_FRAME_MAX", "8192"))
    except Exception:
        max_len = 8192
    if max_len < 64:
        max_len = 64
    while True:
        while len(hdr) < 4:
            need = 4 - len(hdr)
            chunk = ser.read(need)
            if chunk:
                hdr += chunk
                if partial_hdr_start is None:
                    partial_hdr_start = time.time()
                continue
            now = time.time()
            if not hdr:
                # Idle link: return quickly so command/RPC polling remains responsive.
                if now - start_hdr > idle_timeout:
                    return None
            else:
                # Partial header started; allow longer to avoid splitting valid frames.
                if partial_hdr_start is not None and (now - partial_hdr_start) > header_timeout:
                    if hdr:
                        discarded.extend(hdr)
                    _flush_discarded("RX_UNFRAMED_TIMEOUT")
                    raise ValueError("timeout reading frame header")
        length = struct.unpack(">I", hdr)[0]
        if 0 < length <= max_len:
            break
        # Resync on noisy/unframed bytes without failing the loop.
        discarded.extend(hdr[:1])
        if len(discarded) >= 256 or b"\n" in discarded:
            _flush_discarded()
        hdr = hdr[1:]
    _flush_discarded()
    payload = b""
    start = time.time()
    while len(payload) < length:
        chunk = ser.read(length - len(payload))
        if chunk:
            payload += chunk
            continue
        if time.time() - start > body_timeout:
            if payload:
                _raw_log_write("RX_PARTIAL_FRAME", payload)
            raise ValueError("timeout reading frame body")
    return payload


def run(port="/dev/ttyUSB0", baud=460800):
    """Stream messages from the ESP32, dispatch events, and echo JSON to stdout."""
    global _raw_log_path  # noqa: PLW0603
    if not _acquire_bridge_lock(port):
        return
    try:
        ser = serial.Serial(port, baud, timeout=0.01)
    except Exception as e:
        _log_err(f"open failed on {port}: {e}")
        try:
            write_state(port=port, connected=False)
        except Exception:
            pass
        _release_bridge_lock()
        return

    _log(f"Opened serial {port} @ {baud}")
    instance_dir = commands_path().parent.parent
    _raw_log_path = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        / "pinballctl"
        / "esp-raw.log"
    )
    _raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    event_manager = get_event_manager(
        instance_path=str(instance_dir),
        logger=lambda msg: _verbose(msg),
    )
    try:
        ensure_scoring_bus_worker(
            instance_dir,
            logger=lambda msg: _verbose(msg),
        )
    except Exception as e:
        _log_err(f"failed to start scoring bus worker: {e}")
    try:
        ensure_audio_bus_worker(
            instance_dir,
            logger=lambda msg: _verbose(msg),
        )
    except Exception as e:
        _log_err(f"failed to start audio bus worker: {e}")
    try:
        # Keep reset/boot control lines deasserted for normal runtime.
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass
    # Allow ESP time to finish USB CDC boot chatter
    time.sleep(0.5)
    # First drain anything the ESP already emitted (e.g., boot INFO)
    use_v2 = False
    got_info, saw_v2 = _drain_info(ser, port, timeout_sec=3.5)
    use_v2 = saw_v2

    cmd = {"cmd":"HELLO","ver":"pinballctl/0.1.0","reqId": _bridge_req_id(), "wantProto": 2}
    _send_cmd(ser, cmd, use_v2=use_v2)
    # Send a single GET_INFO then read frames for a short window
    _send_cmd(ser, {"cmd": "GET_INFO", "reqId": _bridge_req_id()}, use_v2=use_v2)

    # Prime: read frames for ~2s to capture INFO/TIME before main loop
    hw_collect = []
    hw_controller = None
    fs_list_collect = []
    fs_list_path = None
    prime_end = time.time() + 2.0
    prime_rx = False
    while time.time() < prime_end:
        try:
            raw = _read_frame(ser)
        except Exception as e:
            _log_err(f"prime read error: {e}")
            _raw_log_write("PRIME_READ_ERROR", str(e))
            break
        if not raw:
            time.sleep(0.005)
            continue
        prime_rx = True
        typed, frame_type, payload = _decode_frame(raw)
        if typed:
            use_v2 = True
        if frame_type == 3:
            try:
                raw_txt = payload.decode("utf-8", errors="replace").strip()
            except Exception:
                raw_txt = None
            if raw_txt:
                _raw_log_write("RX_TEXT", raw_txt)
                _log_in_text(raw_txt)
            continue
        try:
            raw_txt = payload.decode("utf-8", errors="replace").strip()
            if raw_txt:
                _raw_log_write("RX_JSON", raw_txt)
            msg = json.loads(raw_txt)
        except Exception as e:
            _log_err(f"prime parse error: {e}")
            _raw_log_write("PRIME_PARSE_ERROR", payload)
            continue
        _log_in(msg)
        if msg.get("t") == "INFO" and msg.get("proto") == 2:
            use_v2 = True
        # Keep raw RX only; omit parsed JSON to reduce log noise.
        t = msg.get("t")
        if t == "HW_BEGIN":
            hw_controller = msg.get("controller")
            hw_collect = []
            continue
        if t == "HW_PIN":
            if msg.get("controller") == hw_controller:
                pin = msg.get("pin")
                if isinstance(pin, dict):
                    hw_collect.append(pin)
            continue
        if t == "HW_UNSAFE":
            if msg.get("controller") == hw_controller:
                pins = msg.get("pins")
                if isinstance(pins, list):
                    hw_collect.extend(p for p in pins if isinstance(p, dict))
            elif isinstance(msg.get("pins"), list):
                payload = {
                    "controller": msg.get("controller"),
                    "pins": [p for p in msg.get("pins") if isinstance(p, dict)],
                    "reloadedAt": _now_iso(),
                    "source": "esp",
                    "usingDefaults": False,
                }
                write_hardware_snapshot(payload, append=True)
            continue
        if t == "HW_END":
            if hw_collect:
                payload = {
                    "controller": msg.get("controller") or hw_controller,
                    "pins": hw_collect,
                    "reloadedAt": _now_iso(),
                    "source": "esp",
                    "usingDefaults": False,
                }
                write_hardware_snapshot(payload, append=False)
            hw_collect = []
            hw_controller = None
            continue
        if t == "INFO":
            info_fields = _parse_info_state_fields(msg)
            if info_fields:
                write_state(port=port, connected=True, **info_fields)
        if t == "TIME":
            ts = msg.get("ts")
            status = msg.get("status")
            iso = None
            try:
                if ts is not None:
                    iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except Exception:
                iso = None
            write_state(
                port=port,
                time_value=iso or (str(ts) if ts is not None else None),
                time_in_sync=(status == "ok"),
            )
    try:
        write_state(port=port, connected=bool(got_info or prime_rx))
    except Exception:
        pass
    _log("Bridge RX loop starting (framed mode)")
    # Kick one more GET_INFO as we enter the main loop to catch late responders
    _send_cmd(ser, {"cmd": "GET_INFO", "reqId": _bridge_req_id()}, use_v2=use_v2)
    hw_collect = []
    hw_controller = None
    fs_list_collect = []
    fs_list_path = None
    last_hw_rx = None
    try:
        echo_seq = int(read_state().get("echo_seq", 0) or 0)
    except Exception:
        echo_seq = 0
    event_rx_total = 0
    event_rx_evt_total = 0
    event_rx_ctrl_total = 0
    event_rx_last_seq = None
    event_rx_last_name = None
    event_rx_last_source = None
    event_rx_last_ts = 0.0
    event_state_written_at = 0.0
    event_state_write_interval_s = 1.0
    try:
        # Keep event execution ordered by default for deterministic hardware behavior.
        # Override with PINBALLCTL_BRIDGE_EVENT_WORKERS if explicit parallelism is needed.
        bridge_event_workers = int(os.environ.get("PINBALLCTL_BRIDGE_EVENT_WORKERS", "1"))
    except Exception:
        bridge_event_workers = 8
    if bridge_event_workers < 1:
        bridge_event_workers = 1
    event_exec = ThreadPoolExecutor(max_workers=bridge_event_workers, thread_name_prefix="bridge-events")
    event_exec_lock = Lock()
    event_exec_stats = {
        "submitted": 0,
        "started": 0,
        "completed": 0,
        "inflight": 0,
        "max_inflight": 0,
        "last_submit_at": 0.0,
        "last_start_at": 0.0,
        "last_complete_at": 0.0,
    }
    boot_completed_emitted = False
    boot_completed_last_emit_at = 0.0

    def _emit_boot_completed_once(
        info_msg: dict | None = None,
        phase: str = "runtime",
        *,
        allow_repeat: bool = False,
    ) -> None:
        nonlocal boot_completed_emitted, boot_completed_last_emit_at
        now = time.time()
        if allow_repeat:
            # Unsolicited INFO (typically emitted by ESP on boot/restart) should
            # re-fire BOOT_COMPLETED, but debounce to avoid accidental duplicates.
            if (now - float(boot_completed_last_emit_at or 0.0)) < 1.0:
                return
        else:
            if boot_completed_emitted:
                return
        try:
            info_msg = info_msg if isinstance(info_msg, dict) else {}
            info_fields = _parse_info_state_fields(info_msg)
            params = {
                "port": str(port),
                "phase": str(phase or "runtime"),
            }
            if isinstance(info_msg.get("controller"), str) and info_msg.get("controller"):
                params["controller"] = str(info_msg.get("controller"))
            if isinstance(info_msg.get("fw"), str) and info_msg.get("fw"):
                params["firmware"] = str(info_msg.get("fw"))
            elif isinstance(info_fields.get("firmware"), str) and info_fields.get("firmware"):
                params["firmware"] = str(info_fields.get("firmware"))
            if isinstance(info_msg.get("chip"), str) and info_msg.get("chip"):
                params["chip"] = str(info_msg.get("chip"))
            elif isinstance(info_fields.get("chip"), str) and info_fields.get("chip"):
                params["chip"] = str(info_fields.get("chip"))
            if isinstance(info_msg.get("proto"), int):
                params["proto"] = int(info_msg.get("proto"))
            elif isinstance(info_fields.get("proto"), int):
                params["proto"] = int(info_fields.get("proto"))
            source = "ESP.BRIDGE"
            envelope = get_bus().emit(name="BOOT_COMPLETED", source=source, params=params)
            try:
                event_manager.dispatch(
                    EventContext(
                        id=envelope.id,
                        ts=envelope.ts,
                        name=envelope.name,
                        source=envelope.source,
                        params=envelope.params,
                        origin="bridge",
                    )
                )
            except Exception as e:
                _log_err(f"BOOT_COMPLETED dispatch failed: {e}")
            try:
                append_event_log(
                    origin="bridge",
                    direction="esp->pi",
                    name="BOOT_COMPLETED",
                    source=source,
                    params=params,
                    meta={"t": "SYSTEM", "phase": str(phase or "runtime")},
                )
            except Exception as e:
                _log_err(f"BOOT_COMPLETED event log failed: {e}")
            try:
                apply_rules_for_event(
                    str(instance_dir),
                    name=envelope.name,
                    source=envelope.source,
                    params=envelope.params,
                    origin="rules",
                    logger=lambda msg: _verbose(msg),
                )
            except Exception as e:
                _log_err(f"BOOT_COMPLETED rules apply failed: {e}")
            boot_completed_emitted = True
            boot_completed_last_emit_at = now
        except Exception as e:
            _log_err(f"BOOT_COMPLETED emit failed: {e}")

    def _event_exec_submit(
        *,
        evt_name: str,
        evt_source: str,
        evt_params: dict,
        evt_id: str,
        evt_kind: str,
    ) -> None:
        now_submit = time.time()
        with event_exec_lock:
            event_exec_stats["submitted"] = int(event_exec_stats.get("submitted", 0)) + 1
            event_exec_stats["last_submit_at"] = now_submit

        def _worker() -> None:
            now_start = time.time()
            with event_exec_lock:
                event_exec_stats["started"] = int(event_exec_stats.get("started", 0)) + 1
                event_exec_stats["inflight"] = int(event_exec_stats.get("inflight", 0)) + 1
                if int(event_exec_stats["inflight"]) > int(event_exec_stats.get("max_inflight", 0)):
                    event_exec_stats["max_inflight"] = int(event_exec_stats["inflight"])
                event_exec_stats["last_start_at"] = now_start
            try:
                event_manager.dispatch(
                    EventContext(
                        id=evt_id,
                        ts=time.time(),
                        name=evt_name,
                        source=evt_source,
                        params=evt_params,
                        origin="bridge",
                    )
                )
            except Exception as e:
                _log_err(f"event manager dispatch failed name={evt_name} source={evt_source}: {e}")
            try:
                append_event_log(
                    origin="bridge",
                    direction="esp->pi",
                    name=evt_name,
                    source=evt_source,
                    params=evt_params,
                    meta={"t": evt_kind},
                )
            except Exception as e:
                _log_err(f"bridge event log append failed name={evt_name} source={evt_source}: {e}")
            try:
                apply_rules_for_event(
                    str(instance_dir),
                    name=evt_name,
                    source=evt_source,
                    params=evt_params,
                    origin="rules",
                    logger=lambda msg: _verbose(msg),
                )
            except Exception as e:
                _log_err(f"bridge rules apply failed name={evt_name} source={evt_source}: {e}")
            finally:
                now_done = time.time()
                with event_exec_lock:
                    event_exec_stats["inflight"] = max(0, int(event_exec_stats.get("inflight", 0)) - 1)
                    event_exec_stats["completed"] = int(event_exec_stats.get("completed", 0)) + 1
                    event_exec_stats["last_complete_at"] = now_done

        try:
            event_exec.submit(_worker)
        except Exception:
            with event_exec_lock:
                event_exec_stats["completed"] = int(event_exec_stats.get("completed", 0)) + 1
                event_exec_stats["last_complete_at"] = time.time()

    responses = {}
    pending = {}
    pending_order = []
    event_fire_seq_last = 0
    fs_list_req_id = None
    response_ttl = 60.0
    pending_ttl = 30.0
    resp_fp = responses_path()
    resp_fp.parent.mkdir(parents=True, exist_ok=True)
    blob_state = None
    write_responses_enabled = os.environ.get("PINBALLCTL_BRIDGE_WRITE_RESPONSES", "").strip().lower() in {"1", "true", "yes", "on"}
    sock_selector = None
    cmd_server = None
    rpc_server = None
    cmd_buffers = {}
    rpc_clients = {}
    rpc_by_req = {}
    recent_batches = {}

    def _host_reboot() -> dict:
        """Reboot ESP by toggling RTS on the active bridge serial handle."""
        try:
            ser.dtr = False
            ser.rts = False
            time.sleep(0.05)
            ser.rts = True
            time.sleep(0.05)
            ser.rts = False
            time.sleep(0.10)
            return {"t": "REBOOT", "ok": True}
        except Exception as e:
            return {"t": "REBOOT", "ok": False, "error": str(e)}

    def _setup_ipc_sockets():
        nonlocal sock_selector, cmd_server, rpc_server
        try:
            for p in (command_socket_path(), rpc_socket_path()):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            sel = selectors.DefaultSelector()
            cmd_srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            cmd_srv.bind(str(command_socket_path()))
            cmd_srv.listen(32)
            cmd_srv.setblocking(False)
            sel.register(cmd_srv, selectors.EVENT_READ, data="cmd_listen")

            rpc_srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            rpc_srv.bind(str(rpc_socket_path()))
            rpc_srv.listen(32)
            rpc_srv.setblocking(False)
            sel.register(rpc_srv, selectors.EVENT_READ, data="rpc_listen")

            sock_selector = sel
            cmd_server = cmd_srv
            rpc_server = rpc_srv
            _log(f"Command socket ready: {command_socket_path()}")
            _log(f"RPC socket ready: {rpc_socket_path()}")
        except Exception as e:
            _log_err(f"ipc socket setup failed: {e}")

    def _close_ipc_sockets():
        nonlocal sock_selector, cmd_server, rpc_server, cmd_buffers, rpc_clients, rpc_by_req
        try:
            if sock_selector:
                for key in list(sock_selector.get_map().values()):
                    try:
                        sock_selector.unregister(key.fileobj)
                    except Exception:
                        pass
                sock_selector.close()
        except Exception:
            pass
        sock_selector = None
        for sock_obj in list(cmd_buffers.keys()):
            try:
                sock_obj.close()
            except Exception:
                pass
        cmd_buffers = {}
        for sock_obj in list(rpc_clients.keys()):
            try:
                sock_obj.close()
            except Exception:
                pass
        rpc_clients = {}
        rpc_by_req = {}
        for srv in (cmd_server, rpc_server):
            if srv:
                try:
                    srv.close()
                except Exception:
                    pass
        cmd_server = None
        rpc_server = None
        try:
            command_socket_path().unlink(missing_ok=True)
        except Exception:
            pass
        try:
            rpc_socket_path().unlink(missing_ok=True)
        except Exception:
            pass

    def _rpc_close_client(sock_obj):
        try:
            if sock_selector:
                sock_selector.unregister(sock_obj)
        except Exception:
            pass
        state = rpc_clients.pop(sock_obj, None)
        if isinstance(state, dict):
            req = state.get("req_id")
            if req and rpc_by_req.get(req) is sock_obj:
                rpc_by_req.pop(req, None)
        try:
            sock_obj.close()
        except Exception:
            pass

    def _rpc_send(sock_obj, obj: dict):
        try:
            sock_obj.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8"))
        except Exception:
            pass
        _rpc_close_client(sock_obj)

    def _poll_socket_payloads(limit: int = 2048):
        payloads = []
        if not sock_selector:
            return payloads
        now = time.time()
        # Keep a short dedupe window for RPC batch retries.
        for bid, ts in list(recent_batches.items()):
            if (now - ts) > 60.0:
                recent_batches.pop(bid, None)
        for sock_obj, st in list(rpc_clients.items()):
            deadline = st.get("deadline", 0.0)
            if deadline and now > deadline:
                req_id = st.get("req_id")
                if req_id:
                    pending.pop(req_id, None)
                    try:
                        pending_order.remove(req_id)
                    except ValueError:
                        pass
                _rpc_send(sock_obj, {"ok": False, "error": "timeout"})
        try:
            events = sock_selector.select(timeout=0)
        except Exception:
            return payloads
        for key, _ in events:
            kind = key.data
            sock_obj = key.fileobj
            if kind == "cmd_listen":
                try:
                    while True:
                        c, _ = cmd_server.accept()
                        c.setblocking(False)
                        cmd_buffers[c] = b""
                        sock_selector.register(c, selectors.EVENT_READ, data="cmd_client")
                except BlockingIOError:
                    pass
                except Exception:
                    pass
                continue
            if kind == "rpc_listen":
                try:
                    while True:
                        c, _ = rpc_server.accept()
                        c.setblocking(False)
                        rpc_clients[c] = {"buffer": b"", "req_id": None, "deadline": 0.0, "registered": False}
                        sock_selector.register(c, selectors.EVENT_READ, data="rpc_client")
                except BlockingIOError:
                    pass
                except Exception:
                    pass
                continue
            if kind == "cmd_client":
                try:
                    chunk = sock_obj.recv(65536)
                except BlockingIOError:
                    chunk = None
                except Exception:
                    chunk = b""
                if chunk:
                    buf = cmd_buffers.get(sock_obj, b"") + chunk
                    while True:
                        idx = buf.find(b"\n")
                        if idx < 0:
                            break
                        raw = buf[:idx].strip()
                        buf = buf[idx + 1:]
                        if not raw:
                            continue
                        try:
                            msg = json.loads(raw.decode("utf-8", errors="replace"))
                            if isinstance(msg, dict):
                                payloads.append(msg)
                        except Exception:
                            continue
                    cmd_buffers[sock_obj] = buf
                else:
                    tail = cmd_buffers.pop(sock_obj, b"")
                    if tail:
                        try:
                            msg = json.loads(tail.decode("utf-8", errors="replace").strip())
                            if isinstance(msg, dict):
                                payloads.append(msg)
                        except Exception:
                            pass
                    try:
                        sock_selector.unregister(sock_obj)
                    except Exception:
                        pass
                    try:
                        sock_obj.close()
                    except Exception:
                        pass
                if len(payloads) >= limit:
                    break
                continue
            if kind == "rpc_client":
                st = rpc_clients.get(sock_obj)
                if not isinstance(st, dict):
                    _rpc_close_client(sock_obj)
                    continue
                try:
                    chunk = sock_obj.recv(65536)
                except BlockingIOError:
                    chunk = None
                except Exception:
                    chunk = b""
                if not chunk:
                    _rpc_close_client(sock_obj)
                    continue
                st["buffer"] = st.get("buffer", b"") + chunk
                if b"\n" not in st["buffer"]:
                    continue
                raw, rest = st["buffer"].split(b"\n", 1)
                st["buffer"] = rest
                if st.get("registered"):
                    continue
                try:
                    req = json.loads(raw.decode("utf-8", errors="replace").strip())
                except Exception:
                    _rpc_send(sock_obj, {"ok": False, "error": "bad_json"})
                    continue
                if not isinstance(req, dict):
                    _rpc_send(sock_obj, {"ok": False, "error": "bad_payload"})
                    continue
                cmd = req.get("cmd")
                req_id = str(req.get("reqId") or _bridge_req_id())
                match_t = req.get("match_t")
                timeout_s = req.get("timeout_s")
                try:
                    timeout_s = float(timeout_s)
                except Exception:
                    timeout_s = 3.0
                if timeout_s < 0.2:
                    timeout_s = 0.2
                if timeout_s > 120.0:
                    timeout_s = 120.0
                st["req_id"] = req_id
                st["deadline"] = time.time() + timeout_s
                st["registered"] = True
                rpc_by_req[req_id] = sock_obj
                if cmd == "ENQUEUE_BATCH":
                    batch_id = req.get("batchId")
                    if isinstance(batch_id, str) and batch_id and batch_id in recent_batches:
                        _rpc_send(sock_obj, {"ok": True, "queued": 0, "duplicate": True, "batchId": batch_id, "reqId": req_id})
                        continue
                    items = req.get("items")
                    count = 0
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                payloads.append(item)
                                count += 1
                    if isinstance(batch_id, str) and batch_id:
                        recent_batches[batch_id] = now
                    _rpc_send(sock_obj, {"ok": True, "queued": count, "batchId": batch_id, "reqId": req_id})
                    continue
                if cmd == "BRIDGE_EVENT_STATS":
                    with event_exec_lock:
                        exec_submitted = int(event_exec_stats.get("submitted", 0))
                        exec_started = int(event_exec_stats.get("started", 0))
                        exec_completed = int(event_exec_stats.get("completed", 0))
                        exec_inflight = int(event_exec_stats.get("inflight", 0))
                        exec_max_inflight = int(event_exec_stats.get("max_inflight", 0))
                        exec_last_submit_at = float(event_exec_stats.get("last_submit_at", 0.0))
                        exec_last_start_at = float(event_exec_stats.get("last_start_at", 0.0))
                        exec_last_complete_at = float(event_exec_stats.get("last_complete_at", 0.0))
                    exec_pending = max(0, exec_submitted - exec_completed)
                    exec_queued = max(0, exec_pending - exec_inflight)
                    _rpc_send(
                        sock_obj,
                        {
                            "ok": True,
                            "reqId": req_id,
                            "payload": {
                                "t": "BRIDGE_EVENT_STATS",
                                "rx_total": int(event_rx_total),
                                "rx_evt_total": int(event_rx_evt_total),
                                "rx_ctrl_total": int(event_rx_ctrl_total),
                                "last_seq": event_rx_last_seq,
                                "last_name": event_rx_last_name,
                                "last_source": event_rx_last_source,
                                "last_rx_ts": event_rx_last_ts,
                                "worker_count": bridge_event_workers,
                                "exec_submitted": exec_submitted,
                                "exec_started": exec_started,
                                "exec_completed": exec_completed,
                                "exec_pending": exec_pending,
                                "exec_inflight": exec_inflight,
                                "exec_queued": exec_queued,
                                "exec_max_inflight": exec_max_inflight,
                                "exec_last_submit_ts": exec_last_submit_at,
                                "exec_last_start_ts": exec_last_start_at,
                                "exec_last_complete_ts": exec_last_complete_at,
                            },
                        },
                    )
                    continue
                if cmd == "WAIT_REQ":
                    _register_pending(req_id, str(match_t) if match_t else None, "WAIT_REQ", ttl_s=timeout_s + 5.0)
                    continue
                if cmd == "HOST_REBOOT":
                    payload = _host_reboot()
                    _complete_pending(req_id, payload)
                    continue
                send_payload = dict(req)
                send_payload["reqId"] = req_id
                send_payload.pop("timeout_s", None)
                send_payload.pop("match_t", None)
                _register_pending(
                    req_id,
                    str(match_t) if match_t else None,
                    cmd if isinstance(cmd, str) else None,
                    ttl_s=timeout_s + 2.0,
                )
                _send_cmd(ser, send_payload, use_v2=use_v2)
        return payloads

    _setup_ipc_sockets()

    def _write_responses():
        if not write_responses_enabled:
            return
        try:
            tmp = resp_fp.with_suffix(resp_fp.suffix + ".tmp")
            tmp.write_text(json.dumps(responses))
            tmp.replace(resp_fp)
        except Exception as e:
            _log_err(f"response write failed: {e}")

    def _prune_responses():
        if not write_responses_enabled:
            return
        now = time.time()
        removed = False
        for req_id, entry in list(responses.items()):
            try:
                at = float(entry.get("at", 0) or 0)
            except Exception:
                at = 0
            if not at or (now - at) > response_ttl:
                responses.pop(req_id, None)
                removed = True
        if removed:
            _write_responses()

    def _prune_pending():
        now = time.time()
        for req_id in list(pending_order):
            entry = pending.get(req_id)
            if not entry:
                try:
                    pending_order.remove(req_id)
                except ValueError:
                    pass
                continue
            expires_at = entry.get("expires_at")
            if expires_at is not None:
                try:
                    if now > float(expires_at):
                        pending.pop(req_id, None)
                        try:
                            pending_order.remove(req_id)
                        except ValueError:
                            pass
                        continue
                except Exception:
                    pass
            created = entry.get("created_at", 0) or 0
            if created and (now - created) > pending_ttl:
                pending.pop(req_id, None)
                try:
                    pending_order.remove(req_id)
                except ValueError:
                    pass

    def _register_pending(req_id: str, match_t: str | None, cmd: str | None, ttl_s: float | None = None):
        if not req_id:
            return
        now = time.time()
        expires_at = None
        if ttl_s is not None:
            try:
                ttl = max(0.5, float(ttl_s))
                expires_at = now + ttl
            except Exception:
                expires_at = None
        pending[req_id] = {"created_at": now, "match_t": match_t, "cmd": cmd, "expires_at": expires_at}
        pending_order.append(req_id)

    def _complete_pending(req_id: str, payload: dict):
        if not req_id:
            return
        responses[req_id] = {"done": True, "at": time.time(), "payload": payload}
        rpc_sock = rpc_by_req.pop(req_id, None)
        if rpc_sock is not None:
            _rpc_send(rpc_sock, {"ok": True, "reqId": req_id, "payload": payload})
        pending.pop(req_id, None)
        try:
            pending_order.remove(req_id)
        except ValueError:
            pass
        if write_responses_enabled:
            _prune_responses()
            _write_responses()

    def _complete_pending_by_match_t(match_t: str, payload: dict) -> bool:
        """Fallback completion for responses that omit reqId.

        Some firmware paths can emit a valid typed response without reqId.
        In that case, complete the oldest pending request waiting for that type.
        """
        if not match_t:
            return False
        for pending_req_id in list(pending_order):
            entry = pending.get(pending_req_id)
            if not isinstance(entry, dict):
                continue
            if entry.get("match_t") != match_t:
                continue
            _log(f"RX matched pending by type {match_t} (missing reqId -> {pending_req_id})")
            _complete_pending(pending_req_id, payload)
            return True
        return False

    def _start_blob_put(payload: dict):
        nonlocal blob_state
        if blob_state and blob_state.get("state") not in ("done", "error"):
            _log_err("BLOB_PUT rejected: busy")
            try:
                write_state(blob_status={"state": "error", "error": "busy"})
            except Exception:
                pass
            return
        blob_type = payload.get("blobType") or "hardware"
        local_path = payload.get("localPath")
        remote_path = payload.get("remotePath")
        if not local_path or not remote_path:
            _log_err("BLOB_PUT missing localPath or remotePath")
            try:
                write_state(blob_status={"state": "error", "error": "missing_paths"})
            except Exception:
                pass
            return
        try:
            blob_bytes = Path(local_path).read_bytes()
            size = len(blob_bytes)
            crc32 = _crc32_bytes(blob_bytes)
        except Exception as e:
            _log_err(f"BLOB_PUT read failed ({local_path}): {e}")
            try:
                write_state(blob_status={"state": "error", "error": "read_failed", "path": local_path})
            except Exception:
                pass
            return
        req_id = _bridge_req_id()
        begin_cmd = {
            "cmd": "BLOB_BEGIN",
            "blobType": blob_type,
            "path": remote_path,
            "size": size,
            "crc32": crc32,
            "ver": 1,
            "reqId": req_id,
        }
        _log(f"BLOB_BEGIN {blob_type} {local_path} -> {remote_path} ({size} bytes)")
        try:
            write_state(blob_status={"state": "begin", "blobType": blob_type, "path": remote_path, "size": size})
        except Exception:
            pass
        _register_pending(req_id, "BLOB_READY", "BLOB_BEGIN")
        _send_cmd(ser, begin_cmd, use_v2=True)
        blob_state = {
            "state": "await_ready",
            "blobType": blob_type,
            "local_path": local_path,
            "remote_path": remote_path,
            "size": size,
            "crc32": crc32,
            "begin_req_id": req_id,
            "result_req_id": None,
            "manifest_req_id": None,
            "sent": 0,
            "chunk_size": 2048,
            "use_v2_chunks": True,
            "send_end": True,
            "busy_retries": 0,
            "blob_bytes": blob_bytes,
            "state_at": time.time(),
        }

    def _drive_blob_transfer():
        nonlocal blob_state
        if not blob_state:
            return
        now = time.time()
        state = blob_state.get("state")
        state_at = blob_state.get("state_at", now)
        if state == "await_ready" and (now - state_at) > 6.0:
            _log_err("BLOB_READY failed: timeout")
            try:
                write_state(blob_status={"state": "error", "error": "blob_ready_failed", "reason": "timeout"})
            except Exception:
                pass
            blob_state = None
            return
        if state == "await_busy_clear" and (now - state_at) > 3.0:
            _log_err("BLOB busy recovery failed: timeout waiting for BLOB_RESULT")
            try:
                write_state(blob_status={"state": "error", "error": "blob_busy_recovery_timeout"})
            except Exception:
                pass
            blob_state = None
            return
        if state == "await_ack" and (now - state_at) > 6.0:
            # Compatibility fallback: if firmware does not emit BLOB_ACK
            # (or ACK is dropped), continue with legacy transfer completion.
            _log("BLOB_ACK timeout; falling back to legacy completion")
            blob_state["state"] = "fallback_send_rest"
            blob_state["state_at"] = time.time()
            return
        if state == "await_result" and (now - state_at) > 10.0:
            _log_err("BLOB_RESULT failed: timeout")
            try:
                write_state(blob_status={"state": "error", "error": "blob_result_failed", "reason": "timeout"})
            except Exception:
                pass
            blob_state = None
            return
        if state == "await_manifest" and (now - state_at) > 4.0:
            _log_err("MANIFEST_UPDATE failed: timeout")
            blob_state = None
            return
        if state == "await_ready":
            ready = responses.get(blob_state.get("begin_req_id"), {}).get("payload")
            if not ready:
                return
            if not ready.get("ok"):
                reason = ready.get("reason") if isinstance(ready, dict) else "error"
                if reason == "busy":
                    retries = int(blob_state.get("busy_retries", 0) or 0)
                    if retries < 1:
                        _log("BLOB_READY busy; forcing stale blob reset")
                        old_req_id = str(blob_state.get("begin_req_id") or "")
                        responses.pop(old_req_id, None)
                        pending.pop(old_req_id, None)
                        try:
                            pending_order.remove(old_req_id)
                        except ValueError:
                            pass
                        cleanup_req_id = _bridge_req_id()
                        _register_pending(cleanup_req_id, "BLOB_RESULT", "BLOB_END")
                        try:
                            _send_cmd(
                                ser,
                                {
                                    "cmd": "BLOB_END",
                                    "reqId": cleanup_req_id,
                                    "sent": int(blob_state.get("sent", 0) or 0),
                                },
                                use_v2=True,
                            )
                        except Exception:
                            pass
                        blob_state["cleanup_req_id"] = cleanup_req_id
                        blob_state["state"] = "await_busy_clear"
                        blob_state["busy_retries"] = retries + 1
                        blob_state["state_at"] = time.time()
                        return
                _log_err(f"BLOB_READY failed: {reason}")
                try:
                    write_state(blob_status={"state": "error", "error": "blob_ready_failed", "reason": reason})
                except Exception:
                    pass
                blob_state = None
                return
            _log(
                f"BLOB_READY ok reqId={blob_state.get('begin_req_id')} "
                f"chunk={ready.get('chunkSize', blob_state.get('chunk_size'))}"
            )
            chunk_size = blob_state.get("chunk_size", 2048)
            try:
                ready_chunk = int(ready.get("chunkSize", chunk_size))
            except Exception:
                ready_chunk = chunk_size
            try:
                host_chunk_cap = int(os.environ.get("PINBALLCTL_BLOB_CHUNK_MAX", "256"))
            except Exception:
                host_chunk_cap = 256
            if host_chunk_cap < 256:
                host_chunk_cap = 256
            if host_chunk_cap > 8192:
                host_chunk_cap = 8192
            if ready_chunk < 256:
                ready_chunk = 256
            if ready_chunk > 8192:
                ready_chunk = 8192
            if ready_chunk > host_chunk_cap:
                ready_chunk = host_chunk_cap
            blob_state["chunk_size"] = ready_chunk
            if use_v2 and not blob_state.get("use_v2_chunks"):
                blob_state["use_v2_chunks"] = True
            responses.pop(blob_state.get("begin_req_id"), None)
            sent = 0
            blob_bytes = blob_state.get("blob_bytes") or b""
            if not isinstance(blob_bytes, (bytes, bytearray)):
                _log_err("BLOB_PUT send failed: blob bytes unavailable")
                try:
                    write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                except Exception:
                    pass
                blob_state = None
                return
            expected = int(blob_state.get("size", 0) or 0)
            if len(blob_bytes) != expected:
                _log_err(f"BLOB_PUT size mismatch: bytes={len(blob_bytes)} expected={expected}")
                try:
                    write_state(
                        blob_status={
                            "state": "error",
                            "error": "size_mismatch",
                            "expected": expected,
                            "actual": len(blob_bytes),
                        }
                    )
                except Exception:
                    pass
                blob_state = None
                return
            try:
                chunk_size = int(blob_state["chunk_size"])
                try:
                    window_bytes = int(os.environ.get("PINBALLCTL_BLOB_WINDOW_BYTES", "4096"))
                except Exception:
                    window_bytes = 4096
                if window_bytes < 256:
                    window_bytes = 256
                view = memoryview(blob_bytes)
                sent = 0
                target = min(expected, window_bytes)
                while sent < target:
                    chunk = view[sent: sent + chunk_size]
                    _send_raw_frame(ser, bytes(chunk), use_v2=blob_state.get("use_v2_chunks", False), frame_type=2)
                    sent += len(chunk)
                    if sent == len(chunk) or sent == blob_state["size"] or sent % (blob_state["chunk_size"] * 8) == 0:
                        _log(f"BLOB_PUT progress {sent}/{blob_state['size']}")
            except Exception as e:
                _log_err(f"BLOB_PUT send failed: {e}")
                try:
                    write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                except Exception:
                    pass
                blob_state = None
                return
            blob_state["sent"] = sent
            blob_state["acked"] = 0
            blob_state["window_bytes"] = window_bytes
            blob_state["ack_target"] = sent
            result_req_id = blob_state.get("begin_req_id")
            blob_state["result_req_id"] = result_req_id
            _register_pending(result_req_id, "BLOB_ACK", "BLOB_ACK")
            blob_state["state"] = "await_ack"
            blob_state["state_at"] = time.time()
            return
        if state == "await_ack":
            result_req_id = str(blob_state.get("result_req_id") or "")
            ack = responses.get(result_req_id, {}).get("payload")
            if not ack:
                return
            responses.pop(result_req_id, None)
            if not isinstance(ack, dict) or ack.get("t") != "BLOB_ACK":
                return
            try:
                acked = int(ack.get("received", 0) or 0)
            except Exception:
                acked = 0
            expected = int(blob_state.get("size", 0) or 0)
            if acked > expected:
                acked = expected
            blob_state["acked"] = max(int(blob_state.get("acked", 0) or 0), acked)
            sent = int(blob_state.get("sent", 0) or 0)
            ack_target = int(blob_state.get("ack_target", sent) or sent)
            if blob_state["acked"] < ack_target:
                _register_pending(result_req_id, "BLOB_ACK", "BLOB_ACK")
                blob_state["state_at"] = time.time()
                return
            if sent < expected:
                blob_bytes = blob_state.get("blob_bytes") or b""
                if not isinstance(blob_bytes, (bytes, bytearray)):
                    _log_err("BLOB_PUT send failed: blob bytes unavailable")
                    try:
                        write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                    except Exception:
                        pass
                    blob_state = None
                    return
                chunk_size = int(blob_state.get("chunk_size", 2048) or 2048)
                window_bytes = int(blob_state.get("window_bytes", 4096) or 4096)
                target = min(expected, sent + window_bytes)
                view = memoryview(blob_bytes)
                try:
                    while sent < target:
                        chunk = view[sent: sent + chunk_size]
                        _send_raw_frame(ser, bytes(chunk), use_v2=blob_state.get("use_v2_chunks", False), frame_type=2)
                        sent += len(chunk)
                        if sent == expected or sent % (chunk_size * 8) == 0:
                            _log(f"BLOB_PUT progress {sent}/{expected}")
                except Exception as e:
                    _log_err(f"BLOB_PUT send failed: {e}")
                    try:
                        write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                    except Exception:
                        pass
                    blob_state = None
                    return
                blob_state["sent"] = sent
                blob_state["ack_target"] = target
                _register_pending(result_req_id, "BLOB_ACK", "BLOB_ACK")
                blob_state["state_at"] = time.time()
                return
            _register_pending(result_req_id, "BLOB_RESULT", "BLOB_RESULT")
            if blob_state.get("send_end"):
                end_cmd = {
                    "cmd": "BLOB_END",
                    "reqId": result_req_id,
                    "sent": sent,
                }
                _send_cmd(ser, end_cmd, use_v2=blob_state.get("use_v2_chunks", False))
            blob_state["state"] = "await_result"
            blob_state["state_at"] = time.time()
            return
        if state == "fallback_send_rest":
            sent = int(blob_state.get("sent", 0) or 0)
            expected = int(blob_state.get("size", 0) or 0)
            blob_bytes = blob_state.get("blob_bytes") or b""
            if not isinstance(blob_bytes, (bytes, bytearray)):
                _log_err("BLOB_PUT fallback failed: blob bytes unavailable")
                try:
                    write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                except Exception:
                    pass
                blob_state = None
                return
            chunk_size = int(blob_state.get("chunk_size", 2048) or 2048)
            view = memoryview(blob_bytes)
            try:
                while sent < expected:
                    chunk = view[sent: sent + chunk_size]
                    _send_raw_frame(ser, bytes(chunk), use_v2=blob_state.get("use_v2_chunks", False), frame_type=2)
                    sent += len(chunk)
                    if sent == expected or sent % (chunk_size * 8) == 0:
                        _log(f"BLOB_PUT progress {sent}/{expected}")
            except Exception as e:
                _log_err(f"BLOB_PUT fallback send failed: {e}")
                try:
                    write_state(blob_status={"state": "error", "error": "send_failed", "sent": sent})
                except Exception:
                    pass
                blob_state = None
                return
            blob_state["sent"] = sent
            result_req_id = str(blob_state.get("result_req_id") or blob_state.get("begin_req_id") or "")
            if not result_req_id:
                result_req_id = _bridge_req_id()
            blob_state["result_req_id"] = result_req_id
            _register_pending(result_req_id, "BLOB_RESULT", "BLOB_RESULT")
            end_cmd = {"cmd": "BLOB_END", "reqId": result_req_id, "sent": sent}
            _send_cmd(ser, end_cmd, use_v2=blob_state.get("use_v2_chunks", False))
            blob_state["state"] = "await_result"
            blob_state["state_at"] = time.time()
            return
        if state == "await_busy_clear":
            cleanup_req_id = str(blob_state.get("cleanup_req_id") or "")
            cleanup_result = responses.get(cleanup_req_id, {}).get("payload")
            if not cleanup_result:
                return
            responses.pop(cleanup_req_id, None)
            pending.pop(cleanup_req_id, None)
            try:
                pending_order.remove(cleanup_req_id)
            except ValueError:
                pass
            _log("BLOB busy recovery complete; retrying BLOB_BEGIN")
            req_id = _bridge_req_id()
            begin_cmd = {
                "cmd": "BLOB_BEGIN",
                "blobType": blob_state.get("blobType") or "hardware",
                "path": blob_state.get("remote_path"),
                "size": int(blob_state.get("size", 0) or 0),
                "crc32": int(blob_state.get("crc32", 0) or 0),
                "ver": 1,
                "reqId": req_id,
            }
            _register_pending(req_id, "BLOB_READY", "BLOB_BEGIN")
            _send_cmd(ser, begin_cmd, use_v2=True)
            blob_state["begin_req_id"] = req_id
            blob_state["state"] = "await_ready"
            blob_state["state_at"] = time.time()
            return
        if state == "await_result":
            result = responses.get(blob_state.get("result_req_id"), {}).get("payload")
            if not result:
                return
            _log(f"BLOB_RESULT rx reqId={blob_state.get('result_req_id')} ok={result.get('ok')}")
            if not result.get("ok"):
                reason = result.get("reason") if isinstance(result, dict) else "timeout"
                _log_err(f"BLOB_RESULT failed: {reason}")
                try:
                    write_state(blob_status={"state": "error", "error": "blob_result_failed", "reason": reason})
                except Exception:
                    pass
                blob_state = None
                return
            _log(f"BLOB_PUT ok ({blob_state['sent']} bytes)")
            _log(f"BLOB_PUT complete reqId={blob_state.get('result_req_id')} bytes={blob_state.get('sent', 0)}")
            try:
                write_state(blob_status={"state": "done", "ok": True, "sent": blob_state["sent"], "blobType": blob_state["blobType"]})
            except Exception:
                pass
            try:
                sha = _sha256_file(blob_state["local_path"])
                uploaded_at = int(time.time())
                blob_state["sha256"] = sha
                blob_state["uploaded_at"] = uploaded_at
                update = {
                    "cmd": "FS_MANIFEST_UPDATE",
                    "name": blob_state["remote_path"],
                    "sha256": sha,
                    "size": blob_state["size"],
                    "uploadedAt": uploaded_at,
                    "reqId": _bridge_req_id(),
                }
                blob_state["manifest_req_id"] = update["reqId"]
                _log(f"MANIFEST_UPDATE {blob_state['remote_path']} sha={sha} bytes={blob_state['size']}")
                _register_pending(update["reqId"], "MANIFEST_UPDATE", "FS_MANIFEST_UPDATE")
                _send_cmd(ser, update, use_v2=use_v2)
                blob_state["state"] = "await_manifest"
                blob_state["state_at"] = time.time()
            except Exception as e:
                _log_err(f"MANIFEST_UPDATE error: {e}")
                blob_state = None
            return
        if state == "await_manifest":
            ack = responses.get(blob_state.get("manifest_req_id"), {}).get("payload")
            if not ack:
                return
            if not ack.get("ok"):
                reason = ack.get("error") if isinstance(ack, dict) else "timeout"
                _log_err(f"MANIFEST_UPDATE failed: {reason}")
            else:
                try:
                    st = read_state()
                    cached = st.get("manifest") if isinstance(st, dict) else None
                    data = {}
                    if isinstance(cached, dict) and cached.get("ok") and isinstance(cached.get("data"), dict):
                        data = dict(cached.get("data") or {})
                    data[blob_state["remote_path"]] = {
                        "sha256": blob_state.get("sha256") or "",
                        "size": int(blob_state.get("size", 0) or 0),
                        "uploadedAt": blob_state.get("uploaded_at"),
                    }
                    write_state(manifest={"t": "MANIFEST", "ok": True, "data": data})
                except Exception:
                    pass
            blob_state = None
    # Prime a manifest fetch now that pending helpers are ready.
    manifest_req_id = _bridge_req_id()
    _register_pending(manifest_req_id, "MANIFEST", "FS_MANIFEST_GET")
    _send_cmd(ser, {"cmd": "FS_MANIFEST_GET", "reqId": manifest_req_id}, use_v2=use_v2)

    last_rx = time.time()
    frame_errors = 0
    transient_read_errors = 0
    serial_error_streak = 0
    last_serial_error_at = 0.0

    def _prepare_cmd_for_send(payload: dict) -> dict:
        nonlocal event_fire_seq_last
        out = dict(payload)
        out.pop("match_t", None)
        cmd_name = str(out.get("cmd") or "").strip().upper()
        if cmd_name == "EVENT_FIRE":
            event_fire_seq_last = _next_event_fire_seq(event_fire_seq_last)
            out["seq"] = event_fire_seq_last
        return out

    while True:
        # Check for pending commands before blocking on serial reads.
        try:
            _prune_pending()
            if blob_state and blob_state.get("state") in ("await_ready", "await_ack", "await_result", "await_manifest"):
                # Avoid interleaving framed commands during active blob transfers.
                pass
            else:
                payloads = []
                payloads.extend(_poll_socket_payloads(limit=2048))
                deferred = []
                for payload in payloads:
                    if blob_state and payload.get("cmd") != "BLOB_PUT":
                        deferred.append(payload)
                        continue
                    if payload.get("cmd") == "BLOB_PUT":
                        _start_blob_put(payload)
                        continue
                    if payload.get("cmd") == "HOST_REBOOT":
                        boot_completed_emitted = False
                        boot_completed_last_emit_at = 0.0
                        _host_reboot()
                        continue
                    # Ensure queued GET_INFO probes are correlated replies, not
                    # mistaken as unsolicited boot INFO frames.
                    if str(payload.get("cmd") or "").strip().upper() == "GET_INFO" and not payload.get("reqId"):
                        payload = {**payload, "reqId": _bridge_req_id()}
                    req_id = payload.get("reqId")
                    match_t = payload.get("match_t")
                    if req_id and (req_id in pending or req_id in responses):
                        continue
                    if req_id:
                        _register_pending(str(req_id), str(match_t) if match_t else None, payload.get("cmd"))
                    # Some commands produce additional async responses keyed by secondary reqIds.
                    done_req_id = payload.get("doneReqId")
                    if done_req_id and isinstance(done_req_id, str):
                        _register_pending(str(done_req_id), "EVT_STREAM_DONE", payload.get("cmd"))
                    extra_req_ids = payload.get("extraReqIds")
                    if isinstance(extra_req_ids, list):
                        for extra_req_id in extra_req_ids:
                            if isinstance(extra_req_id, str) and extra_req_id:
                                _register_pending(str(extra_req_id), None, payload.get("cmd"))
                    send_payload = _prepare_cmd_for_send(payload)
                    _send_cmd(ser, send_payload, use_v2=use_v2)
                if deferred:
                    # Requeue deferred payloads in-memory via socket path.
                    try:
                        for item in deferred:
                            queued = {**item, "reqId": item.get("reqId") or _bridge_req_id()}
                            _send_cmd(ser, _prepare_cmd_for_send(queued), use_v2=use_v2)
                    except Exception as e:
                        _log_err(f"cmd requeue failed: {e}")
        except Exception as e:
            _log_err(f"cmd check failed: {e}")
        _drive_blob_transfer()

        # Process any additional queued frames immediately (non-blocking) after the first read
        def process_all(raw_first, body_timeout: float):
            raws = [raw_first] if raw_first else []
            try:
                while True:
                    try:
                        if ser.in_waiting <= 0:
                            break
                    except Exception:
                        break
                    # Keep header timeout conservative; tiny values can drop partial headers
                    # under USB scheduling jitter and desynchronize framing.
                    nxt = _read_frame(ser, body_timeout=body_timeout, header_timeout=1.0)
                    if not nxt:
                        break
                    raws.append(nxt)
            except Exception:
                pass
            return raws
        def process_fs_line(line: str) -> bool:
            nonlocal fs_list_collect, fs_list_path, fs_list_req_id
            line = line.strip()
            if line.startswith("FS_BEGIN"):
                _log_in_text(line)
                fs_list_collect = []
                fs_list_path = None
                fs_list_req_id = None
                parts = line.split()
                for part in parts[1:]:
                    if part.startswith("path="):
                        fs_list_path = part.split("=", 1)[1].strip() or "/"
                    elif part.startswith("reqId="):
                        fs_list_req_id = part.split("=", 1)[1].strip()
                if not fs_list_req_id:
                    fs_list_req_id = None
                return True
            if line.startswith("FS_FILE"):
                _log_in_text(line)
                entry = {"name": "", "size": 0, "mtime": 0}
                parts = line.split()
                for part in parts[1:]:
                    if "=" not in part:
                        continue
                    key, value = part.split("=", 1)
                    if key == "name":
                        entry["name"] = value
                    elif key == "size":
                        try:
                            entry["size"] = int(value)
                        except Exception:
                            entry["size"] = 0
                    elif key == "mtime":
                        try:
                            entry["mtime"] = int(value)
                        except Exception:
                            entry["mtime"] = 0
                if entry["name"]:
                    fs_list_collect.append(entry)
                return True
            if line.startswith("FS_END"):
                _log_in_text(line)
                parts = line.split()
                for part in parts[1:]:
                    if part.startswith("reqId="):
                        fs_list_req_id = part.split("=", 1)[1].strip()
                        break
                count = len(fs_list_collect)
                payload = {"path": fs_list_path or "/", "files": fs_list_collect, "count": count}
                try:
                    write_state(fs_list=payload)
                except Exception:
                    pass
                if fs_list_req_id:
                    complete_payload = {"t": "FS_LIST", "path": payload["path"], "files": payload["files"], "count": payload["count"]}
                    _complete_pending(fs_list_req_id, complete_payload)
                fs_list_collect = []
                fs_list_path = None
                fs_list_req_id = None
                return True
            return False

        def process_msg(msg: dict):
            nonlocal hw_collect, hw_controller, last_hw_rx, last_rx, echo_seq
            nonlocal event_rx_total, event_rx_evt_total, event_rx_ctrl_total, event_rx_last_seq, event_rx_last_name
            nonlocal event_rx_last_source, event_rx_last_ts, event_state_written_at
            # Keep raw RX only; omit parsed JSON to reduce log noise.
            t = msg.get("t")
            try:
                req_id = msg.get("reqId")
                if req_id:
                    rid = str(req_id)
                    entry = pending.get(rid)
                    if isinstance(entry, dict):
                        expected_t = entry.get("match_t")
                        if expected_t and isinstance(t, str) and t != expected_t:
                            # Ignore same-reqId side-channel messages (e.g. BLOB_DEBUG)
                            # until the expected typed response arrives.
                            pass
                        else:
                            _complete_pending(rid, msg)
                    else:
                        _complete_pending(rid, msg)
                elif isinstance(t, str):
                    _complete_pending_by_match_t(t, msg)
            except Exception:
                pass
            if t == "FS_STATUS":
                try:
                    write_state(fs_status=msg)
                except Exception:
                    pass
                write_state(port=port, connected=True)
                return
            if t == "MANIFEST":
                try:
                    write_state(manifest=msg)
                except Exception:
                    pass
                write_state(port=port, connected=True)
                return
            if t == "ECHO":
                try:
                    echo_seq += 1
                    write_state(echo_status=msg, echo_seq=echo_seq, port=port, connected=True)
                except Exception:
                    pass
                return
            if t == "EVENT_DROP":
                try:
                    append_event_log(
                        origin="bridge",
                        direction="esp->pi",
                        name=str(msg.get("name") or "EVENT_DROP"),
                        source=str(msg.get("source") or ""),
                        params={},
                        meta={
                            "t": "EVENT_DROP",
                            "reason": msg.get("reason"),
                            "seq": msg.get("seq"),
                            "name": msg.get("name"),
                            "source": msg.get("source"),
                        },
                    )
                except Exception:
                    pass
                return
            if t in ("EVT", "EVENT", "EVENT_ACK", "EVT_STREAM_STATUS", "EVT_STREAM_DONE"):
                now = time.time()
                event_rx_total += 1
                if t in ("EVT", "EVENT"):
                    event_rx_evt_total += 1
                else:
                    event_rx_ctrl_total += 1
                event_rx_last_ts = now
                if isinstance(msg.get("seq"), int):
                    event_rx_last_seq = int(msg.get("seq"))
                name = msg.get("name") or msg.get("event")
                if isinstance(name, str) and name:
                    event_rx_last_name = name
                src = msg.get("source") or msg.get("src")
                if isinstance(src, str) and src:
                    event_rx_last_source = src
                try:
                    bus = get_bus()
                    if t in ("EVT", "EVENT"):
                        evt_name = msg.get("name") if isinstance(msg.get("name"), str) else "esp.event"
                        evt_source = str(msg.get("source") or "esp")
                        evt_params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
                        if not isinstance(evt_params, dict):
                            evt_params = {}
                        if isinstance(msg.get("eventType"), str) and msg.get("eventType"):
                            evt_params.setdefault("eventType", str(msg.get("eventType")))
                        if isinstance(msg.get("detailMs"), int) and int(msg.get("detailMs")) > 0:
                            evt_params.setdefault("detailMs", int(msg.get("detailMs")))
                        if isinstance(msg.get("seq"), int):
                            evt_params.setdefault("seq", int(msg.get("seq")))
                        evt_params.setdefault("payload", msg)
                        bus.emit(
                            evt_name,
                            source=evt_source,
                            params=evt_params,
                        )
                        _event_exec_submit(
                            evt_name=evt_name,
                            evt_source=evt_source,
                            evt_params=dict(evt_params),
                            evt_id=str(msg.get("reqId") or _bridge_req_id()),
                            evt_kind=t,
                        )
                except Exception:
                    pass
                # Throttle event metrics writes to avoid heavy disk churn under load.
                # Keep a forced write on stream completion for immediate post-run visibility.
                if now - event_state_written_at >= event_state_write_interval_s or t in ("EVT_STREAM_DONE",):
                    with event_exec_lock:
                        exec_submitted = int(event_exec_stats.get("submitted", 0))
                        exec_started = int(event_exec_stats.get("started", 0))
                        exec_completed = int(event_exec_stats.get("completed", 0))
                        exec_inflight = int(event_exec_stats.get("inflight", 0))
                        exec_max_inflight = int(event_exec_stats.get("max_inflight", 0))
                        exec_last_submit_at = float(event_exec_stats.get("last_submit_at", 0.0))
                        exec_last_start_at = float(event_exec_stats.get("last_start_at", 0.0))
                        exec_last_complete_at = float(event_exec_stats.get("last_complete_at", 0.0))
                    exec_pending = max(0, exec_submitted - exec_completed)
                    exec_queued = max(0, exec_pending - exec_inflight)
                    try:
                        write_state(
                            event_metrics={
                                "rx_total": event_rx_total,
                                "rx_evt_total": event_rx_evt_total,
                                "rx_ctrl_total": event_rx_ctrl_total,
                                "last_t": t,
                                "last_name": event_rx_last_name,
                                "last_seq": event_rx_last_seq,
                                "last_source": event_rx_last_source,
                                "last_rx_ts": event_rx_last_ts,
                                "worker_count": bridge_event_workers,
                                "exec_submitted": exec_submitted,
                                "exec_started": exec_started,
                                "exec_completed": exec_completed,
                                "exec_pending": exec_pending,
                                "exec_inflight": exec_inflight,
                                "exec_queued": exec_queued,
                                "exec_max_inflight": exec_max_inflight,
                                "exec_last_submit_ts": exec_last_submit_at,
                                "exec_last_start_ts": exec_last_start_at,
                                "exec_last_complete_ts": exec_last_complete_at,
                            },
                            port=port,
                            connected=True,
                        )
                        event_state_written_at = now
                    except Exception:
                        pass
                return
            if t == "HW_BEGIN":
                hw_controller = msg.get("controller")
                hw_collect = []
                last_hw_rx = time.time()
                write_state(port=port, connected=True)
                return
            if t == "HW_PIN":
                if msg.get("controller") == hw_controller:
                    pin = msg.get("pin")
                    if isinstance(pin, dict):
                        hw_collect.append(pin)
                        last_hw_rx = time.time()
                write_state(port=port, connected=True)
                return
            if t == "HW_UNSAFE":
                if msg.get("controller") == hw_controller:
                    pins = msg.get("pins")
                    if isinstance(pins, list):
                        hw_collect.extend(p for p in pins if isinstance(p, dict))
                        last_hw_rx = time.time()
                elif isinstance(msg.get("pins"), list):
                    payload = {
                        "controller": msg.get("controller"),
                        "pins": [p for p in msg.get("pins") if isinstance(p, dict)],
                        "reloadedAt": _now_iso(),
                        "source": "esp",
                        "usingDefaults": False,
                    }
                    write_hardware_snapshot(payload, append=True)
                    last_hw_rx = time.time()
                write_state(port=port, connected=True)
                return
            if t == "HW_END":
                if hw_collect:
                    payload = {
                        "controller": msg.get("controller") or hw_controller,
                        "pins": hw_collect,
                        "reloadedAt": _now_iso(),
                        "source": "esp",
                        "usingDefaults": False,
                    }
                    write_hardware_snapshot(payload, append=False)
                hw_collect = []
                hw_controller = None
                last_hw_rx = None
                write_state(port=port, connected=True)
                return
            handle_event(msg)
            try:
                info_fields = _parse_info_state_fields(msg)
                if info_fields:
                    write_state(port=port, connected=True, **info_fields)
                    if msg.get("t") == "INFO":
                        # Emit BOOT_COMPLETED once per active bridge session.
                        # Some firmware paths can emit INFO without reqId outside
                        # of a real reboot; treating those as repeatable causes
                        # false BOOT_COMPLETED triggers and repeated BOOT rules.
                        _emit_boot_completed_once(msg, phase="runtime", allow_repeat=False)
                else:
                    write_state(port=port, connected=True)
                if msg.get("t") == "TIME":
                    ts = msg.get("ts")
                    status = msg.get("status")
                    iso = None
                    try:
                        if ts is not None:
                            iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
                    except Exception:
                        iso = None
                    write_state(
                        port=port,
                        time_value=iso or (str(ts) if ts is not None else None),
                        time_in_sync=(status == "ok"),
                    )
                    _debug(f"STATE updated: {msg}")
                if msg.get("t") in ("HW", "SCAN"):
                    payload = {
                        "controller": msg.get("controller"),
                        "pins": msg.get("pins", []),
                        "reloadedAt": _now_iso(),
                        "source": "esp",
                        "usingDefaults": False,
                    }
                    write_hardware_snapshot(payload, append=bool(msg.get("append")))
            except Exception:
                pass
        body_timeout = 8.0 if blob_state else 3.0
        try:
            raw = _read_frame(ser, body_timeout=body_timeout, header_timeout=1.0)
        except serial.SerialException as e:
            now_err = time.time()
            # Decay error streaks so sporadic hiccups never accumulate into reconnect.
            if last_serial_error_at and (now_err - last_serial_error_at) > 1.0:
                transient_read_errors = 0
                serial_error_streak = 0
            last_serial_error_at = now_err
            serial_error_streak += 1
            msg = str(e).lower()
            since_rx = time.time() - last_rx
            if ("returned no data" in msg) or ("device not configured" in msg):
                transient_read_errors += 1
                _log_err(f"serial read transient ({transient_read_errors}): {e}")
                # On macOS USB CDC this can be transient; avoid tearing down the link immediately.
                if transient_read_errors < 8:
                    time.sleep(0.05)
                    continue
            else:
                transient_read_errors = 0
                # Non-transient read errors can still be momentary; tolerate a short streak.
                if serial_error_streak < 5:
                    _log_err(f"serial read recoverable ({serial_error_streak}): {e}")
                    time.sleep(0.05)
                    continue
            _log_err(f"serial read failed: {e}")
            try:
                boot_completed_emitted = False
                write_state(port=port, connected=False)
            except Exception:
                pass
            try:
                ser.close()
            except Exception:
                pass
            reconnected = False
            for attempt in range(1, 61):
                wait_s = 0.5 if attempt <= 10 else 1.0
                time.sleep(wait_s)
                for cand in _esp_port_candidates(port):
                    try:
                        ser = serial.Serial(cand, baud, timeout=0.01)
                        try:
                            ser.dtr = False
                            ser.rts = False
                            ser.reset_input_buffer()
                            ser.reset_output_buffer()
                        except Exception:
                            pass
                        time.sleep(0.25)
                        got_info, saw_v2 = _drain_info(ser, cand, timeout_sec=1.2)
                        use_v2 = bool(saw_v2)
                        _send_cmd(ser, {"cmd": "HELLO", "ver": "pinballctl/0.1.0", "reqId": _bridge_req_id(), "wantProto": 2}, use_v2=use_v2)
                        probe_req_id = _bridge_req_id()
                        _send_cmd(ser, {"cmd": "GET_INFO", "reqId": probe_req_id}, use_v2=use_v2)
                        _send_cmd(ser, {"cmd": "FS_MANIFEST_GET", "reqId": _bridge_req_id()}, use_v2=use_v2)
                        probe = _wait_for_json(
                            ser,
                            timeout_sec=1.5,
                            match_fn=lambda m: (
                                isinstance(m, dict)
                                and (
                                    (m.get("t") == "INFO" and m.get("reqId") == probe_req_id)
                                    or m.get("t") in ("FS_STATUS", "PING", "MANIFEST")
                                )
                            ),
                        )
                        if not got_info and not probe:
                            try:
                                ser.close()
                            except Exception:
                                pass
                            continue
                        frame_errors = 0
                        last_rx = time.time()
                        port = cand
                        try:
                            write_state(port=port, connected=True)
                        except Exception:
                            pass
                        _log(f"serial reconnect ok on {port} (attempt {attempt})")
                        reconnected = True
                        break
                    except Exception:
                        continue
                if reconnected:
                    break
            if reconnected:
                continue
            _log_err("serial reconnect failed; bridge exiting")
            break
        except ValueError as e:
            frame_errors += 1
            _log_err(f"frame error ({frame_errors}): {e}")
            _raw_log_write("FRAME_ERROR", str(e))
            if frame_errors >= 3:
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass
                _log_err("frame errors exceeded; input buffer reset")
                frame_errors = 0
            time.sleep(0.05)
            continue
        except Exception as e:
            _log_err(f"unhandled read error: {e}")
            try:
                boot_completed_emitted = False
                write_state(port=port, connected=False)
            except Exception:
                pass
            time.sleep(0.1)
            continue
        if not raw:
            # If we haven't received anything for a while, attempt to resync
            if hw_collect and last_hw_rx and time.time() - last_hw_rx > 1.5:
                try:
                    payload = {
                        "controller": hw_controller,
                        "pins": hw_collect,
                        "reloadedAt": _now_iso(),
                        "source": "esp",
                        "usingDefaults": False,
                    }
                    write_hardware_snapshot(payload, append=False)
                    _log("HW snapshot committed (timeout without HW_END)")
                except Exception:
                    pass
                hw_collect = []
                hw_controller = None
                last_hw_rx = None
            if time.time() - last_rx > 5:
                last_rx = time.time()
            # Keep error counters from carrying across long idle windows.
            if last_serial_error_at and (time.time() - last_serial_error_at) > 1.0:
                transient_read_errors = 0
                serial_error_streak = 0
            time.sleep(0.005)
            continue
        transient_read_errors = 0
        serial_error_streak = 0
        frame_errors = 0
        last_rx = time.time()
        for raw_msg in process_all(raw, body_timeout=body_timeout):
            typed, frame_type, payload = _decode_frame(raw_msg)
            if typed:
                use_v2 = True
            if frame_type == 2:
                _debug(f"RX blob frame {len(payload)} bytes (ignored)")
                continue
            if frame_type == 3:
                try:
                    raw_txt = payload.decode("utf-8", errors="replace").strip()
                except Exception:
                    raw_txt = ""
                if raw_txt:
                    _raw_log_write("RX_TEXT", raw_txt)
                    process_fs_line(raw_txt)
                continue
            try:
                raw_txt = payload.decode("utf-8", errors="replace").strip()
            except Exception:
                raw_txt = ""
            if not raw_txt:
                continue
            _raw_log_write("RX_JSON", raw_txt)
            try:
                msg = json.loads(raw_txt)
                _log_in(msg)
                process_msg(msg)
            except Exception:
                if process_fs_line(raw_txt):
                    continue
                _raw_log_write("RX_PARSE_FALLBACK", raw_txt)
                _log_in_text(raw_txt)
        _drive_blob_transfer()
    try:
        ser.close()
    except Exception:
        pass
    try:
        # Avoid leaving stale "connected=true" when the bridge exits cleanly.
        write_state(port=port, connected=False)
    except Exception:
        pass
    try:
        event_exec.shutdown(wait=False, cancel_futures=False)
    except Exception:
        pass
    _close_ipc_sockets()
    _log("Bridge RX loop exiting")
    _release_bridge_lock()
