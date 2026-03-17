#!/usr/bin/env bash
set -euo pipefail

# ----------------------------
# Config (edit if needed)
# ----------------------------
BOARD="esp32:esp32:esp32s3"
PORT_DEVICE="${PORT_DEVICE:-/dev/cu.usbserial-A5069RR4}"

# Project layout (relative to repo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FIRMWARE_DIR="${REPO_ROOT}/src/firmware"
SRC_DIR="${FIRMWARE_DIR}/src"
SKETCH_PATH="${SRC_DIR}/src.ino"
BUILD_DIR="${FIRMWARE_DIR}/build"

DIST_DIR="${REPO_ROOT}/dist"
BIN_DIR="${DIST_DIR}/firmware"
VERSIONS_FILE="${BIN_DIR}/versions.json"

# Library requirements
LIBS_REQUIRED=(
  "ArduinoJson"
  "ArduinoOTA"
  "MPU6050"
  "https://github.com/johnrickman/LiquidCrystal_I2C"
  "FastLED"
)

PATCH_ROLLOVER=20

# ----------------------------
# Helpers
# ----------------------------
fail() { echo "❌ $*" >&2; exit 1; }
log()  { echo "➜ $*" >&2; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"; }

sha256_file() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  else
    shasum -a 256 "$f" | awk '{print $1}'
  fi
}

file_mtime_iso_utc() {
  local f="$1"
  local epoch
  epoch="$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")"
  if date -u -r "$epoch" +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
    date -u -r "$epoch" +"%Y-%m-%dT%H:%M:%SZ"
  else
    date -u -d "@$epoch" +"%Y-%m-%dT%H:%M:%SZ"
  fi
}

parse_semver() {
  local v="$1"
  if [[ "$v" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "${BASH_REMATCH[1]} ${BASH_REMATCH[2]} ${BASH_REMATCH[3]}"
  else
    fail "Invalid semver: ${v}"
  fi
}

next_version_auto() {
  local current="$1"
  read -r MAJ MIN PAT < <(parse_semver "$current")
  PAT=$((PAT + 1))
  if (( PAT > PATCH_ROLLOVER )); then
    MIN=$((MIN + 1)); PAT=0
  fi
  echo "${MAJ}.${MIN}.${PAT}"
}

detect_last_version() {
  local best="0.0.0"
  if [[ -d "$BIN_DIR" ]]; then
    for f in "$BIN_DIR"/firmware-v*.bin; do
      [[ -f "$f" ]] || continue
      if [[ "$(basename "$f")" =~ ^firmware-v([0-9]+\.[0-9]+\.[0-9]+)\.bin$ ]]; then
        local v="${BASH_REMATCH[1]}"
        best="$(printf "%s\n%s\n" "$best" "$v" | sort -V | tail -n1)"
      fi
    done
  fi
  echo "$best"
}

# Find the newest build output .bin (your app) from BUILD_DIR.
find_app_bin() {
  local app=""
  if [[ -f "${BUILD_DIR}/src.ino.bin" ]]; then
    app="${BUILD_DIR}/src.ino.bin"
  else
    app="$(
      find "${BUILD_DIR}" -type f -name "*.bin" -exec stat -f '%m %N' {} + 2>/dev/null \
      | sort -nr | head -n1 | cut -d' ' -f2-
    )"
  fi
  app="$(printf "%s" "$app" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  [[ -f "$app" ]] || fail "❌ No .bin produced in ${BUILD_DIR}"
  printf "%s" "$app"
}

# Copy bootloader + boot_app0 from BUILD_DIR.
# Arduino-ESP32 typically names bootloader like: <sketch>.ino.bootloader.bin
copy_bootloader_versioned() {
  local version="$1"
  mkdir -p "$BIN_DIR"

  local bootloader_src=""
  bootloader_src="$(find "${BUILD_DIR}" -type f -name "*bootloader*.bin" -print -quit 2>/dev/null || true)"
  if [[ -z "$bootloader_src" || ! -f "$bootloader_src" ]]; then
    fail "❌ No *bootloader*.bin found in BUILD_DIR. After erase_flash, ESP will not boot."
  fi

  local out="${BIN_DIR}/bootloader-v${version}.bin"
  cp -f "$bootloader_src" "$out"
  log "Installed bootloader: ${out}"
  printf "%s" "$out"
}

# ----------------------------
# Arduino core helpers
# ----------------------------
arduino_core_json() {
  arduino-cli core list --format json | jq -c '(.installed // .) | map(select((.ID // .id)=="esp32:esp32")) | first // empty'
}

# ----------------------------
# Deps
# ----------------------------
check_deps() {
  log "Checking required commands..."
  need_cmd arduino-cli
  need_cmd jq
  need_cmd sed
  need_cmd tr
  need_cmd python3

  log "Initializing arduino-cli config..."
  arduino-cli config init >/dev/null 2>&1 || true

  if ! arduino-cli config dump | grep -q 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'; then
    log "Adding Espressif boards URL..."
    arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json >/dev/null
  fi

  log "Ensuring core and libs..."
  arduino-cli config set library.enable_unsafe_install true >/dev/null
  if ! arduino-cli core list | grep -q '^esp32:esp32'; then
    log "Installing ESP32 core..."
    arduino-cli core update-index
    arduino-cli core install esp32:esp32
  fi

  for lib in "${LIBS_REQUIRED[@]}"; do
    ensure_lib "$lib"
  done
}

lib_present_regex() {
  local pattern="$1"
  arduino-cli lib list | awk -F'  +' '{print $1}' | grep -Eiq "$pattern"
}

ensure_lib() {
  local spec="$1"
  if [[ "$spec" == http* ]]; then
    local pattern='^LiquidCrystal[ _]?I2C$'
    if lib_present_regex "$pattern"; then
      log "Library already present: LiquidCrystal I2C"
      return 0
    fi
    log "Installing (git) LiquidCrystal I2C"
    arduino-cli lib install --git-url "$spec" || true
  else
    local name_regex="^${spec//+/\\+}$"
    if lib_present_regex "$name_regex"; then
      log "Library already present: $spec"
    else
      log "Installing $spec"
      arduino-cli lib install "$spec"
    fi
  fi
}

# ----------------------------
# Partitions helper
# ----------------------------
find_gen_esp32part() {
  local bases=(
    "$HOME/Library/Arduino15/packages/esp32/hardware/esp32"
    "$HOME/.arduino15/packages/esp32/hardware/esp32"
    "$HOME/.arduino15/packages/esp32/hardware/esp32"
  )
  local entries=()
  for base in "${bases[@]}"; do
    [[ -d "$base" ]] || continue
    for d in "$base"/*; do
      [[ -d "$d" ]] || continue
      local ver
      ver="$(basename "$d")"
      entries+=("${ver}|${d}")
    done
  done
  if ((${#entries[@]} == 0)); then
    fail "gen_esp32part.py not found; install the Arduino ESP32 core."
  fi
  local best
  best="$(printf "%s\n" "${entries[@]}" | sort -t'|' -k1,1V | tail -n1)"
  local dir="${best#*|}"
  local tool="${dir}/tools/gen_esp32part.py"
  [[ -f "$tool" ]] || fail "gen_esp32part.py missing at ${tool}"
  echo "$tool"
}

generate_partitions_versioned() {
  local version="$1"
  local csv="${FIRMWARE_DIR}/partitions.csv"
  [[ -f "$csv" ]] || fail "Missing partitions CSV: ${csv}"
  local tool
  tool="$(find_gen_esp32part)"

  mkdir -p "$BIN_DIR"

  local out="${BIN_DIR}/partitions-v${version}.bin"
  python3 "$tool" "$csv" "$out"
  log "Installed partitions: ${out}"
  printf "%s" "$out"
}

# ----------------------------
# Build + package
# ----------------------------
compile_firmware() {
  log "Compiling firmware..."
  mkdir -p "$BUILD_DIR" "$BIN_DIR"

  [[ -f "$SKETCH_PATH" ]] || fail "Missing sketch entrypoint: ${SKETCH_PATH}"

  local start_epoch
  start_epoch="$(date +%s)"

  if ! arduino-cli compile \
      --fqbn "${BOARD}" \
      --export-binaries \
      --build-path "${BUILD_DIR}" \
      "${SKETCH_PATH}" 1>&2; then
    fail "❌ Build failed; skipping artifact install."
  fi

  local newest_epoch
  newest_epoch="$(
    find "${BUILD_DIR}" -type f -name "*.bin" -exec stat -f '%m' {} + 2>/dev/null | sort -nr | head -n1 || true
  )"
  if [[ -z "${newest_epoch:-}" || "$newest_epoch" -lt "$start_epoch" ]]; then
    fail "❌ Build did not produce fresh .bin outputs in BUILD_DIR; skipping artifact install."
  fi

  find_app_bin
}

write_version_header() {
  local version="$1"
  local hdr="${SRC_DIR}/version.h"
  cat > "$hdr" <<EOF
#pragma once
#define FW_VERSION "${version}"
EOF
}

install_app_versioned() {
  local produced_app="$1"
  local version="$2"

  mkdir -p "$BIN_DIR"

  local out="${BIN_DIR}/firmware-v${version}.bin"
  cp -f "$produced_app" "$out"
  log "Installed app: ${out}"
  printf "%s" "$out"
}

write_versions_json() {
  local notes="$1"

  mkdir -p "$BIN_DIR"
  local tmp; tmp="$(mktemp)"
  local versions=()

  for f in "$BIN_DIR"/firmware-v*.bin; do
    [[ -f "$f" ]] || continue
    local base ver
    base="$(basename "$f")"
    if [[ "$base" =~ ^firmware-v([0-9]+\.[0-9]+\.[0-9]+)\.bin$ ]]; then
      ver="${BASH_REMATCH[1]}"
    else
      continue
    fi

    local app_size app_hash dt
    app_size="$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f")"
    app_hash="$(sha256_file "$f")"
    dt="$(file_mtime_iso_utc "$f")"

    # Infer the matching partitions/bootloader filenames for this firmware version
    local partitions_file="partitions-v${ver}.bin"
    local bootloader_file="bootloader-v${ver}.bin"

    local partitions_path="${BIN_DIR}/${partitions_file}"
    local bootloader_path="${BIN_DIR}/${bootloader_file}"

    local partitions_sha=""
    local bootloader_sha=""

    if [[ -f "$partitions_path" ]]; then
      partitions_sha="$(sha256_file "$partitions_path")"
    fi
    if [[ -f "$bootloader_path" ]]; then
      bootloader_sha="$(sha256_file "$bootloader_path")"
    fi

    versions+=("$(jq -n \
      --arg version "v${ver}" \
      --arg date "$dt" \
      --arg notes "$notes" \
      --arg filename "$base" \
      --arg sha256 "$app_hash" \
      --arg partitions "$partitions_file" \
      --arg partitions_sha256 "$partitions_sha" \
      --arg bootloader "$bootloader_file" \
      --arg bootloader_sha256 "$bootloader_sha" \
      --argjson size "$app_size" \
      '{
        version:$version,
        date:$date,
        notes:$notes,
        filename:$filename,
        size:$size,
        sha256:$sha256,
        partitions:$partitions,
        partitions_sha256:$partitions_sha256,
        bootloader:$bootloader,
        bootloader_sha256:$bootloader_sha256
      }')")
  done

  if ((${#versions[@]} == 0)); then
    jq -n '{latest:null, versions:[]}' > "$tmp"
    mv "$tmp" "$VERSIONS_FILE"
    log "Rebuilt ${VERSIONS_FILE} (no firmware bins found)"
    return
  fi

  local latest_ver
  latest_ver="$(printf "%s\n" "${versions[@]}" | jq -s 'map(.version) | sort_by(split("v")[1]|split(".")|map(tonumber)) | reverse | .[0]')"

  printf "%s\n" "${versions[@]}" | jq -s \
    --arg latest "$latest_ver" \
    '{latest:$latest, versions:.}' > "$tmp"

  mv "$tmp" "$VERSIONS_FILE"
  log "Rebuilt ${VERSIONS_FILE} (found ${#versions[@]} versions)"
}

# ----------------------------
# CLI + Entry
# ----------------------------
usage() {
  cat <<EOF
Usage:
  $(basename "$0") [--version X.Y.Z] [--notes "Text here"]

If --version is omitted, it auto-increments from the last build.
Notes are optional.

Expected outputs per run (in ${BIN_DIR}):
  - firmware-vX.Y.Z.bin
  - partitions-vX.Y.Z.bin
  - bootloader-vX.Y.Z.bin

versions.json will include filenames + sha256 for firmware, partitions and bootloader.
EOF
}

main() {
  local version=""
  local notes=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version) version="$2"; shift 2;;
      --notes)   notes="$2"; shift 2;;
      -h|--help) usage; exit 0;;
      *) fail "Unknown argument: $1";;
    esac
  done

  check_deps

  if [[ -z "$version" ]]; then
    local last
    last="$(detect_last_version)"
    version="$(next_version_auto "$last")"
  fi

  write_version_header "v${version}"

  log "Building firmware v${version}"
  [[ -n "$notes" ]] && log "Notes: ${notes}"

  local app_bin
  app_bin="$(compile_firmware)"

  # Install the 3 expected versioned outputs
  local app_out
  app_out="$(install_app_versioned "$app_bin" "$version")"

  local boot_out
  boot_out="$(copy_bootloader_versioned "$version")"

  local part_out
  part_out="$(generate_partitions_versioned "$version")"

  # Update versions.json with firmware + partitions + bootloader + sha256
  write_versions_json "$notes"

  echo
  echo "✅ Done."
  echo "   Firmware   : ${app_out}"
  echo "   Partitions : ${part_out}"
  echo "   Bootloader : ${boot_out}"
  echo "   Index      : ${VERSIONS_FILE}"

  log "Cleaning build folder..."
  rm -rf "$BUILD_DIR"
}

main "$@"
