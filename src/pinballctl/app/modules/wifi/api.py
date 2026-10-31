"""Wi-Fi status/config API helpers for common OS targets."""
# pinballctl/app/modules/wifi/api_routes.py
import os
import re
import platform
import subprocess
import shutil
from flask import jsonify, request
from . import api_bp

# --- tiny helpers ------------------------------------------------------------

def _run(cmd):
	"""Execute a command and return stripped stdout or empty string."""
	try:
		return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
	except Exception:
		return ""

def _os():
	"""Return the lowercase platform system name."""
	return platform.system().lower()

# ------------------------- LINUX ---------------------------------------------

def _linux_iface():
	"""Guess the active Wi-Fi interface on Linux (env override supported)."""
	env = os.getenv("PINBALL_WIFI_IFACE")
	if env:
		return env
	iw = _run(["iw", "dev"])
	m = re.search(r"\bInterface\s+([^\s]+)", iw)
	return m.group(1) if m else "wlan0"

def _linux_ssid(iface):
	"""Return current SSID from iwgetid/nmcli."""
	ssid = _run(["iwgetid", "-r", "-i", iface]) or _run(["iwgetid", "-r"])
	if ssid:
		return ssid
	rows = _run(["nmcli", "--terse", "--escape", "no", "--fields", "active,ssid",
	             "device", "wifi", "list", "ifname", iface])
	return next((row[4:] for row in rows.splitlines() if row.startswith("yes:")), "")

def _linux_ip(iface):
	"""Return IPv4 for a Linux interface via ip tool."""
	ip = _run(["ip", "-4", "addr", "show", "dev", iface])
	m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)", ip)
	return m.group(1) if m else ""

def _linux_state(ssid, ip):
	"""Translate SSID/IP presence into a simple connection state."""
	if not ssid:
		return "wifi_disconnected"
	if not ip:
		return "wifi_associating"
	return "wifi_connected"

# ------------------------- macOS ---------------------------------------------

MAC_ROUTE = "/sbin/route"
MAC_IPCONFIG = "/usr/sbin/ipconfig"

def _mac_default_iface():
	"""Determine the default interface macOS routes through."""
	out = _run([MAC_ROUTE, "-n", "get", "default"])
	m = re.search(r"(?m)^\s*interface:\s*([^\s]+)", out)
	return m.group(1) if m else None

def _mac_ip_for(iface):
	"""Return IPv4 address for a macOS interface."""
	if not iface:
		return ""
	return _run([MAC_IPCONFIG, "getifaddr", iface])

def _mac_state(ip):
	"""Simple connected/disconnected state based on IP presence."""
	return "connected" if ip else "disconnected"

# ------------------------- routes --------------------------------------------

@api_bp.get("/status")
def status():
	"""Report Wi-Fi interface, SSID (if available), IP, and connection state."""
	sys = _os()

	if sys == "linux":
		iface = _linux_iface()
		ssid = _linux_ssid(iface) or None
		ip = _linux_ip(iface) or None
		return jsonify({
			"iface": iface,
			"ssid": ssid,
			"ip": ip,
			"state": _linux_state(ssid, ip),
		})

	if sys == "darwin":  # macOS
		iface = _mac_default_iface()
		ip = _mac_ip_for(iface) or None
		return jsonify({
			"iface": iface,
			"ssid": "Unsupported on this OS",
			"ip": ip,
			"state": _mac_state(ip), # "connected" or "disconnected"
		})

	# Others: quick stub
	return jsonify({
		"iface": None,
		"ssid": None,
		"ip": None,
		"state": "Unknown",
	})

@api_bp.post("/save")
def save():
	"""Save and activate a personal/open Wi-Fi connection through NetworkManager."""
	if _os() != "linux":
		return jsonify(ok=False, error="wifi_configuration_not_supported",
		               message="Wi-Fi changes are supported on Linux with NetworkManager, not this OS."), 501
	nmcli = shutil.which("nmcli")
	if not nmcli:
		return jsonify(ok=False, error="networkmanager_unavailable",
		               message="NetworkManager (nmcli) is required to change Wi-Fi settings."), 503
	ssid = request.form.get("ssid", "")
	psk = request.form.get("psk", "")
	if not 1 <= len(ssid.encode("utf-8")) <= 32 or any(c in ssid for c in "\r\n\x00"):
		return jsonify(ok=False, error="invalid_ssid", message="Enter a network name of 1–32 UTF-8 bytes."), 400
	if any(c in psk for c in "\r\n\x00") or (psk and not (
		(8 <= len(psk) <= 63 and all(32 <= ord(c) <= 126 for c in psk)) or (len(psk) == 64 and all(c in "0123456789abcdefABCDEF" for c in psk))
	)):
		return jsonify(ok=False, error="invalid_password",
		               message="Use an 8–63 character personal-network password, 64 hexadecimal digits, or leave blank for an open network."), 400
	# NetworkManager owns credential persistence. Never log command arguments or
	# return its output (which may contain secrets). No shell is involved.
	command = [nmcli, "--wait", "20", "device", "wifi", "connect", ssid,
	           "ifname", _linux_iface()]
	if psk:
		command.extend(["password", psk])
	try:
		result = subprocess.run(
			command, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=25,
			env={**os.environ, "LC_ALL": "C"},
		)
	except subprocess.TimeoutExpired:
		return jsonify(ok=False, error="connection_timeout",
		               message="Connection attempt timed out. Check the Pi network status before retrying; its address may have changed."), 504
	except OSError:
		return jsonify(ok=False, error="networkmanager_unavailable",
		               message="Could not start NetworkManager's connection tool."), 503
	if result.returncode:
		# Do not return command output: it may contain credentials or prompts.
		return jsonify(ok=False, error="connection_failed",
		               message="Wi-Fi connection failed. Check the password, network availability and NetworkManager permissions for the service user."), 502
	return jsonify(ok=True, message="Wi-Fi connection activated and saved by NetworkManager. The Pi address may have changed.")
