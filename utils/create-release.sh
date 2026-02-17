#!/usr/bin/env bash
# utils/build-release.sh
# Build the package and create a GitHub Release (non-interactive, flag-based).
# Notes:
#   - Pulls notes from CHANGELOG.md by default (section for the version).
#   - Fails if the GitHub release tag already exists (unless --replace 1).
#
# Requirements:
#   - Git
#   - Python 3.11+ (for tomllib) OR sed/grep fallback
#   - GitHub CLI 'gh' (authenticated: `gh auth login` or GH_TOKEN/GITHUB_TOKEN)
#
# Examples:
#   utils/build-release.sh
#   utils/build-release.sh --repo yourname/pinballctl --branch main
#   utils/build-release.sh --replace 1                      # overwrite if exists
#   utils/build-release.sh --prerelease 1 --latest 0        # pre-release
#   utils/build-release.sh --generate 1                     # auto notes
#   utils/build-release.sh --notes-file docs/notes.md       # custom file

set -euo pipefail

# Always run from repo root (script is at ./utils/build-release.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# --- Defaults ---
REPO=""
BRANCH=""
GENERATE_NOTES=0
NOTES=""
NOTES_FILE=""
CHANGELOG_FILE="CHANGELOG.md"
LATEST=1
PRERELEASE=1
REPLACE=0  # new flag

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --generate) GENERATE_NOTES="$2"; shift 2 ;;
    --notes) NOTES="$2"; shift 2 ;;
    --notes-file) NOTES_FILE="$2"; shift 2 ;;
    --changelog) CHANGELOG_FILE="$2"; shift 2 ;;
    --latest) LATEST="$2"; shift 2 ;;
    --prerelease) PRERELEASE="$2"; shift 2 ;;
    --replace) REPLACE="$2"; shift 2 ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --repo <owner/repo>      GitHub repository (default: auto-detect from git remote)
  --branch <name>          Branch to checkout before building (default: current)
  --generate <0|1>         Use GitHub's --generate-notes instead of CHANGELOG (default: 0)
  --notes "<text>"         Inline release notes (overrides CHANGELOG/generate)
  --notes-file <path>      File for release notes (overrides CHANGELOG/generate)
  --changelog <path>       Changelog file to read (default: CHANGELOG.md)
  --latest <0|1>           Mark as latest release (default: 1)
  --prerelease <0|1>       Mark as prerelease (default: 1)
  --replace <0|1>          Overwrite existing release if it already exists (default: 0)
  -h, --help               Show this help and exit
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# --- Helpers ---
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1"; exit 1; }; }

need git
need python
need gh

# --- Ensure gh authenticated ---
if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated."
  echo "Run: gh auth login   (or set GH_TOKEN/GITHUB_TOKEN)"
  exit 1
fi

# --- Post-release cleanup (belt & braces) ---
cleanup() {
  echo "🧹 Cleaning up temporary build metadata..."
  find "$ROOT" -type d -name "*.egg-info" -exec rm -rf {} + || true
  rm -rf "$ROOT/build" || true
}
trap cleanup EXIT

# --- Resolve repo ---
if [[ -z "$REPO" ]]; then
  if ! REPO="$(git config --get remote.origin.url)"; then
    echo "Could not determine git remote. Use --repo <owner/repo>." >&2
    exit 1
  fi
  if [[ "$REPO" == git@github.com:* ]]; then
    REPO="${REPO#git@github.com:}"
    REPO="${REPO%.git}"
  elif [[ "$REPO" == https://github.com/* ]]; then
    REPO="${REPO#https://github.com/}"
    REPO="${REPO%.git}"
  fi
fi

# --- Optional branch checkout ---
if [[ -n "$BRANCH" ]]; then
  git checkout "$BRANCH"
fi

# --- Determine version (portable) ---
if VERSION="$(python - <<'PY' 2>/dev/null
try:
    import tomllib, sys
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    print(data["project"]["version"])
except Exception:
    sys.exit(1)
PY
)"; then
  :
else
  VERSION="$(grep -E '^[[:space:]]*version[[:space:]]*=' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')" || true
fi

if [[ -z "${VERSION:-}" ]]; then
  echo "Could not parse version from pyproject.toml" >&2
  exit 1
fi
TAG="v${VERSION}"

echo "Repo       : $REPO"
echo "Branch     : ${BRANCH:-<current>}"
echo "Version    : $VERSION"
echo "Tag        : $TAG"

# --- Build package ---
python -m pip install --upgrade build >/dev/null
rm -rf dist build ./*.egg-info src/*.egg-info src/pinballctl.egg-info || true
python -m build

# --- Tag if needed ---
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists."
else
  git tag -a "$TAG" -m "Release $TAG"
  git push origin "$TAG"
fi

# --- Determine notes source ---
TMP_NOTES=""
if [[ -n "$NOTES_FILE" ]]; then
  :  # use provided file
elif [[ -n "$NOTES" ]]; then
  :  # inline notes
elif [[ "$GENERATE_NOTES" == "0" && -f "$CHANGELOG_FILE" ]]; then
  TMP_NOTES="$(mktemp)"
  python - "$CHANGELOG_FILE" "$VERSION" "$TMP_NOTES" <<'PY'
import re, sys, io
chlog, ver, out = sys.argv[1], sys.argv[2], sys.argv[3]
txt = io.open(chlog, 'r', encoding='utf-8').read()
pattern = re.compile(rf'(?m)^(##+)\s*\[?v?{re.escape(ver)}\]?\b.*?$')
m = pattern.search(txt)
if not m:
    sys.exit(1)
start = m.end()
n = re.search(r'(?m)^\s*##\s+', txt[start:])
end = start + (n.start() if n else len(txt))
section = txt[start:end].strip('\n')
if not section.strip():
    sys.exit(1)
io.open(out, 'w', encoding='utf-8').write(section.strip() + '\n')
PY
  if [[ $? -ne 0 ]]; then
    echo "CHANGELOG section for $VERSION not found; will fallback."
    rm -f "$TMP_NOTES" || true
    TMP_NOTES=""
  else
    NOTES_FILE="$TMP_NOTES"
  fi
fi

# --- Prepare gh release arguments ---
args=( "release" "create" "$TAG" dist/* "--repo" "$REPO" "--verify-tag" )

# Never mark prereleases as latest (avoids HTTP 422)
if [[ "$PRERELEASE" == "1" && "$LATEST" == "1" ]]; then
  echo "Note: prerelease requested; disabling --latest to satisfy GitHub rules."
  LATEST=0
fi

[[ "$LATEST" == "1" ]] && args+=( "--latest" )
[[ "$PRERELEASE" == "1" ]] && args+=( "--prerelease" )

if [[ -n "$NOTES_FILE" ]]; then
  args+=( "--notes-file" "$NOTES_FILE" )
elif [[ -n "$NOTES" ]]; then
  args+=( "--notes" "$NOTES" )
elif [[ "$GENERATE_NOTES" == "1" ]]; then
  args+=( "--generate-notes" )
else
  args+=( "--notes" "Release $TAG" )
fi

# --- Check if release already exists ---
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  if [[ "$REPLACE" == "1" ]]; then
    echo "⚠️  Release $TAG already exists — replacing (--replace=1)."
    gh release upload "$TAG" dist/* --clobber --repo "$REPO"
    echo "✅ Existing release updated for $TAG on $REPO"
    exit 0
  else
    echo "❌ Release $TAG already exists. Use --replace 1 to overwrite."
    exit 1
  fi
fi

# --- Create release ---
echo "Creating GitHub Release..."
gh "${args[@]}"
echo "✅ Done — created release for $TAG on $REPO"


[[ -n "${TMP_NOTES:-}" && -f "$TMP_NOTES" ]] && rm -f "$TMP_NOTES" || true