"""Markdown rendering shared by the GitHub Pages website."""
from __future__ import annotations
import html
import re
import struct
from pathlib import Path
from urllib.parse import quote, urlsplit
import markdown
from docs_navigation import REDIRECTS

_ORDERED_NAME_RE = re.compile(r"^\s*(\d+)\s*[-_. )]+\s*(.*)$")
_IMG_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".avif": "image/avif", ".svg": "image/svg+xml"}

def doc_url(slug):
    path = '/docs/' + ('' if slug == 'index' else slug.removesuffix('/index') + '/')
    return REDIRECTS.get(path, path)

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

        parts = urlsplit(url)
        target = (doc_dir / parts.path).resolve()
        if target.suffix.lower() == ".md":
            if not target.is_relative_to(pages_root.resolve()) or not target.is_file():
                raise ValueError(f'Missing documentation link in {doc_md}: {url}')
            slug = _slug_for(target, pages_root.resolve())
            href = doc_url(slug)
            if parts.fragment:
                href += '#' + parts.fragment
            return f'{attr}="{html.escape(href, quote=True)}"'

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


def _render_markdown(md_text, md_path, pages_root, assets_root):
    rendered = markdown.markdown(md_text, extensions=["fenced_code", "tables", "toc"])
    return _rewrite_links(rendered, md_path, pages_root, assets_root)
