#!/usr/bin/env python3
"""Build screenshots from a flat screenshots manifest.

Manifest format (utils/screenshots.txt):
- One entry per line.
- Blank lines and lines starting with # are ignored.
- Preferred format:
    assets/img/dashboard.webp {"url":"/dashboard","dark_mode":true}
  (output path first, JSON spec second)
- Also supported:
    {"output":"assets/img/dashboard.webp","url":"/dashboard"}

JSON spec keys mirror the docs screenshot tool where useful:
- url (required)
- next_url
- domain
- output (optional when output path is prefixed in the line)
- click (list of selectors or step objects)
- next_click (list of selectors or step objects)
- wait_for
- target
- dark_mode
- dark_toggle
- settle_ms
- with_frame
- full_page
- login / username / password / username_selector / password_selector / submit_selector
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "utils" / "screenshots.txt"
DEFAULT_DOMAIN = "http://127.0.0.1:8888"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
DEFAULT_TIMEOUT_MS = 10000
DEFAULT_VIEWPORT_WIDTH = 1440
DEFAULT_VIEWPORT_HEIGHT = 900


@dataclass
class ShotPlan:
    source: str
    line: int
    url: str
    next_url: str | None
    output: Path
    login: bool
    username: str | None
    password: str | None
    with_frame: bool
    full_page: bool
    target: str | None
    wait_for: str | None
    dark_mode: bool
    dark_toggle: str | None
    settle_ms: int
    click: list[Any]
    next_click: list[Any]
    username_selector: str
    password_selector: str
    submit_selector: str


def _bool(spec: dict[str, Any], key: str, default: bool) -> bool:
    value = spec.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{key} must be a boolean")


def _normalize_output(path_str: str, root: Path) -> Path:
    output = Path(path_str)
    if not output.is_absolute():
        output = root / output
    return output


def parse_manifest(manifest_path: Path) -> list[tuple[dict[str, Any], str, int]]:
    parsed: list[tuple[dict[str, Any], str, int]] = []
    text = manifest_path.read_text(encoding="utf-8")
    source = manifest_path.as_posix()

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        spec: dict[str, Any]
        if line.startswith("{"):
            try:
                spec = json.loads(line)
            except Exception as exc:
                raise ValueError(f"Invalid JSON in {source}:{idx}: {exc}") from exc
            if not isinstance(spec, dict):
                raise ValueError(f"Entry must decode to an object in {source}:{idx}")
            parsed.append((spec, source, idx))
            continue

        split_at = line.find("{")
        if split_at <= 0:
            raise ValueError(
                f"Invalid entry in {source}:{idx}. Expected '<output> {{...json...}}'"
            )

        output = line[:split_at].strip()
        payload = line[split_at:].strip()
        if not output:
            raise ValueError(f"Missing output path in {source}:{idx}")

        try:
            spec = json.loads(payload)
        except Exception as exc:
            raise ValueError(f"Invalid JSON in {source}:{idx}: {exc}") from exc
        if not isinstance(spec, dict):
            raise ValueError(f"Entry must decode to an object in {source}:{idx}")

        if "output" in spec and str(spec["output"]).strip() != output:
            raise ValueError(
                f"Conflicting output values in {source}:{idx}: '{output}' vs '{spec['output']}'"
            )
        spec["output"] = output
        parsed.append((spec, source, idx))

    return parsed


def build_plan(
    spec: dict[str, Any],
    source: str,
    line: int,
    root: Path,
    default_domain: str,
    default_username: str,
    default_password: str,
) -> ShotPlan:
    if "output" not in spec:
        raise ValueError(f"{source}:{line} missing required 'output'")
    if "url" not in spec:
        raise ValueError(f"{source}:{line} missing required 'url'")

    domain = str(spec.get("domain") or default_domain).rstrip("/")

    def _resolve_url(raw_url: str) -> str:
        value = str(raw_url).strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if not value.startswith("/"):
            value = "/" + value
        return urljoin(domain + "/", value.lstrip("/"))

    url = _resolve_url(str(spec["url"]))
    next_url = _resolve_url(str(spec["next_url"])) if spec.get("next_url") is not None else None

    login = _bool(spec, "login", False)
    with_frame = _bool(spec, "with_frame", True)
    full_page = _bool(spec, "full_page", False)
    dark_mode = _bool(spec, "dark_mode", False)

    username = str(spec.get("username")) if spec.get("username") is not None else default_username
    password = str(spec.get("password")) if spec.get("password") is not None else default_password

    target = str(spec.get("target")) if spec.get("target") is not None else None
    wait_for = str(spec.get("wait_for")) if spec.get("wait_for") is not None else None
    dark_toggle = str(spec.get("dark_toggle")) if spec.get("dark_toggle") is not None else None

    settle_ms = int(spec.get("settle_ms", 220))

    click = spec.get("click", [])
    if not isinstance(click, list):
        raise ValueError(f"{source}:{line} 'click' must be a list")

    next_click = spec.get("next_click", [])
    if not isinstance(next_click, list):
        raise ValueError(f"{source}:{line} 'next_click' must be a list")

    return ShotPlan(
        source=source,
        line=line,
        url=url,
        next_url=next_url,
        output=_normalize_output(str(spec["output"]), root),
        login=login,
        username=username,
        password=password,
        with_frame=with_frame,
        full_page=full_page,
        target=target,
        wait_for=wait_for,
        dark_mode=dark_mode,
        dark_toggle=dark_toggle,
        settle_ms=settle_ms,
        click=click,
        next_click=next_click,
        username_selector=str(spec.get("username_selector", "input[name='username']")),
        password_selector=str(spec.get("password_selector", "input[name='password']")),
        submit_selector=str(spec.get("submit_selector", "button[type='submit']")),
    )


def _first_visible_selector(page: Any, selectors: list[str], timeout_ms: int) -> str | None:
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=timeout_ms, state="visible")
            return selector
        except Exception:
            continue
    return None


def _run_login(page: Any, plan: ShotPlan, timeout_ms: int) -> None:
    user_sel = _first_visible_selector(
        page,
        [
            plan.username_selector,
            "#username",
            "input[type='text']",
            "input[name='user']",
        ],
        timeout_ms,
    )
    pass_sel = _first_visible_selector(
        page,
        [
            plan.password_selector,
            "#password",
            "input[type='password']",
            "input[name='pass']",
        ],
        timeout_ms,
    )
    if not user_sel or not pass_sel:
        raise RuntimeError("Login requested but could not find username/password fields")

    page.fill(user_sel, plan.username or "")
    page.fill(pass_sel, plan.password or "")

    try:
        page.click(plan.submit_selector, timeout=timeout_ms)
    except Exception:
        alt_submit = _first_visible_selector(
            page,
            [
                "button[type='submit']",
                "button:has-text('Sign in')",
                "button:has-text('Login')",
                "input[type='submit']",
            ],
            timeout_ms,
        )
        if not alt_submit:
            raise RuntimeError("Login requested but could not find submit button")
        page.click(alt_submit, timeout=timeout_ms)


def _run_click_steps(page: Any, plan: ShotPlan, timeout_ms: int, steps: list[Any]) -> None:
    username_selectors = {
        plan.username_selector,
        "input[name='username']",
        'input[name="username"]',
        "#username",
        "input[name='user']",
        'input[name="user"]',
        "input[type='text']",
    }
    password_selectors = {
        plan.password_selector,
        "input[name='password']",
        'input[name="password"]',
        "#password",
        "input[name='pass']",
        'input[name="pass"]',
        "input[type='password']",
    }

    for idx, step in enumerate(steps, start=1):
        if isinstance(step, str):
            page.wait_for_selector(step, timeout=timeout_ms, state="visible")
            page.click(step, timeout=timeout_ms)
            continue

        if not isinstance(step, dict):
            raise ValueError(f"{plan.source}:{plan.line} click step {idx} must be string or object")

        action = str(step.get("action", "click")).strip().lower()
        selector = step.get("selector")
        local_timeout = int(step.get("timeout_ms", timeout_ms))

        if action == "click":
            if not selector:
                raise ValueError(f"{plan.source}:{plan.line} click step {idx} missing 'selector'")
            page.click(str(selector), timeout=local_timeout)
        elif action == "wait":
            wait_sel = step.get("wait_for") or selector
            if not wait_sel:
                raise ValueError(
                    f"{plan.source}:{plan.line} wait step {idx} needs 'wait_for' or 'selector'"
                )
            page.wait_for_selector(str(wait_sel), timeout=local_timeout)
        elif action == "type":
            if not selector:
                raise ValueError(f"{plan.source}:{plan.line} type step {idx} missing 'selector'")
            sel = str(selector)
            if "value" in step:
                fill_value = str(step["value"])
            elif sel in username_selectors:
                fill_value = str(plan.username or "")
            elif sel in password_selectors:
                fill_value = str(plan.password or "")
            else:
                raise ValueError(f"{plan.source}:{plan.line} type step {idx} missing 'value'")
            page.fill(sel, fill_value, timeout=local_timeout)
        elif action == "hover":
            if not selector:
                raise ValueError(f"{plan.source}:{plan.line} hover step {idx} missing 'selector'")
            page.hover(str(selector), timeout=local_timeout)
        else:
            raise ValueError(
                f"{plan.source}:{plan.line} click step {idx} has unsupported action '{action}'"
            )

        if step.get("wait_for") and action != "wait":
            page.wait_for_selector(str(step["wait_for"]), timeout=local_timeout)


def _capture(page: Any, plan: ShotPlan, timeout_ms: int) -> None:
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    suffix = plan.output.suffix.lower()
    capture_path = plan.output
    tmp_path: Path | None = None

    # Playwright only writes PNG/JPEG; convert to WebP when requested.
    if suffix == ".webp":
        fd, temp_name = tempfile.mkstemp(prefix="shot_", suffix=".png")
        os.close(fd)
        tmp_path = Path(temp_name)
        capture_path = tmp_path

    if plan.target:
        locator = page.locator(plan.target).first
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.screenshot(path=str(capture_path))
    else:
        page.screenshot(path=str(capture_path), full_page=plan.full_page)

    if suffix == ".webp":
        try:
            _convert_to_webp(capture_path, plan.output)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


def _convert_to_webp(source: Path, target: Path) -> None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(source) as image:
            image.save(target, format="WEBP", quality=86, method=6)
        return
    except Exception:
        pass

    tool = shutil.which("cwebp")
    if tool:
        result = subprocess.run(
            [tool, "-quiet", "-q", "86", str(source), "-o", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        raise RuntimeError(result.stderr.strip() or "cwebp failed")

    raise RuntimeError(
        "WebP output requested but no encoder available. Install Pillow "
        "(`pip install pillow`) or install `cwebp`."
    )


def run_capture(plans: list[ShotPlan], timeout_ms: int, headed: bool, overwrite: bool) -> tuple[int, int]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(
            "Playwright is required for capture. Install it with:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return (0, len(plans))

    ok = 0
    fail = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            for plan in plans:
                if plan.output.exists() and not overwrite:
                    print(f"SKIP {plan.source}:{plan.line} -> {plan.output} (already exists)")
                    continue

                context = browser.new_context(
                    viewport={"width": DEFAULT_VIEWPORT_WIDTH, "height": DEFAULT_VIEWPORT_HEIGHT}
                )
                page = context.new_page()
                try:
                    if plan.dark_mode:
                        page.emulate_media(color_scheme="dark")

                    page.goto(plan.url, wait_until="domcontentloaded", timeout=timeout_ms)
                    if plan.login:
                        _run_login(page, plan, timeout_ms)
                    if plan.dark_toggle:
                        page.click(plan.dark_toggle, timeout=timeout_ms)
                    _run_click_steps(page, plan, timeout_ms, plan.click)

                    if plan.next_url:
                        page.goto(plan.next_url, wait_until="domcontentloaded", timeout=timeout_ms)
                        _run_click_steps(page, plan, timeout_ms, plan.next_click)

                    if plan.wait_for:
                        page.wait_for_selector(plan.wait_for, timeout=timeout_ms)
                    if plan.settle_ms > 0:
                        page.wait_for_timeout(plan.settle_ms)

                    _capture(page, plan, timeout_ms)
                    print(f"OK   {plan.source}:{plan.line} -> {plan.output}")
                    ok += 1
                except Exception as exc:
                    print(f"FAIL {plan.source}:{plan.line} -> {plan.output} ({exc})")
                    fail += 1
                finally:
                    page.close()
                    context.close()
        finally:
            browser.close()

    return (ok, fail)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build screenshots from utils/screenshots.txt")
    parser.add_argument("--root", type=Path, default=ROOT, help="Website root path")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to screenshots manifest (default: utils/screenshots.txt)",
    )
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Default base domain")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Default username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Default password")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS, help="Default timeout")
    parser.add_argument("--headed", action="store_true", help="Run browser with UI")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    manifest = args.manifest.resolve()

    parsed = parse_manifest(manifest)
    if not parsed:
        print("No screenshot entries found.")
        return

    plans: list[ShotPlan] = []
    for spec, source, line in parsed:
        plan = build_plan(
            spec=spec,
            source=source,
            line=line,
            root=root,
            default_domain=args.domain,
            default_username=args.username,
            default_password=args.password,
        )
        plans.append(plan)

    print(f"Found {len(plans)} screenshot entries")
    for plan in plans:
        target_label = plan.target or ("full-page" if plan.full_page else "window")
        print(
            f"PLAN {plan.source}:{plan.line} -> {plan.output} @ {plan.url} "
            f"target={target_label} dark_mode={plan.dark_mode} clicks={len(plan.click)}"
        )

    if args.dry_run:
        return

    ok, fail = run_capture(
        plans,
        timeout_ms=args.timeout_ms,
        headed=args.headed,
        overwrite=args.overwrite,
    )
    print(f"Completed: ok={ok} fail={fail}")
    if fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
