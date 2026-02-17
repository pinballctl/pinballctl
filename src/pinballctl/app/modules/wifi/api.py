"""Wi-Fi status/config API helpers for common OS targets."""
# pinballctl/app/modules/wifi/api_routes.py
import os
import re
import platform
import subprocess
from flask import jsonify, request
from . import api_bp

# --- tiny helpers ------------------------------------------------------------

def _run(cmd):
	"""Execute a command and return stripped stdout or empty string."""
	try:
		return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
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
	return _run(["iwgetid", "-r", "-i", iface]) or _run(["iwgetid", "-r"])

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
	"""Stub endpoint to accept Wi-Fi credentials from the UI."""
	ssid = (request.form.get("ssid") or "").strip()
	psk = request.form.get("psk") or ""
	return jsonify(ok=True, message="Wi-Fi settings received", ssid=ssid)
