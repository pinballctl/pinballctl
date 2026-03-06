#!/usr/bin/env bash
set -euo pipefail

# Upload firmware to ESP32-S3 from local manifest (default) or remote manifest URL.
# Mirrors ESPLink web behavior:
# - resolves version
# - stops bridge for exclusive serial access
# - flashes bootloader + partitions + app with baud fallback
# - recovery: app-only compressed, then app-only uncompressed
# - optionally restarts bridge

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

DEFAULT_MANIFEST="${REPO_ROOT}/dist/firmware/versions.json"
DEFAULT_FW_DIR="${REPO_ROOT}/dist/firmware"
INSTANCE_FW_DIR="${REPO_ROOT}/src/instance/firmware"
PIDFILE="${HOME}/.local/state/pinballctl/bridge.pid"
BRIDGE_LOG="${HOME}/.local/state/pinballctl/bridge.log"

VERSION="latest"
PORT="auto"
BAUD=460800
MANIFEST_PATH="${DEFAULT_MANIFEST}"
MANIFEST_URL=""
RESTART_BRIDGE=1
STOP_BRIDGE=1
KEEP_TMP=0
FLASH_CTX_FILE=""
FLASH_SESSION_STARTED=0
FLASH_SUCCESS=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --version <vX.Y.Z|latest>   Firmware version to flash (default: latest)
  --port <device|auto>        Serial port (default: auto)
  --baud <rate>               Initial baud for flashing (default: 460800)
  --manifest <path>           Local versions.json path (default: dist/firmware/versions.json)
  --manifest-url <url>        Remote versions.json URL (downloads assets if needed)
  --no-stop-bridge            Do not stop bridge before flashing
  --no-restart-bridge         Do not restart bridge after flashing
  --keep-tmp                  Keep temporary downloaded files
  -h, --help                  Show help

Examples:
  bash utils/upload-firmware.sh --version latest --port /dev/cu.usbmodemXXXX
  bash utils/upload-firmware.sh --version v0.0.6
  bash utils/upload-firmware.sh --manifest-url https://example.com/firmware/versions.json --version latest
EOF
}

log() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

norm_ver() {
  local v="$1"
  v="${v//\"/}"
  v="${v//\'/}"
  if [[ "$v" == latest ]]; then
    printf '%s' "latest"
    return
  fi
  if [[ "$v" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s' "$v"
    return
  fi
  if [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'v%s' "$v"
    return
  fi
  fail "Invalid version: $v"
}

choose_port_auto() {
  local p
  for p in /dev/cu.usbmodem* /dev/tty.usbmodem* /dev/cu.usbserial* /dev/tty.usbserial* /dev/ttyUSB* /dev/ttyACM*; do
    [[ -e "$p" ]] || continue
    printf '%s' "$p"
    return 0
  done
  return 1
}

sha256_file() {
  local f="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  else
    sha256sum "$f" | awk '{print $1}'
  fi
}

resolve_esptool() {
  if [[ -n "${ESPLINK_ESPTOOL:-}" ]]; then
    read -r -a ESPTOOL_CMD <<<"${ESPLINK_ESPTOOL}"
    return 0
  fi
  if command -v esptool >/dev/null 2>&1; then
    ESPTOOL_CMD=("esptool")
    return 0
  fi
  if command -v esptool.py >/dev/null 2>&1; then
    ESPTOOL_CMD=("esptool.py")
    return 0
  fi
  ESPTOOL_CMD=("python3" "-m" "esptool")
}

start_flash_session() {
  FLASH_CTX_FILE="${TMP_DIR}/flash-session.json"
  python3 -m pinballctl.ops.flash_lifecycle begin \
    --port "${PORT}" \
    --reason "upload_firmware.sh" \
    --settle 1.0 \
    --context-file "${FLASH_CTX_FILE}" >/dev/null
  FLASH_SESSION_STARTED=1
}

end_flash_session() {
  [[ "${FLASH_SESSION_STARTED:-0}" -eq 1 ]] || return 0
  local restart_flag=0
  if [[ "$RESTART_BRIDGE" -eq 1 ]]; then
    restart_flag=1
  fi
  python3 -m pinballctl.ops.flash_lifecycle end \
    --success "$FLASH_SUCCESS" \
    --restart-on-success "$restart_flag" \
    --restart-baud 460800 \
    --context-file "${FLASH_CTX_FILE}" >/dev/null || true
  FLASH_SESSION_STARTED=0
}

download_file() {
  local url="$1"
  local out="$2"
  curl -fsSL --retry 2 --retry-delay 1 "$url" -o "$out"
}

run_cmd_with_stream() {
  local -a cmd=("$@")
  set +e
  "${cmd[@]}" 2>&1
  local code=$?
  set -e
  return "$code"
}

run_flash_attempt() {
  local run_baud="$1"
  local compress="$2"
  local no_stub="$3"
  local include_boot="$4"
  local include_parts="$5"
  local include_app="$6"
  local -a cmd=("${ESPTOOL_CMD[@]}" "--chip" "esp32s3" "--port" "${PORT}" "--baud" "${run_baud}" "--before" "default-reset" "--after" "hard-reset" "write-flash")
  if [[ "$no_stub" == "1" ]]; then
    cmd=("${ESPTOOL_CMD[@]}" "--chip" "esp32s3" "--port" "${PORT}" "--baud" "${run_baud}" "--before" "default-reset" "--after" "hard-reset" "--no-stub" "write-flash")
  fi
  if [[ "$compress" == "1" ]]; then
    cmd+=("-z")
  else
    cmd+=("-u")
  fi
  if [[ "$include_boot" == "1" ]]; then
    cmd+=("0x0000" "${BOOTLOADER_BIN}")
  fi
  if [[ "$include_parts" == "1" ]]; then
    cmd+=("0x8000" "${PARTITIONS_BIN}")
  fi
  if [[ "$include_app" == "1" ]]; then
    cmd+=("0x10000" "${APP_BIN}")
  fi
  run_cmd_with_stream "${cmd[@]}"
}

run_flash_ladder() {
  local -a baud_plan=()
  local candidate
  for candidate in "$BAUD" 230400 115200; do
    [[ "$candidate" =~ ^[0-9]+$ ]] || continue
    local seen=0
    for b in "${baud_plan[@]:-}"; do
      [[ "$b" == "$candidate" ]] && seen=1
    done
    [[ "$seen" -eq 1 ]] || baud_plan+=("$candidate")
  done

  local code=1
  local b
  for idx in "${!baud_plan[@]}"; do
    b="${baud_plan[$idx]}"
    if [[ "$idx" -gt 0 ]]; then
      log "Retrying flash at lower baud ${b}"
    fi
    if run_flash_attempt "$b" 1 0 1 1 1; then
      return 0
    fi
    code=$?
    if [[ "$idx" -lt $((${#baud_plan[@]} - 1)) ]]; then
      log "esptool exited ${code}; preparing retry"
      sleep 1
    fi
  done

  log "esptool exited ${code}; trying recovery mode (app-only @ 115200)"
  if run_flash_attempt 115200 1 0 0 0 1; then
    return 0
  fi

  log "app-only compressed retry failed; trying app-only uncompressed @ 115200"
  run_flash_attempt 115200 0 1 0 0 1
}

pick_entry_json() {
  local manifest_json="$1"
  local want_ver="$2"
  local picked
  if [[ "$want_ver" == "latest" ]]; then
    local latest
    latest="$(jq -r '.latest // empty' "$manifest_json" | tr -d '"' )"
    [[ -n "$latest" ]] || fail "Manifest has no latest version"
    want_ver="$(norm_ver "$latest")"
  fi
  picked="$(jq -c --arg v "$want_ver" '.versions[] | select(.version==$v)' "$manifest_json" | head -n1)"
  [[ -n "$picked" ]] || fail "Version ${want_ver} not found in manifest"
  printf '%s' "$picked"
}

resolve_artifact() {
  local manifest_dir="$1"
  local val="$2"
  local out="$3"
  if [[ "$val" =~ ^https?:// ]]; then
    download_file "$val" "$out"
  else
    local src="${manifest_dir}/${val}"
    [[ -f "$src" ]] || fail "Missing artifact: ${src}"
    cp -f "$src" "$out"
  fi
}

sync_instance_firmware() {
  mkdir -p "$INSTANCE_FW_DIR"
  local app_base part_base boot_base
  app_base="$(basename "$APP_BIN")"
  part_base="$(basename "$PARTITIONS_BIN")"
  boot_base="$(basename "$BOOTLOADER_BIN")"

  cp -f "$APP_BIN" "${INSTANCE_FW_DIR}/${app_base}"
  cp -f "$PARTITIONS_BIN" "${INSTANCE_FW_DIR}/${part_base}"
  cp -f "$BOOTLOADER_BIN" "${INSTANCE_FW_DIR}/${boot_base}"

  ENTRY_JSON="$ENTRY" \
  SEL_VERSION="$SEL_VERSION" \
  APP_BASENAME="$app_base" \
  PART_BASENAME="$part_base" \
  BOOT_BASENAME="$boot_base" \
  APP_BIN_PATH="$APP_BIN" \
  PART_BIN_PATH="$PARTITIONS_BIN" \
  BOOT_BIN_PATH="$BOOTLOADER_BIN" \
  INSTANCE_FW_DIR="$INSTANCE_FW_DIR" \
  python3 - <<'PY'
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def ver_key(v: str):
    try:
        s = v[1:] if v.startswith("v") else v
        a, b, c = s.split(".")
        return (int(a), int(b), int(c))
    except Exception:
        return (0, 0, 0)

entry = json.loads(os.environ["ENTRY_JSON"])
sel_version = os.environ["SEL_VERSION"]
instance_dir = Path(os.environ["INSTANCE_FW_DIR"])
manifest_fp = instance_dir / "versions.json"

date_val = entry.get("date") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
notes = entry.get("notes") or ""

app_path = Path(os.environ["APP_BIN_PATH"])
part_path = Path(os.environ["PART_BIN_PATH"])
boot_path = Path(os.environ["BOOT_BIN_PATH"])

new_entry = {
    "version": sel_version,
    "date": date_val,
    "notes": notes,
    "filename": os.environ["APP_BASENAME"],
    "size": app_path.stat().st_size,
    "sha256": sha256_file(app_path),
    "partitions": os.environ["PART_BASENAME"],
    "partitions_sha256": sha256_file(part_path),
    "bootloader": os.environ["BOOT_BASENAME"],
    "bootloader_sha256": sha256_file(boot_path),
}

manifest = {"latest": sel_version, "versions": []}
if manifest_fp.exists():
    try:
        manifest = json.loads(manifest_fp.read_text())
    except Exception:
        manifest = {"latest": sel_version, "versions": []}

versions = [v for v in (manifest.get("versions") or []) if isinstance(v, dict)]
updated = False
for i, v in enumerate(versions):
    if v.get("version") == sel_version:
        versions[i] = new_entry
        updated = True
        break
if not updated:
    versions.append(new_entry)

versions.sort(key=lambda v: ver_key(v.get("version", "")), reverse=True)
manifest["versions"] = versions
manifest["latest"] = sel_version if sel_version else (versions[0]["version"] if versions else None)
manifest_fp.write_text(json.dumps(manifest, indent=2) + "\n")
PY
  log "Synced to instance firmware: ${INSTANCE_FW_DIR}/${app_base}"
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --baud) BAUD="$2"; shift 2 ;;
    --manifest) MANIFEST_PATH="$2"; shift 2 ;;
    --manifest-url) MANIFEST_URL="$2"; shift 2 ;;
    --no-stop-bridge) STOP_BRIDGE=0; shift ;;
    --no-restart-bridge) RESTART_BRIDGE=0; shift ;;
    --keep-tmp) KEEP_TMP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

need_cmd jq
need_cmd python3
need_cmd curl
resolve_esptool

VERSION="$(norm_ver "$VERSION")"

if [[ "$PORT" == "auto" ]]; then
  PORT="$(choose_port_auto || true)"
  [[ -n "$PORT" ]] || fail "No serial port found (use --port)"
fi
[[ -e "$PORT" ]] || fail "Serial port does not exist: ${PORT}"

TMP_DIR="$(mktemp -d -t pinballctl-fw-XXXXXX)"
cleanup() {
  end_flash_session
  if [[ "$KEEP_TMP" -eq 0 ]]; then
    rm -rf "$TMP_DIR" || true
  else
    log "Kept tmp dir: ${TMP_DIR}"
  fi
}
trap cleanup EXIT

MANIFEST_JSON="${TMP_DIR}/versions.json"
if [[ -n "$MANIFEST_URL" ]]; then
  log "Downloading manifest: ${MANIFEST_URL}"
  download_file "$MANIFEST_URL" "$MANIFEST_JSON"
  MANIFEST_DIR="$(dirname "$MANIFEST_URL")"
else
  [[ -f "$MANIFEST_PATH" ]] || fail "Manifest not found: ${MANIFEST_PATH}"
  cp -f "$MANIFEST_PATH" "$MANIFEST_JSON"
  MANIFEST_DIR="$(cd "$(dirname "$MANIFEST_PATH")" && pwd)"
fi

ENTRY="$(pick_entry_json "$MANIFEST_JSON" "$VERSION")"
SEL_VERSION="$(printf '%s' "$ENTRY" | jq -r '.version')"
APP_NAME="$(printf '%s' "$ENTRY" | jq -r '.filename')"
PART_NAME="$(printf '%s' "$ENTRY" | jq -r '.partitions // "partitions.bin"')"
BOOT_NAME="$(printf '%s' "$ENTRY" | jq -r '.bootloader // empty')"
APP_SHA="$(printf '%s' "$ENTRY" | jq -r '.sha256 // empty')"
PART_SHA="$(printf '%s' "$ENTRY" | jq -r '.partitions_sha256 // empty')"
BOOT_SHA="$(printf '%s' "$ENTRY" | jq -r '.bootloader_sha256 // empty')"

APP_BIN="${TMP_DIR}/$(basename "$APP_NAME")"
PARTITIONS_BIN="${TMP_DIR}/$(basename "$PART_NAME")"
BOOTLOADER_BIN=""

log "Selected version: ${SEL_VERSION}"
resolve_artifact "$MANIFEST_DIR" "$APP_NAME" "$APP_BIN"
resolve_artifact "$MANIFEST_DIR" "$PART_NAME" "$PARTITIONS_BIN"
if [[ -n "$BOOT_NAME" && "$BOOT_NAME" != "null" ]]; then
  BOOTLOADER_BIN="${TMP_DIR}/$(basename "$BOOT_NAME")"
  resolve_artifact "$MANIFEST_DIR" "$BOOT_NAME" "$BOOTLOADER_BIN"
fi

if [[ -n "$APP_SHA" && "$APP_SHA" != "null" ]]; then
  [[ "$(sha256_file "$APP_BIN")" == "$APP_SHA" ]] || fail "App sha256 mismatch"
fi
if [[ -n "$PART_SHA" && "$PART_SHA" != "null" ]]; then
  [[ "$(sha256_file "$PARTITIONS_BIN")" == "$PART_SHA" ]] || fail "Partitions sha256 mismatch"
fi
if [[ -n "$BOOTLOADER_BIN" && -n "$BOOT_SHA" && "$BOOT_SHA" != "null" ]]; then
  [[ "$(sha256_file "$BOOTLOADER_BIN")" == "$BOOT_SHA" ]] || fail "Bootloader sha256 mismatch"
fi

if [[ -z "$BOOTLOADER_BIN" ]]; then
  fail "Manifest entry has no bootloader; expected bootloader-vX.Y.Z.bin"
fi

sync_instance_firmware

log "Flashing bootloader @ 0x0000, $(basename "$PARTITIONS_BIN") @ 0x8000, $(basename "$APP_BIN") @ 0x10000"
log "Target port: ${PORT}"
log "Initial baud: ${BAUD}"

if [[ "$STOP_BRIDGE" -eq 1 ]]; then
  start_flash_session
fi
sleep 1

if run_flash_ladder; then
  FLASH_SUCCESS=1
  log "Flash complete (${SEL_VERSION})"
else
  code=$?
  FLASH_SUCCESS=0
  fail "Flashing failed (esptool exit ${code})"
fi

log "Done."
