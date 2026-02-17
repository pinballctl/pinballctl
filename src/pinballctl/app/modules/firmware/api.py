"""Serve firmware manifests/binaries to ESPLink and other clients."""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_from_directory, abort, current_app, url_for
from pathlib import Path
import json
import urllib.parse
import os

api_bp = Blueprint("firmware_api", __name__)

# ---------- paths ----------
def _repo_root_via_src() -> Path:
    """
    Walk up until we find the 'src' dir; repo root is its parent. Works in
    dev (src layout) and installed/editable envs.
    """
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "src":
            return p.parent
    return Path.cwd()

def _firmware_dir_local() -> Path:
    """Return the firmware directory under the instance path."""
    try:
        base = Path(current_app.instance_path)
    except Exception:
        base = Path.cwd() / "instance"
    d = base / "firmware"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _firmware_dir_remote() -> Path:
    """Return the dist/firmware directory."""
    return _repo_root_via_src() / "dist" / "firmware"

def _versions_path_local() -> Path | None:
    """Locate a versions manifest in the instance firmware folder."""
    d = _firmware_dir_local()
    v1 = d / "versions" / "versions.json"
    v2 = d / "versions.json"
    if v1.exists():
        return v1
    if v2.exists():
        return v2
    return None

def _versions_path_remote() -> Path | None:
    """Locate a versions manifest in the dist firmware folder."""
    d = _firmware_dir_remote()
    v1 = d / "versions" / "versions.json"
    v2 = d / "versions.json"
    if v1.exists():
        return v1
    if v2.exists():
        return v2
    return None

# ---------- helpers ----------
def _read_json(fp: Path) -> dict | None:
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None

def _abs_download_url_local(filename: str) -> str:
    base = request.host_url.rstrip("/")
    safe = urllib.parse.quote(Path(filename).name)
    return f"{base}{url_for('firmware_api.download_local', filename=safe)}"

def _abs_download_url_remote(filename: str) -> str:
    base = request.host_url.rstrip("/")
    safe = urllib.parse.quote(Path(filename).name)
    return f"{base}{url_for('firmware_api.download_remote', filename=safe)}"

def _versions_payload(vp: Path | None, download_builder) -> dict:
    if not vp:
        return {"latest": None, "versions": []}

    data = _read_json(vp) or {"latest": None, "versions": []}
    out = {"latest": data.get("latest"), "versions": []}

    for v in data.get("versions", []):
        fn = (v.get("filename") or "").strip()
        bn = Path(fn).name if fn else ""
        out["versions"].append({
            "version": v.get("version"),
            "date": v.get("date"),
            "notes": v.get("notes") or "",
            "filename": bn or None,
            "download_url": download_builder(bn) if bn else None,
            "size": v.get("size"),
            "sha256": v.get("sha256"),
            "partitions": Path(v.get("partitions") or "").name or None,
            "partitions_sha256": v.get("partitions_sha256"),
            "bootloader": Path(v.get("bootloader") or "").name or None,
            "bootloader_sha256": v.get("bootloader_sha256"),
        })

    if not out["latest"] and out["versions"]:
        out["latest"] = out["versions"][0].get("version")
    return out

# ---------- endpoints ----------
@api_bp.get("/versions")
def versions_local():
    """Return firmware versions from instance/firmware."""
    return jsonify(_versions_payload(_versions_path_local(), _abs_download_url_local))

@api_bp.get("/versions/remote")
def versions_remote():
    """Return firmware versions from dist/firmware."""
    return jsonify(_versions_payload(_versions_path_remote(), _abs_download_url_remote))


def _write_manifest(fp: Path, data: dict):
    fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(fp)


@api_bp.post("/delete")
def delete_version():
    """Delete a specific version from instance/firmware (manifest + file)."""
    payload = request.get_json(silent=True) or {}
    version = payload.get("version")
    if not version:
        return jsonify({"ok": False, "error": "version required"}), 400

    base = _firmware_dir_local()
    manifest_fp = base / "versions.json"
    manifest = _read_json(manifest_fp) or {"latest": None, "versions": []}

    remaining = []
    removed_file = None
    for v in manifest.get("versions", []):
        if v.get("version") == version:
            fn = v.get("filename") or ""
            partitions = v.get("partitions") or ""
            bootloader = v.get("bootloader") or ""
            if fn:
                fp = (base / fn)
                try:
                    if fp.exists():
                        fp.unlink()
                        removed_file = fp.name
                except Exception:
                    pass
            for extra in (partitions, bootloader):
                if not extra:
                    continue
                fp = base / Path(extra).name
                try:
                    if fp.exists():
                        fp.unlink()
                except Exception:
                    pass
            continue
        remaining.append(v)

    manifest["versions"] = remaining
    if remaining:
        manifest["latest"] = remaining[0].get("version")
    else:
        manifest["latest"] = None

    _write_manifest(manifest_fp, manifest)
    return jsonify({"ok": True, "removed": version, "file": removed_file})


@api_bp.post("/delete/all")
def delete_all_versions():
    """Delete all firmware entries and binaries from instance/firmware."""
    base = _firmware_dir_local()
    manifest_fp = base / "versions.json"
    deleted = []
    try:
        for fp in base.glob("*.bin"):
            try:
                fp.unlink()
                deleted.append(fp.name)
            except Exception:
                continue
    except Exception:
        pass
    try:
        if manifest_fp.exists():
            manifest_fp.unlink()
    except Exception:
        pass
    return jsonify({"ok": True, "deleted": deleted})

@api_bp.get("/download/<path:filename>")
def download_local(filename: str):
    """Serve a firmware binary from instance/firmware, enforcing .bin files."""
    dist_fw = _firmware_dir_local()
    bn = Path(filename).name
    if Path(bn).suffix.lower() != ".bin":
        abort(404)

    target = (dist_fw / bn).resolve()
    try:
        target.relative_to(dist_fw.resolve())
    except Exception:
        abort(404)

    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(
        directory=str(dist_fw),
        path=bn,
        as_attachment=True,
        download_name=bn,
        mimetype="application/octet-stream",
        max_age=0,
        conditional=True,
        etag=True,
        last_modified=target.stat().st_mtime,
    )

@api_bp.get("/download/remote/<path:filename>")
def download_remote(filename: str):
    """Serve a firmware binary from dist/firmware, enforcing .bin files."""
    dist_fw = _firmware_dir_remote()
    bn = Path(filename).name
    if Path(bn).suffix.lower() != ".bin":
        abort(404)

    target = (dist_fw / bn).resolve()
    try:
        target.relative_to(dist_fw.resolve())
    except Exception:
        abort(404)

    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(
        directory=str(dist_fw),
        path=bn,
        as_attachment=True,
        download_name=bn,
        mimetype="application/octet-stream",
        max_age=0,
        conditional=True,
        etag=True,
        last_modified=target.stat().st_mtime,
    )
