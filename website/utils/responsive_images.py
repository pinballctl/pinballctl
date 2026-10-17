"""Generate smaller screenshot variants in the build output, retaining originals for zoom."""
from html import escape, unescape
from pathlib import Path
import re
from PIL import Image


def responsive_images(html: str, output: Path) -> str:
    def replace(match):
        tag = match.group(0)
        src = re.search(r'\bsrc="([^"]+)"', tag)
        if not src:
            return tag
        url = unescape(src.group(1))
        if not url.startswith(('/assets/', '/docs/')):
            return tag
        source = output / url.lstrip('/')
        if source.suffix.lower() not in ('.webp', '.png', '.jpg', '.jpeg') or not source.is_file():
            return tag
        with Image.open(source) as image:
            width, height = image.size
            variants = []
            for size in (400, 800, 1200):
                if size >= width:
                    continue
                target = source.with_name(f'{source.stem}-{size}w.webp')
                if not target.exists():
                    image.resize((size, round(height * size / width)), Image.Resampling.LANCZOS).save(
                        target, 'WEBP', quality=82, method=6)
                variants.append(f'/{target.relative_to(output).as_posix()} {size}w')
        variants.append(f'{url} {width}w')
        # Wide hero screenshots use the page width; other screenshots occupy a column.
        wide = 'fetchpriority="high"' in tag
        sizes = '(max-width: 760px) calc(100vw - 44px), (max-width: 1440px) calc(100vw - 72px), 1368px' if wide else '(max-width: 760px) calc(100vw - 44px), (max-width: 1100px) calc(100vw - 100px), 720px'
        tag = re.sub(r'\s(?:width|height|srcset|sizes)="[^"]*"', '', tag)
        return tag[:-1] + f' width="{width}" height="{height}" srcset="{escape(", ".join(variants), quote=True)}" sizes="{sizes}" data-full-src="{escape(url, quote=True)}">'
    return re.sub(r'<img\b[^>]*>', replace, html)
