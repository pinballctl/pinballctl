"""System status helpers used by the dashboard module."""
import json
import os
import re
import platform
import subprocess
import shutil
import time
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from pinballctl.bridge.state import read_state as read_bridge_state, enqueue_command

# ---------- helpers -----------------------------------------------------------

def _run(cmd):
	"""Run a command and return stripped stdout, or None on failure."""
	try:
		out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
		return out.strip()
	except Exception:
		return None

def _run_json(cmd):
	"""Run a command expected to return JSON, returning parsed data or None."""
	try:
		out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
		return json.loads(out)
	except Exception:
		return None

IS_DARWIN = platform.system() == "Darwin"
IS_LINUX  = platform.system() == "Linux"
INFO_POKE_INTERVAL = 5  # seconds between opportunistic GET_INFO polls
INFO_STALE_SECONDS = 15  # consider ESP info stale beyond this
_last_info_poke = 0.0

# ---------- uptime ------------------------------------------------------------

def get_uptime():
	"""Calculate uptime in seconds/human format across Linux/macOS."""
	seconds = None

	if IS_LINUX:
		# /proc/uptime is simplest
		try:
			with open("/proc/uptime", "r") as f:
				seconds = float(f.read().split()[0])
		except Exception:
			# Fallback: uptime -s (boot time)
			started = _run(["uptime", "-s"])
			if started:
				try:
					dt0 = datetime.fromisoformat(started)
					seconds = (datetime.now() - dt0).total_seconds()
				except Exception:
					seconds = None

	elif IS_DARWIN:
		# sysctl -n kern.boottime returns: { sec = 1700000000, usec = 0 } ...
		out = _run(["sysctl", "-n", "kern.boottime"])
		if out:
			m = re.search(r"sec\s*=\s*(\d+)", out)
			if m:
				sec = int(m.group(1))
				seconds = datetime.now().timestamp() - sec
		if seconds is None:
			# who -b e.g. "system boot  2024-11-01 09:42"
			out = _run(["who", "-b"])
			if out:
				m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", out)
				if m:
					try:
						dt0 = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
						seconds = (datetime.now() - dt0).total_seconds()
					except Exception:
						pass

	# format
	human = since_iso = since_pretty = None
	if seconds is not None:
		secs = int(seconds)
		days, rem = divmod(secs, 86400)
		hours, rem = divmod(rem, 3600)
		minutes, seconds = divmod(rem, 60)
		parts = []
		if days: parts.append(f"{days}d")
		if hours or parts: parts.append(f"{hours}h")
		if minutes or parts: parts.append(f"{minutes}m")
		parts.append(f"{seconds}s")
		human = " ".join(parts)
		try:
			boot_time = datetime.now(timezone.utc).timestamp() - secs
			dt_boot = datetime.fromtimestamp(boot_time, tz=timezone.utc)
			since_iso = dt_boot.isoformat()
			since_pretty = dt_boot.strftime("%Y-%m-%d %H:%M:%S UTC")
		except Exception:
			since_iso = None
			since_pretty = None

	return {
		"seconds": int(secs) if 'secs' in locals() else None,
		"human": human,
		"since": since_iso,
		"since_pretty": since_pretty,
	}

# ---------- bridge ------------------------------------------------------------

def get_bridge_status():
	"""Best-effort detection of the bridge process across init systems."""
	state = read_bridge_state()

	# Linux systemd
	if IS_LINUX:
		active = _run(["systemctl", "is-active", "pinballctl-bridge.service"])
		if active in {"active", "activating"}:
			return {"running": True, "via": "systemctl", "detail": active, "firmware": state.get("firmware"), "chip": state.get("chip")}

	# PID file (works both on macOS & Linux)
	state_home = os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state"))
	pidfile = os.path.join(state_home, "pinballctl", "bridge.pid")
	try:
		if os.path.exists(pidfile):
			with open(pidfile, "r") as f:
				pid = int(f.read().strip())
			os.kill(pid, 0)
			return {"running": True, "via": "pidfile", "pid": pid, "firmware": state.get("firmware"), "chip": state.get("chip")}
	except Exception:
		pass

	# pgrep fallback
	out = _run(["pgrep", "-f", "pinballctl.bridge.daemon"])
	if out:
		pids = [int(x) for x in out.splitlines() if x.strip().isdigit()]
		if pids:
			state = read_bridge_state()
			return {
				"running": True,
				"via": "pgrep",
				"pid": pids[0],
				"firmware": state.get("firmware"),
				"chip": state.get("chip"),
			}

	return {"running": False, "via": None, "firmware": state.get("firmware"), "chip": state.get("chip")}

# ---------- wifi --------------------------------------------------------------

# ---- Linux implementations ----
def _linux_detect_wifi_iface():
	"""Guess the Wi-Fi interface name on Linux."""
	try:
		for name in os.listdir("/sys/class/net"):
			if name.startswith(("wl", "wlan")):
				return name
	except Exception:
		pass
	return None

def _linux_ip_for(iface):
	"""Return IPv4 address for a Linux interface."""
	data = _run_json(["ip", "-j", "addr"])
	if not data:
		return None
	for dev in data:
		if dev.get("ifname") == iface:
			for addr in dev.get("addr_info", []):
				if addr.get("family") == "inet":
					return addr.get("local")
	return None

def _linux_ssid(iface):
	"""Return current SSID for a Linux interface (nmcli/iwgetid)."""
	ssid = None
	out = _run(["nmcli", "-t", "-f", "active,ssid,device", "dev", "wifi"])
	if out:
		for line in out.splitlines():
			parts = line.split(":")
			if len(parts) >= 3 and parts[0] == "yes" and parts[2] == iface:
				ssid = parts[1] or None
				break
	if not ssid:
		ssid = _run(["iwgetid", iface, "--raw"])
	return ssid

def _linux_signal_dbm(iface):
	"""Return RSSI in dBm if iwconfig is available."""
	out = _run(["iwconfig", iface])
	if not out:
		return None
	m = re.search(r"Signal level[=:-]\s*(-?\d+)\s*dBm", out)
	return int(m.group(1)) if m else None

# ---- macOS implementations ----
def _darwin_wifi_device():
	"""Find the Wi-Fi device name on macOS via networksetup output."""
	# Parse: networksetup -listallhardwareports  → "Hardware Port: Wi-Fi ... Device: en0"
	out = _run(["networksetup", "-listallhardwareports"])
	if not out:
		return None
	dev = None
	current_port = None
	for line in out.splitlines():
		line = line.strip()
		if line.startswith("Hardware Port:"):
			current_port = line.split(":", 1)[1].strip()
		elif line.startswith("Device:") and current_port and current_port.lower() in {"wi-fi", "wifi"}:
			dev = line.split(":", 1)[1].strip()
			break
	return dev

def _darwin_ip_for(device):
	"""Return IPv4 for a macOS device using ipconfig."""
	out = _run(["ipconfig", "getifaddr", device])
	return out or None

# ---- main wifi status ----
def get_wifi_status():
	"""Collect Wi-Fi connection details based on OS capabilities."""
	if IS_LINUX:
		iface = _linux_detect_wifi_iface()
		if not iface:
			return {"connected": False, "interface": None}
		try:
			with open(f"/sys/class/net/{iface}/operstate", "r") as f:
				oper = f.read().strip()
		except Exception:
			oper = None
		ip = _linux_ip_for(iface)
		ssid = _linux_ssid(iface)
		signal = _linux_signal_dbm(iface)
		connected = bool(ip) and oper in {"up", "unknown"}
		return {
			"interface": iface,
			"connected": connected,
			"ssid": ssid,
			"ip": ip,
			"signal_dbm": signal,
			"operstate": oper,
		}

	elif IS_DARWIN:
		dev = _darwin_wifi_device()
		if not dev:
			return {
				"connected": False,
				"interface": None,
				"ssid": "unsupported",
				"ip": None,
				"signal_dbm": None,
				"operstate": None,
			}

		ip = _darwin_ip_for(dev)
		connected = bool(ip)
		return {
			"interface": dev,
			"connected": connected,
			"ssid": "Unsupported on this OS",   # simplified macOS behavior
			"ip": ip,
			"signal_dbm": None,
			"operstate": None,
		}

	# other OS: minimal
	return {"connected": False, "interface": None}

# ---------- top-level ---------------------------------------------------------

def get_dashboard_status():
	"""Aggregate uptime, bridge, and wifi state for the dashboard API."""
	state = read_bridge_state()
	bridge = get_bridge_status()

	# If bridge is up but we lack fresh ESP info, queue a GET_INFO once.
	try:
		global _last_info_poke  # noqa: PLW0603
		now = time.time()
		if bridge.get("running") and (now - _last_info_poke) > INFO_POKE_INTERVAL:
			# Lightweight poll to refresh firmware/time; bridge daemon handles dedupe.
			enqueue_command({"cmd": "GET_INFO", "reqId": uuid4().hex})
			_last_info_poke = now
	except Exception:
		pass

	info_at = state.get("info_at", 0) or 0
	try:
		info_fresh = (time.time() - float(info_at)) <= INFO_STALE_SECONDS
	except Exception:
		info_fresh = False
	esp_connected = bool(state.get("connected")) and bridge.get("running") and info_fresh
	return {
		"wifi": get_wifi_status(),
		"bridge": bridge,
		"esp": {
			"connected": bool(esp_connected),
			"firmware": state.get("firmware") if esp_connected else None,
			"chip": state.get("chip") if esp_connected else None,
			"time": state.get("time") if esp_connected else None,
			"time_in_sync": state.get("time_in_sync") if esp_connected else None,
		},
		"uptime": get_uptime(),
		"deps": get_dependencies_status(),
	}

# ---------- dependencies ------------------------------------------------------

def _check_version(cmd):
	"""Run a version command; return version string or None."""
	try:
		out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=5)
		first = out.strip().splitlines()[0]
		return first.strip() if first else out.strip()
	except Exception:
		return None

def _check_dep(name, commands):
	seen_binary = False
	for cmd in commands:
		if shutil.which(cmd[0]) is None:
			continue
		seen_binary = True
		ver = _check_version(cmd)
		if ver:
			return {"name": name, "ok": True, "version": ver}
	return {"name": name, "ok": seen_binary, "version": "Installed" if seen_binary else None}

def _check_godot_dep(name: str):
	"""Check Godot availability across PATH and known app bundles."""
	candidates = [
		"godot4",
		"godot",
		"/Applications/Godot.app/Contents/MacOS/Godot",
	]
	seen_binary = False
	for candidate in candidates:
		binary = None
		if candidate.startswith("/"):
			if Path(candidate).exists():
				binary = candidate
		else:
			found = shutil.which(candidate)
			if found:
				binary = found
		if not binary:
			continue
		seen_binary = True
		ver = _check_version([binary, "--version"])
		if ver:
			return {"name": name, "ok": True, "version": ver}
	return {"name": name, "ok": seen_binary, "version": "Installed" if seen_binary else None}

def get_dependencies_status():
	deps = [
		_check_dep("arduino-cli", [["arduino-cli", "version"]]),
		_check_dep("esptool", [["esptool", "version"], ["esptool.py", "version"], ["python3", "-m", "esptool", "version"]]),
		_check_dep("python3", [["python3", "--version"]]),
		_check_dep("jq", [["jq", "--version"]]),
	]
	host = platform.system().lower()
	if host == "darwin":
		deps.extend([
			_check_godot_dep("godot"),
		])
	elif host == "linux":
		deps.extend([
			_check_godot_dep("godot"),
			_check_dep("xrandr", [["xrandr", "--version"]]),
		])
	else:
		deps.append(_check_godot_dep("godot"))
	return deps
