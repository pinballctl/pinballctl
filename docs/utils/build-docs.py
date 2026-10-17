#!/usr/bin/env python3
"""Build a static docs site from markdown pages.

Source of truth:
- docs/**/*.md
- assets/**

Generated:
- index.html
- site-data.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

try:
    import markdown as _markdown  # type: ignore
except Exception:
    _markdown = None

_ORDERED_NAME_RE = re.compile(r"^\s*(\d+)\s*[-_. )]+\s*(.*)$")
_ICON_NAME_SIZE_RE = re.compile(r"(?<!\d)(\d{2,4})[xX](\d{2,4})(?!\d)")
_IMG_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
}


def _ordered_name(raw: str) -> tuple[int, str]:
    text = str(raw or "").strip()
    match = _ORDERED_NAME_RE.match(text)
    if not match:
        clean = text.replace("-", " ").replace("_", " ").strip()
        return (10_000, clean or text)
    order = int(match.group(1))
    tail = (match.group(2) or "").strip()
    clean = tail.replace("-", " ").replace("_", " ").strip() or text
    return (order, clean)


def _title_from_markdown(md_path: Path) -> str:
    stem = _ordered_name(md_path.stem)[1].title()
    try:
        for line in md_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("# "):
                heading = _ordered_name(s[2:].strip())[1]
                return heading or stem
    except Exception:
        return stem
    return stem


def _guess_media_type(path: Path) -> str | None:
    return _IMG_MEDIA_TYPES.get(path.suffix.lower())


def _image_size(path: Path) -> tuple[int, int] | None:
    media_type = _guess_media_type(path)
    if not media_type:
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None

    if media_type == "image/png":
        if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
            w = int.from_bytes(data[16:20], "big")
            h = int.from_bytes(data[20:24], "big")
            if w > 0 and h > 0:
                return (w, h)
        return None

    if media_type == "image/jpeg":
        if len(data) < 4 or data[0:2] != b"\xff\xd8":
            return None
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9):
                i += 2
                continue
            if i + 4 > len(data):
                return None
            seg_len = int.from_bytes(data[i + 2:i + 4], "big")
            if seg_len < 2 or i + 2 + seg_len > len(data):
                return None
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 9 > len(data):
                    return None
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                if w > 0 and h > 0:
                    return (w, h)
                return None
            i += 2 + seg_len
        return None

    if media_type == "image/webp":
        if len(data) < 30 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
            return None
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            if w > 0 and h > 0:
                return (w, h)
        if chunk == b"VP8 " and len(data) >= 30:
            # Frame header width/height are 14-bit little-endian fields.
            w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            if w > 0 and h > 0:
                return (w, h)
        if chunk == b"VP8L" and len(data) >= 25:
            b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
            w = 1 + (((b1 & 0x3F) << 8) | b0)
            h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            if w > 0 and h > 0:
                return (w, h)
        return None

    return None


def _human_label_from_name(name: str) -> str:
    text = str(name or "").strip()
    text = re.sub(r"\.[A-Za-z0-9]+$", "", text)
    text = re.sub(r"^screenshot[-_. ]*", "", text, flags=re.IGNORECASE)
    text = text.replace("-", " ").replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.title() or "Screenshot"


def _slug_to_page_href(slug: str) -> str:
    s = str(slug or "").strip()
    if not s or s.lower() == "readme":
        return "/"
    parts = [p for p in s.split("/") if p]
    cleaned_parts: list[str] = []
    for raw_part in parts:
        part = str(raw_part)
        if part.lower().endswith(".md"):
            part = part[:-3]
        part = _ordered_name(part)[1] or part
        part = re.sub(r"^\d+\s*[-_. )]+\s*", "", part).strip()
        part = part.strip().lower()
        part = re.sub(r"[^a-z0-9]+", "-", part)
        part = re.sub(r"-{2,}", "-", part).strip("-")
        if part:
            cleaned_parts.append(part)
    if not cleaned_parts:
        return "/"
    flat_name = "-".join(cleaned_parts)
    return f"/pages/{quote(flat_name, safe='')}.html"


def _asset_prefix_for_href(rel_href: str) -> str:
    path = str(rel_href or "/").strip()
    if path in ("", "/"):
        return "./"
    parts = [p for p in path.lstrip("/").split("/") if p]
    depth = max(0, len(parts) - 1)
    return "../" * depth or "./"


def _truncate_meta(text: str, max_len: int = 160) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if len(raw) <= max_len:
        return raw
    cut = raw.rfind(" ", 0, max_len)
    if cut < max_len // 2:
        cut = max_len
    return raw[:cut].rstrip(" ,.;:") + "..."


def _page_meta(page: dict) -> tuple[str, str, str]:
    slug = str(page.get("slug") or "").strip()
    title = str(page.get("title") or slug or "Pinball CTL Docs").strip()
    excerpt = str(page.get("excerpt") or "").strip()
    plain = str(page.get("plain") or "").strip()
    description = _truncate_meta(excerpt or plain or f"Documentation page: {title}")

    base_keywords = [
        "Pinball CTL",
        "pinball docs",
        "pinball controller",
        "ESP32",
        "Raspberry Pi",
        "rules engine",
        "lighting",
        "playfield",
        "firmware",
        "hardware",
    ]
    tokens = [title]
    parts = [p for p in slug.split("/") if p]
    if parts:
        section = parts[0].replace("-", " ")
        section = re.sub(r"^\s*\d+\s*", "", section).strip()
        if section:
            tokens.append(section)
    seen: set[str] = set()
    keywords: list[str] = []
    for item in base_keywords + tokens:
        k = re.sub(r"\s+", " ", str(item or "").strip())
        low = k.lower()
        if not k or low in seen:
            continue
        seen.add(low)
        keywords.append(k)
    return (title, description, ", ".join(keywords))


def _collect_manifest_icons(root: Path) -> list[dict]:
    icons: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def _add_icon(src: str, media_type: str, sizes: str | None, purpose: str | None) -> None:
        key = (src, media_type, purpose or "")
        if key in seen:
            return
        seen.add(key)
        icon: dict[str, str] = {"src": src, "type": media_type}
        if sizes:
            icon["sizes"] = sizes
        if purpose:
            icon["purpose"] = purpose
        icons.append(icon)

    favicon_svg = root / "assets" / "img" / "favicon.svg"
    if favicon_svg.exists():
        _add_icon("/assets/img/favicon.svg", "image/svg+xml", "any", "any")
        _add_icon("/assets/img/favicon.svg", "image/svg+xml", "any", "maskable")

    assets_root = root / "assets"
    if assets_root.exists():
        for img in sorted(assets_root.rglob("*")):
            if not img.is_file():
                continue
            stem_low = img.stem.lower()
            if "icon" not in stem_low and "favicon" not in stem_low:
                continue
            media_type = _guess_media_type(img)
            if not media_type:
                continue
            rel = "/" + img.relative_to(root).as_posix()
            size_match = _ICON_NAME_SIZE_RE.search(img.stem)
            sizes = f"{size_match.group(1)}x{size_match.group(2)}" if size_match else ("any" if media_type == "image/svg+xml" else None)
            _add_icon(rel, media_type, sizes, "any")

    return icons


def _collect_manifest_screenshots(root: Path) -> list[dict]:
    screenshots: list[dict] = []
    seen_src: set[str] = set()
    scan_dirs = (root / "assets" / "screenshots", root / "media")

    for base in scan_dirs:
        if not base.exists():
            continue
        for img in sorted(base.rglob("*")):
            if not img.is_file():
                continue
            if img.name.startswith("."):
                continue
            media_type = _guess_media_type(img)
            if not media_type:
                continue
            if base.name == "media" and not img.name.lower().startswith("screenshot-"):
                continue
            rel = "/" + img.relative_to(root).as_posix()
            if rel in seen_src:
                continue
            seen_src.add(rel)
            dims = _image_size(img)
            screenshots.append(
                {
                    "src": rel,
                    "type": media_type,
                    "sizes": f"{dims[0]}x{dims[1]}" if dims is not None else "1x1",
                    "label": _human_label_from_name(img.name),
                    "form_factor": "wide",
                }
            )

    return screenshots


def _build_manifest_shortcuts(default_slug: str, pages: list[dict]) -> list[dict]:
    by_slug = {str(p.get("slug") or ""): p for p in pages}
    preferred = [
        default_slug,
        "1-user-guide/1-getting-started",
        "1-user-guide/7.1-rules",
        "2-technical-notes/bridge-protocol",
    ]
    selected: list[str] = []
    for slug in preferred:
        s = str(slug or "")
        if not s or s not in by_slug or s in selected:
            continue
        selected.append(s)
    for p in pages:
        if len(selected) >= 4:
            break
        slug = str(p.get("slug") or "")
        if slug and slug not in selected:
            selected.append(slug)

    shortcuts: list[dict] = []
    for slug in selected[:4]:
        page = by_slug.get(slug) or {}
        title = str(page.get("title") or slug).strip()
        label = title[:28].strip() or "Doc"
        shortcuts.append(
            {
                "name": title,
                "short_name": label,
                "description": f"Open {title}",
                "url": _slug_to_page_href(slug),
            }
        )
    return shortcuts


def _build_manifest_payload(root: Path, default_slug: str, pages: list[dict]) -> dict:
    site_url = "https://docs.pinballctl.com"
    icons = _collect_manifest_icons(root)
    shortcuts = _build_manifest_shortcuts(default_slug, pages)

    for icon in icons:
        src = str(icon.get("src") or "")
        if src.startswith("/"):
            icon["src"] = f"{site_url}{src}"
    for shortcut in shortcuts:
        url = str(shortcut.get("url") or "")
        if url.startswith("/"):
            shortcut["url"] = f"{site_url}{url}"

    payload: dict = {
        "id": f"{site_url}/",
        "name": "Pinball CTL Documentation",
        "short_name": "Pinball CTL Docs",
        "description": "Official Pinball CTL documentation with setup guides, feature walkthroughs, screenshots, and troubleshooting.",
        "lang": "en-GB",
        "dir": "ltr",
        "start_url": f"{site_url}/#doc=README",
        "scope": f"{site_url}/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone", "minimal-ui", "browser"],
        "orientation": "any",
        "background_color": "#071019",
        "theme_color": "#071019",
        "categories": ["documentation", "developer", "utilities", "education", "technology"],
        "prefer_related_applications": False,
        "related_applications": [],
        "launch_handler": {"client_mode": ["navigate-existing", "auto"]},
        "handle_links": "preferred",
        "icons": icons,
        "shortcuts": shortcuts,
    }
    return payload


def _slug_for(md_path: Path, root: Path) -> str:
    return md_path.relative_to(root).with_suffix("").as_posix()


def _scan_pages(root: Path) -> list[dict]:
    pages = []
    if not root.exists():
        return pages
    for md_path in sorted(root.rglob("*.md")):
        slug = _slug_for(md_path, root)
        pages.append(
            {
                "slug": slug,
                "path": md_path.relative_to(root).as_posix(),
                "title": _title_from_markdown(md_path),
                "order": _ordered_name(md_path.stem)[0],
                "md_path": md_path,
            }
        )
    return pages


def _insert_node(tree: dict, rel_parts: list[str], page: dict) -> None:
    node = tree
    for part in rel_parts[:-1]:
        children = node.setdefault("children", {})
        part_order, part_name = _ordered_name(part)
        node = children.setdefault(
            part,
            {
                "type": "folder",
                "name": part_name.title(),
                "order": part_order,
                "children": {},
            },
        )
    file_nodes = node.setdefault("pages", [])
    file_nodes.append(
        {
            "type": "page",
            "title": page["title"],
            "slug": page["slug"],
            "order": page.get("order", 10_000),
        }
    )


def _normalize_tree(node: dict, path_prefix: str = "") -> list[dict]:
    def _page_sort_key(page: dict) -> tuple[int, int, str]:
        slug = str(page.get("slug", "")).strip("/").lower()
        leaf = slug.split("/")[-1] if slug else ""
        is_overview = leaf in ("readme", "index")
        order = int(page.get("order", 10_000))
        title = str(page.get("title", "")).lower()
        return (0 if is_overview else 1, order, title)

    pages = sorted(node.get("pages", []), key=_page_sort_key)

    folders = []

    def _folder_sort_key(item: tuple[str, dict]) -> tuple[int, str]:
        key, child = item
        return (int(child.get("order", 10_000)), key.lower())

    for key, child in sorted(node.get("children", {}).items(), key=_folder_sort_key):
        child_path = f"{path_prefix}/{key}".strip("/")
        folders.append(
            {
                "type": "folder",
                "name": child.get("name", key),
                "path": child_path,
                "children": _normalize_tree(child, child_path),
            }
        )
    return pages + folders


def _plain_text_from_markdown(md: str) -> str:
    text = md.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove raw HTML blocks/tags from preview/search text (for example inline <img ...>).
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"^\s*\[[^\]]+\]:\s+\S+.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\b[\w./-]+\.md\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(\*\*|__|\*|_)", "", text)
    text = re.sub(r"[\[\]\(\)]", " ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_excerpt(content: str, query: str = "") -> str:
    plain = _plain_text_from_markdown(content)
    if not plain:
        return ""
    if not query:
        lead = plain[:220]
        if len(lead) < len(plain):
            cut = lead.rfind(" ")
            if cut > 100:
                lead = lead[:cut]
            lead = f"{lead.strip()}..."
        return lead.strip()

    q = (query or "").strip().lower()
    low = plain.lower()
    i = low.find(q)
    if i < 0:
        return _extract_excerpt(content, "")
    start = max(0, i - 90)
    end = min(len(plain), i + max(70, len(q)) + 90)
    if start > 0:
        ws = plain.rfind(" ", 0, start)
        if ws > 0:
            start = ws + 1
    if end < len(plain):
        ws = plain.find(" ", end)
        if ws > 0:
            end = ws
    snippet = plain[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(plain):
        snippet = f"{snippet}..."
    return snippet


def _safe_resolve(base: Path, rel_path: str) -> Path | None:
    try:
        resolved = (base / rel_path).resolve()
    except Exception:
        return None
    try:
        resolved.relative_to(base)
    except Exception:
        return None
    return resolved


def _parse_tag_attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, value in re.findall(r'([:@\w-]+)\s*=\s*(".*?"|\'.*?\'|[^\s>]+)', tag, re.DOTALL):
        val = value.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        attrs[key.lower()] = html.unescape(val)
    return attrs


def _rewrite_links(html_text: str, doc_md: Path, pages_root: Path, assets_root: Path) -> str:
    doc_dir = doc_md.parent

    def _replace(match: re.Match) -> str:
        attr = match.group(1)
        url = (match.group(2) or "").strip()
        if not url:
            return match.group(0)

        if url.startswith("/api/manual/assets/"):
            rel = url.removeprefix("/api/manual/assets/")
            return f'{attr}="./assets/{html.escape(rel, quote=True)}"'

        if url.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return match.group(0)

        if url.startswith("/"):
            return match.group(0)

        target = _safe_resolve(doc_dir, url)
        if target is None:
            return match.group(0)

        if target.suffix.lower() == ".md" and target.exists():
            slug = _slug_for(target, pages_root)
            href = _slug_to_page_href(slug)
            return f'{attr}="{html.escape(href, quote=True)}" data-doc-slug="{html.escape(slug, quote=True)}"'

        if target.exists() and target.is_file():
            if target.is_relative_to(assets_root):
                rel = target.relative_to(assets_root).as_posix()
                return f'{attr}="./assets/{quote(rel, safe="/")}"'
            try:
                rel_page = target.relative_to(pages_root).as_posix()
                return f'{attr}="./pages/{quote(rel_page, safe="/")}"'
            except Exception:
                return match.group(0)

        return match.group(0)

    rewritten = re.sub(r'(href|src)="([^"]+)"', _replace, html_text)
    # Strip screenshot build directives from compiled output.
    rewritten = re.sub(
        r"""\sdata-source\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""",
        "",
        rewritten,
        flags=re.IGNORECASE,
    )
    # Remove legacy inline image sizing from authored HTML; docs.css owns defaults.
    def _clean_style(match: re.Match) -> str:
        quote = match.group(1)
        style = match.group(2)
        style = re.sub(r"max-width\s*:\s*800px\s*;?", "", style, flags=re.IGNORECASE)
        style = re.sub(r"\s*;\s*;\s*", "; ", style)
        style = re.sub(r"\s{2,}", " ", style).strip()
        style = style.strip(";").strip()
        if not style:
            return ""
        if not style.endswith(";"):
            style = f"{style};"
        return f" style={quote}{style}{quote}"

    rewritten = re.sub(r"""\sstyle=(["'])(.*?)\1""", _clean_style, rewritten, flags=re.IGNORECASE)

    docs_root = assets_root.parent

    def _set_src(tag: str, new_src: str) -> str:
        def _replace_src(match: re.Match) -> str:
            quote_ch = match.group(1)
            return f"src={quote_ch}{html.escape(new_src, quote=True)}{quote_ch}"

        return re.sub(
            r"""\bsrc\s*=\s*(["']).*?\1""",
            _replace_src,
            tag,
            count=1,
            flags=re.IGNORECASE,
        )

    def _append_attr(tag: str, name: str, value: str) -> str:
        if re.search(fr"""\b{name}\s*=""", tag, flags=re.IGNORECASE):
            return tag
        return re.sub(r"\s*/?>$", f' {name}="{value}"\\g<0>', tag, count=1)

    def _enhance_img(match: re.Match) -> str:
        tag = match.group(0)
        attrs = _parse_tag_attrs(tag)
        src = str(attrs.get("src", "")).strip()
        if not src:
            return tag

        if re.search(r"screenshot-[^/?#]+\.png(?:[?#].*)?$", src, flags=re.IGNORECASE):
            src = re.sub(r"\.png(?=([?#].*)?$)", ".webp", src, flags=re.IGNORECASE)
            tag = _set_src(tag, src)

        tag = _append_attr(tag, "loading", "lazy")
        tag = _append_attr(tag, "decoding", "async")

        rel: str | None = None
        if src.startswith("./"):
            rel = src[2:]
        elif src.startswith("/"):
            rel = src[1:]

        if rel:
            img_path = _safe_resolve(docs_root, rel)
            if img_path and img_path.is_file():
                dims = _image_size(img_path)
                if dims:
                    tag = _append_attr(tag, "width", str(dims[0]))
                    tag = _append_attr(tag, "height", str(dims[1]))
        return tag

    rewritten = re.sub(r"<img\b[^>]*>", _enhance_img, rewritten, flags=re.IGNORECASE)
    return rewritten


def _render_markdown(md_text: str, md_path: Path, pages_root: Path, assets_root: Path) -> str:
    if _markdown is not None:
        rendered = _markdown.markdown(md_text, extensions=["fenced_code", "tables", "toc"])
        return _rewrite_links(rendered, md_path, pages_root, assets_root)

    def _inline(s: str) -> str:
        out = html.escape(s)
        out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
        out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
        out = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", out)
        out = re.sub(
            r"!\[([^\]]*)\]\(([^)]+)\)",
            lambda m: f'<img alt="{html.escape(m.group(1), quote=True)}" src="{html.escape(m.group(2), quote=True)}">',
            out,
        )
        out = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
            out,
        )
        return out

    lines = md_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    code_lines: list[str] = []
    in_raw_html = False
    raw_html_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("```"):
            flush_paragraph()
            close_list()
            if not in_code:
                in_code = True
                code_lines = []
            else:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                in_code = False
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if in_raw_html:
            raw_html_lines.append(line)
            if ">" in line:
                flush_paragraph()
                close_list()
                out.append("\n".join(raw_html_lines))
                in_raw_html = False
                raw_html_lines = []
            continue

        if not line.strip():
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            continue

        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(bullet.group(1).strip())}</li>")
            continue

        ordered = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if ordered:
            flush_paragraph()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(ordered.group(1).strip())}</li>")
            continue

        if line.strip().startswith("<") and line.strip().endswith(">"):
            flush_paragraph()
            close_list()
            out.append(line)
            continue

        if line.strip().startswith("<") and not line.strip().endswith(">"):
            in_raw_html = True
            raw_html_lines = [line]
            continue

        paragraph.append(line.strip())

    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    if in_raw_html and raw_html_lines:
        out.append("\n".join(raw_html_lines))
    flush_paragraph()
    close_list()
    return _rewrite_links("".join(out), md_path, pages_root, assets_root)


def _build_tree(pages: list[dict]) -> list[dict]:
    raw_tree: dict = {"children": {}, "pages": []}
    for page in pages:
        rel = Path(page["path"])
        _insert_node(raw_tree, list(rel.parts), page)
    return _normalize_tree(raw_tree)


def _minify_css(css_text: str) -> str:
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    css_text = re.sub(r"\s+", " ", css_text)
    css_text = re.sub(r"\s*([{}:;,>])\s*", r"\1", css_text)
    css_text = re.sub(r";}", "}", css_text)
    return css_text.strip()


def _load_inline_css(style_path: Path, docs_css_path: Path) -> str:
    return _minify_css(
        style_path.read_text(encoding="utf-8")
        + "\n"
        + docs_css_path.read_text(encoding="utf-8")
    )


def _render_index_html(
    embedded_data_json: str,
    updated_label: str,
    generated_at_iso: str,
    inline_css: str,
    title: str = "Pinball CTL Docs | Build, Test, and Run Homebrew Pinball",
    description: str | None = None,
    keywords: str | None = None,
    og_type: str = "website",
    canonical_url: str | None = None,
    initial_article_html: str = "",
    include_inline_data: bool = True,
    asset_prefix: str = "./",
) -> str:
    page_description = description or (
        "Official Pinball CTL documentation with setup guides, feature walkthroughs, "
        "screenshots, and troubleshooting."
    )
    page_keywords = keywords or (
        "Pinball CTL, pinball docs, pinball controller, ESP32, Raspberry Pi, "
        "rules engine, lighting, playfield, firmware, hardware"
    )
    site_url = "https://docs.pinballctl.com/"
    org_url = "https://www.pinballctl.com/"
    og_image_url = f"{site_url}assets/img/favicon.svg"
    page_canonical = canonical_url or site_url
    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{org_url}#organization",
                "name": "Pinball CTL",
                "url": org_url,
                "logo": og_image_url,
            },
            {
                "@type": "WebSite",
                "@id": f"{site_url}#website",
                "url": site_url,
                "name": "Pinball CTL Docs",
                "description": page_description,
                "inLanguage": "en",
                "publisher": {"@id": f"{org_url}#organization"},
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": f"{site_url}#doc=README&q={{search_term_string}}",
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@type": "WebPage",
                "@id": f"{page_canonical}#webpage",
                "url": page_canonical,
                "name": title,
                "description": page_description,
                "isPartOf": {"@id": f"{site_url}#website"},
                "about": {"@id": f"{org_url}#organization"},
                "inLanguage": "en",
                "dateModified": generated_at_iso,
                "datePublished": generated_at_iso,
            },
        ],
    }
    schema_json = json.dumps(schema_graph, ensure_ascii=False, separators=(",", ":"))
    schema_json = schema_json.replace("</", "<\\/")
    inline_data_block = (
        f'<script id="site-data-inline" type="application/json">{embedded_data_json}</script>\n  '
        if include_inline_data
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>{html.escape(title)}</title>
  <meta name=\"description\" content=\"{html.escape(page_description, quote=True)}\">
  <meta name=\"keywords\" content=\"{html.escape(page_keywords, quote=True)}\">
  <meta name=\"author\" content=\"Pinball CTL\">
  <meta name=\"robots\" content=\"index,follow,max-image-preview:large\">
  <meta name=\"theme-color\" content=\"#071019\">
  <meta name=\"theme-color\" media=\"(prefers-color-scheme: dark)\" content=\"#071019\">
  <meta name=\"theme-color\" media=\"(prefers-color-scheme: light)\" content=\"#102236\">
  <meta name=\"application-name\" content=\"Pinball CTL Docs\">
  <meta name=\"apple-mobile-web-app-capable\" content=\"yes\">
  <meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">
  <link rel=\"canonical\" href=\"{html.escape(page_canonical, quote=True)}\">
  <link rel=\"icon\" type=\"image/svg+xml\" href=\"{asset_prefix}assets/img/favicon.svg\">
  <link rel=\"shortcut icon\" href=\"{asset_prefix}assets/img/favicon.svg\">
  <meta property=\"og:type\" content=\"{html.escape(og_type, quote=True)}\">
  <meta property=\"og:locale\" content=\"en_GB\">
  <meta property=\"og:site_name\" content=\"Pinball CTL Docs\">
  <meta property=\"og:title\" content=\"{html.escape(title, quote=True)}\">
  <meta property=\"og:description\" content=\"{html.escape(page_description, quote=True)}\">
  <meta property=\"og:url\" content=\"{html.escape(page_canonical, quote=True)}\">
  <meta property=\"og:image\" content=\"{og_image_url}\">
  <meta property=\"og:image:secure_url\" content=\"{og_image_url}\">
  <meta property=\"og:image:type\" content=\"image/svg+xml\">
  <meta property=\"og:image:width\" content=\"64\">
  <meta property=\"og:image:height\" content=\"64\">
  <meta property=\"og:image:alt\" content=\"Pinball CTL Docs icon\">
  <meta property=\"og:updated_time\" content=\"{html.escape(generated_at_iso, quote=True)}\">
  <meta name=\"twitter:card\" content=\"summary\">
  <meta name=\"twitter:site\" content=\"@pinballctl\">
  <meta name=\"twitter:title\" content=\"{html.escape(title, quote=True)}\">
  <meta name=\"twitter:description\" content=\"{html.escape(page_description, quote=True)}\">
  <meta name=\"twitter:image\" content=\"{og_image_url}\">
  <meta name=\"twitter:image:alt\" content=\"Pinball CTL Docs icon\">
  <link rel=\"manifest\" href=\"{asset_prefix}site.webmanifest\">
  <link rel=\"preconnect\" href=\"https://www.googletagmanager.com\" crossorigin>
  <link rel=\"dns-prefetch\" href=\"//www.googletagmanager.com\">
  <style>{inline_css}</style>
  <!-- Google tag (gtag.js) -->
  <script async src=\"https://www.googletagmanager.com/gtag/js?id=G-MH2T2SDF1P\"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-MH2T2SDF1P');
  </script>
  <script type=\"application/ld+json\">{schema_json}</script>
</head>
<body>
  <header class=\"site-header\">
    <a class=\"brand\" href=\"{asset_prefix}index.html\" aria-label=\"Pinball CTL docs home\">
      <span class=\"brand-dot\" aria-hidden=\"true\"></span>
      <span>Pinball CTL Docs</span>
    </a>
    <div class=\"header-actions\">
      <button id=\"docs-mobile-search-toggle\" class=\"docs-mobile-search-toggle\" type=\"button\" aria-label=\"Open search\">
        <svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\">
          <path d=\"M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-3.6-3.6\"/>
        </svg>
      </button>
      <button class=\"menu-toggle\" type=\"button\" aria-expanded=\"false\" aria-label=\"Toggle navigation\">
        <span></span><span></span><span></span>
      </button>
    </div>
    <nav class=\"site-nav\" aria-label=\"Main navigation\">
      <span class=\"docs-updated\">Updated {html.escape(updated_label)}</span>
      <div id=\"docs-mobile-nav-list\" class=\"docs-mobile-nav-list\"></div>
      <a href=\"https://pinballctl.com\" class=\"nav-link website-link\">
        <svg class=\"website-link__icon\" viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\">
          <path d=\"M3 12h18M12 3a16 16 0 0 1 0 18M12 3a16 16 0 0 0 0 18M4.5 7.5h15M4.5 16.5h15\"/>
        </svg>
        <span>Pinball CTL Website</span>
      </a>
    </nav>
  </header>

  <main id=\"top\" class=\"docs-shell\">
    <section class=\"section\">
      <p class=\"kicker hero-kicker\">Documentation</p>
      <h1>Pinball CTL Documentation</h1>
      <p class=\"lead\">Find setup guides, feature walkthroughs, and troubleshooting help for Pinball CTL.</p>

      <div class=\"docs-toolbar\">
        <button class=\"docs-sidebar-toggle\" type=\"button\" data-docs-sidebar-toggle aria-expanded=\"false\" aria-controls=\"docs-sidebar\">Docs Menu</button>
        <input type=\"search\" id=\"docs-search\" data-docs-search=\"desktop\" class=\"docs-search-input docs-search-desktop\" placeholder=\"Search docs...\" />
        <span id=\"docs-search-status\" data-docs-search-status=\"desktop\" class=\"docs-search-status docs-search-status-desktop\"></span>
      </div>
      <div id=\"docs-search-results-top\" class=\"docs-search-results docs-search-results-top hidden\"></div>

      <div class=\"docs-layout\">
        <aside id=\"docs-sidebar\" class=\"docs-sidebar\">
          <div class=\"docs-sidebar-head\">
            <span class=\"docs-sidebar-title\">Docs Menu</span>
            <button id=\"docs-sidebar-close\" class=\"docs-sidebar-close\" type=\"button\" aria-label=\"Close docs menu\">Close</button>
          </div>
          <div id=\"docs-bookmarks-wrap\" class=\"docs-bookmarks-wrap hidden\">
            <div class=\"docs-bookmarks-title\">Bookmarks</div>
            <div id=\"docs-bookmarks\" class=\"docs-bookmarks\"></div>
          </div>
          <div id=\"docs-tree\" class=\"docs-tree\"></div>
        </aside>

        <article class=\"docs-content\">
          <button id=\"docs-bookmark-toggle\" class=\"docs-bookmark-toggle docs-bookmark-toggle-card\" type=\"button\" aria-pressed=\"false\" aria-label=\"Bookmark current page\" title=\"Bookmark current page\">
            <svg class=\"docs-bookmark-icon\" viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\">
              <path d=\"M7 3h10a1 1 0 0 1 1 1v17l-6-3.8L6 21V4a1 1 0 0 1 1-1z\"></path>
            </svg>
          </button>
          <div class=\"doc-panel\" id=\"docs-article\">{initial_article_html}</div>
        </article>
      </div>
    </section>
  </main>

  <footer class=\"site-footer\">
    <div class=\"site-footer__inner\">
      <p class=\"site-footer__copy\">&copy; 2026 Pinball CTL. All rights reserved.</p>
      <nav class=\"site-footer__nav\" aria-label=\"Footer links\">
        <a href=\"https://www.pinballctl.com/privacy.html\" target=\"_blank\" rel=\"noopener noreferrer\">Privacy</a>
        <a href=\"https://www.pinballctl.com/terms.html\" target=\"_blank\" rel=\"noopener noreferrer\">Terms</a>
        <a href=\"https://www.pinballctl.com/contact.html\" target=\"_blank\" rel=\"noopener noreferrer\">Contact</a>
      </nav>
    </div>
  </footer>

  <div id=\"img-modal\" class=\"img-modal\" aria-hidden=\"true\" role=\"dialog\" aria-label=\"Screenshot preview\">
    <div class=\"img-modal__backdrop\"></div>
    <div class=\"img-modal__body\">
      <button class=\"img-modal__close\" aria-label=\"Close preview\">Close</button>
      <img src=\"\" alt=\"Screenshot preview\" class=\"img-modal__img\">
    </div>
  </div>
  <div id=\"docs-search-modal\" class=\"docs-search-modal\" aria-hidden=\"true\" role=\"dialog\" aria-label=\"Search docs\">
    <div class=\"docs-search-modal__backdrop\"></div>
    <div class=\"docs-search-modal__panel\">
      <div class=\"docs-search-modal__head\">
        <div class=\"docs-search-modal__title\">Search docs</div>
        <button id=\"docs-search-modal-close\" class=\"docs-search-modal__close\" type=\"button\" aria-label=\"Close search\">Close</button>
      </div>
      <input type=\"search\" id=\"docs-search-modal-input\" data-docs-search=\"modal\" class=\"docs-search-input\" placeholder=\"Search docs...\" />
      <span id=\"docs-search-status-modal\" data-docs-search-status=\"modal\" class=\"docs-search-status\"></span>
      <div id=\"docs-search-results-modal\" class=\"docs-search-results docs-search-results-modal\"></div>
    </div>
  </div>

  {inline_data_block}<script src=\"{asset_prefix}site-data.js\"></script>\n  <script src=\"{asset_prefix}assets/js/main.js\" defer></script>\n  <script src=\"{asset_prefix}assets/js/components.js\" defer></script>
</body>
</html>
"""


def _render_404_html(updated_label: str, inline_css: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Page Not Found | Pinball CTL Docs</title>
  <meta name=\"description\" content=\"The requested documentation page was not found.\">
  <meta name=\"robots\" content=\"noindex,follow\">
  <meta name=\"theme-color\" content=\"#071019\">
  <link rel=\"icon\" type=\"image/svg+xml\" href=\"./assets/img/favicon.svg\">
  <link rel=\"manifest\" href=\"./site.webmanifest\">
  <link rel=\"preconnect\" href=\"https://www.googletagmanager.com\" crossorigin>
  <link rel=\"dns-prefetch\" href=\"//www.googletagmanager.com\">
  <style>{inline_css}</style>
  <!-- Google tag (gtag.js) -->
  <script async src=\"https://www.googletagmanager.com/gtag/js?id=G-MH2T2SDF1P\"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-MH2T2SDF1P');
  </script>
  <style>
    body {{
      background:
        radial-gradient(1200px 500px at 8% -2%, rgba(35, 209, 139, 0.15), transparent 55%),
        linear-gradient(180deg, #050b13 0%, #071019 45%, #081427 100%);
      background-repeat: no-repeat;
      background-size: 100% 100%;
      min-height: 100vh;
    }}
    .error-actions {{
      margin-top: 1rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
    }}
    .error-cta {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 2.5rem;
      padding: 0.62rem 1rem;
      border-radius: 0.78rem;
      border: 1px solid rgba(136, 163, 198, 0.35);
      background: linear-gradient(180deg, rgba(17, 36, 58, 0.96), rgba(10, 24, 39, 0.96));
      color: #eef5ff;
      font-weight: 700;
      letter-spacing: 0.01em;
      text-decoration: none !important;
      box-shadow: 0 10px 22px rgba(2, 8, 14, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.06);
      transition: transform 120ms ease, border-color 140ms ease, box-shadow 140ms ease, background 140ms ease;
    }}
    .error-cta:hover {{
      border-color: rgba(150, 219, 255, 0.55);
      background: linear-gradient(180deg, rgba(22, 46, 72, 0.98), rgba(12, 30, 47, 0.98));
      color: #ffffff;
      text-decoration: none !important;
      transform: translateY(-1px);
      box-shadow: 0 14px 26px rgba(2, 8, 14, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }}
    .error-cta.primary {{
      border-color: rgba(69, 214, 160, 0.58);
      background: linear-gradient(145deg, #2bd69c, #15b58f);
      color: #032018;
      box-shadow: 0 12px 24px rgba(21, 181, 143, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }}
    .error-cta.primary:hover {{
      border-color: rgba(108, 240, 191, 0.72);
      background: linear-gradient(145deg, #39e0a9, #19c39a);
      color: #022117;
      box-shadow: 0 16px 30px rgba(25, 195, 154, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.24);
    }}
  </style>
</head>
<body>
  <header class=\"site-header\">
    <a class=\"brand\" href=\"./index.html\" aria-label=\"Pinball CTL docs home\">
      <span class=\"brand-dot\" aria-hidden=\"true\"></span>
      <span>Pinball CTL Docs</span>
    </a>
    <nav class=\"site-nav\" aria-label=\"Main navigation\">
      <span class=\"docs-updated\">Updated {html.escape(updated_label)}</span>
      <a href=\"https://pinballctl.com\" class=\"nav-link website-link\">
        <svg class=\"website-link__icon\" viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\">
          <path d=\"M3 12h18M12 3a16 16 0 0 1 0 18M12 3a16 16 0 0 0 0 18M4.5 7.5h15M4.5 16.5h15\"/>
        </svg>
        <span>Pinball CTL Website</span>
      </a>
    </nav>
  </header>

  <main class=\"docs-shell\">
    <section class=\"section\">
      <div class=\"doc-panel\">
        <p class=\"kicker hero-kicker\">Error 404</p>
        <h1>Page Not Found</h1>
        <p class=\"lead\">The page you requested does not exist in Pinball CTL Docs.</p>
        <div class=\"error-actions\">
          <a class=\"error-cta primary\" href=\"./index.html\">Docs Home</a>
          <a class=\"error-cta\" href=\"https://pinballctl.com\" target=\"_blank\" rel=\"noopener noreferrer\">Website</a>
          <a class=\"error-cta\" href=\"https://github.com/pinballctl/pinballctl\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub Project</a>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_sitemap_xml(site_url: str, urls: list[str], generated_at_iso: str) -> str:
    base = site_url.rstrip("/")
    lastmod = generated_at_iso.split("T", 1)[0]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in urls:
        loc = f"{base}{path if path.startswith('/') else '/' + path}"
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(loc)}</loc>")
        lines.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _purge_generated_page_html(pages_root: Path) -> int:
    removed = 0
    for html_file in pages_root.rglob("*.html"):
        try:
            html_file.unlink()
            removed += 1
        except Exception:
            continue
    return removed


def build(root: Path, website_root: Path | None = None) -> None:
    source_root = root / "docs"
    pages_root = root / "pages"
    assets_root = root / "assets"
    out_html = root / "index.html"
    out_404 = root / "404.html"
    out_data = root / "site-data.json"
    out_data_js = root / "site-data.js"
    out_manifest = root / "site.webmanifest"
    out_sitemap = root / "sitemap.xml"
    css_dir = root / "assets" / "css"
    js_dir = root / "assets" / "js"
    out_style = css_dir / "style.css"
    out_docs_css = css_dir / "docs.css"
    out_main_js = js_dir / "main.js"
    out_components_js = js_dir / "components.js"

    if not source_root.exists():
        raise FileNotFoundError(f"docs directory not found: {source_root}")
    if not assets_root.exists():
        raise FileNotFoundError(f"assets directory not found: {assets_root}")

    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)

    if website_root is not None:
        website_style = website_root / "style.css"
        if website_style.exists():
            out_style.write_text(website_style.read_text(encoding="utf-8"), encoding="utf-8")

    if not out_docs_css.exists():
        raise FileNotFoundError(f"docs.css missing: {out_docs_css}")
    if not out_main_js.exists():
        raise FileNotFoundError(f"main.js missing: {out_main_js}")
    if not out_components_js.exists():
        raise FileNotFoundError(f"components.js missing: {out_components_js}")
    inline_css = _load_inline_css(out_style, out_docs_css)

    purged_pages = _purge_generated_page_html(pages_root)

    pages = _scan_pages(source_root)
    if not pages:
        raise RuntimeError("No markdown files found under docs/")

    for page in pages:
        md_text = page["md_path"].read_text(encoding="utf-8")
        page["html"] = _render_markdown(md_text, page["md_path"], source_root, assets_root)
        page["plain"] = _plain_text_from_markdown(md_text)
        page["excerpt"] = _extract_excerpt(md_text)
        page["href"] = _slug_to_page_href(str(page.get("slug") or ""))
        page.pop("md_path", None)

    tree = _build_tree(pages)
    default = next((p for p in pages if p["slug"] == "README"), None)
    if default is None:
        default = next((p for p in pages if p["slug"].split("/")[-1].lower() == "readme"), None)
    default_slug = (default or pages[0])["slug"]

    build_now = datetime.now(timezone.utc)
    payload = {
        "generated_at": build_now.isoformat(),
        "default_slug": default_slug,
        "tree": tree,
        "pages": pages,
    }

    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    out_data.write_text(payload_json, encoding="utf-8")
    out_data_js.write_text(f"window.__PINBALLCTL_SITE_DATA__={payload_json};\n", encoding="utf-8")
    updated_label = build_now.strftime("%Y-%m-%d %H:%M UTC")
    site_url = "https://docs.pinballctl.com/"
    out_html.write_text(
        _render_index_html(
            payload_json,
            updated_label,
            build_now.isoformat(),
            inline_css,
            canonical_url=site_url,
            initial_article_html=str((default or pages[0]).get("html") or ""),
            include_inline_data=False,
            asset_prefix="./",
        ),
        encoding="utf-8",
    )

    page_urls: list[str] = ["/", "/index.html"]
    for page in pages:
        slug = str(page.get("slug") or "").strip()
        if not slug:
            continue
        rel_href = str(page.get("href") or _slug_to_page_href(slug))
        page_urls.append(rel_href)
        if rel_href == "/":
            continue
        rel_file = rel_href.lstrip("/")
        out_page = root / rel_file
        out_page.parent.mkdir(parents=True, exist_ok=True)
        page_title_raw, page_desc, page_keywords = _page_meta(page)
        out_page.write_text(
            _render_index_html(
                "",
                updated_label,
                build_now.isoformat(),
                inline_css,
                title=f"{page_title_raw} | Pinball CTL Docs",
                description=page_desc,
                keywords=page_keywords,
                og_type="article",
                canonical_url=f"{site_url.rstrip('/')}{rel_href}",
                initial_article_html=str(page.get("html") or ""),
                include_inline_data=False,
                asset_prefix=_asset_prefix_for_href(rel_href),
            ),
            encoding="utf-8",
        )

    out_404.write_text(_render_404_html(updated_label, inline_css), encoding="utf-8")
    manifest_payload = _build_manifest_payload(root, default_slug, pages)
    out_manifest.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    unique_urls = list(dict.fromkeys(page_urls))
    out_sitemap.write_text(
        _render_sitemap_xml(site_url, unique_urls, build_now.isoformat()),
        encoding="utf-8",
    )

    print(f"Built {out_html}")
    print(f"Built {out_404}")
    print(f"Built {out_data} ({len(pages)} pages)")
    print(f"Built {out_data_js}")
    print(f"Built {out_sitemap} ({len(unique_urls)} URLs)")
    print(f"Purged {purged_pages} generated page HTML files under {pages_root}")
    print(
        f"Built {out_manifest} "
        f"({len(manifest_payload.get('icons', []))} icons, {len(manifest_payload.get('shortcuts', []))} shortcuts)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static docs site from markdown pages.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--website-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "website",
        help="Website repo root used to copy style.css for matching layout",
    )
    args = parser.parse_args()

    website_root = args.website_root if args.website_root.exists() else None
    build(args.root.resolve(), website_root=website_root)


if __name__ == "__main__":
    main()
