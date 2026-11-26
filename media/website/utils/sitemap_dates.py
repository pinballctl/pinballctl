"""Find the last committed changes to each page's content sources."""
from html import unescape
import json
from pathlib import PurePosixPath
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


class SitemapDates:
    def __init__(self, root, website):
        self.root = root
        self.website = website.relative_to(root)
        self.files = {}
        self.has_history = False
        if not shutil.which('git'):
            return
        history = self.git('rev-parse', '--is-shallow-repository', check=False)
        if history.returncode or history.stdout.strip() != 'false':
            return
        if self.git('rev-parse', '--verify', 'HEAD', check=False).returncode:
            return
        self.has_history = True
        listing = self.git('-c', 'core.quotepath=false', 'log', '--first-parent',
                           '--diff-merges=first-parent', '--no-renames', '--format=%cs',
                           '--name-only', '--', str(self.website)).stdout
        prefix = self.website.as_posix() + '/'
        date = None
        for line in listing.splitlines():
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', line):
                date = line
            elif date and line.startswith(prefix):
                self.files.setdefault(line.removeprefix(prefix), date)

    def git(self, *args, check=True):
        return subprocess.run(['git', '-C', str(self.root), *args],
                              text=True, capture_output=True, check=check)

    def records(self, source, index):
        """Date each record in a shared JSON file independently."""
        if not self.has_history:
            return {}
        path = (self.website / source).as_posix()
        history = self.git('log', '--first-parent', '--reverse', '--format=%H%x09%cs',
                           '--', path).stdout
        previous = {}
        dates = {}
        for line in history.splitlines():
            revision, date = line.split('\t')
            snapshot = self.git('show', f'{revision}:{path}', check=False)
            current = index(json.loads(snapshot.stdout)) if snapshot.returncode == 0 else {}
            for key, value in current.items():
                if key not in previous or previous[key] != value:
                    dates[key] = date
            previous = current
        return {key: dates[key] for key in previous}

    def page(self, body, sources, record_dates):
        dates = [self.files.get(source) for source in sources]
        dates.extend(record_dates)
        for value in re.findall(r'\b(?:src|srcset|poster)="([^"]+)"', body):
            for candidate in unescape(value).split(','):
                parts = urlsplit(candidate.strip().split()[0]) if candidate.strip() else None
                if parts is None or parts.scheme or parts.netloc:
                    continue
                path = unquote(parts.path)
                if path.startswith('/docs/media/') or path.startswith('/docs/assets/'):
                    path = '/assets' + path
                if path.startswith('/assets/'):
                    dates.append(self.files.get(PurePosixPath(path).as_posix().lstrip('/')))
        return max((date for date in dates if date), default=None)
