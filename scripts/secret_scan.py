from __future__ import annotations
import re
from pathlib import Path

PATTERNS = [
    re.compile(r'BYBIT_API_SECRET\s*=\s*[^\n]+'),
    re.compile(r'api[_-]?secret["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', re.I),
    re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', re.I),
]
ALLOW = {'.env.example', 'README.md'}
SKIP_DIRS = {'.venv', '__pycache__', '.pytest_cache', '.git'}
SKIP_SUFFIXES = {'.png', '.jpg', '.jpeg', '.zip', '.pyc'}


def main() -> int:
    violations = []
    for path in Path('.').rglob('*'):
        if not path.is_file() or SKIP_DIRS & set(path.parts) or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        # Реальные секреты должны жить в server-side .env/secret store, но эти
        # файлы не входят в поставочный архив и не должны ломать локальный startup.
        if path.name.startswith('.env') and path.name != '.env.example':
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        for pattern in PATTERNS:
            if pattern.search(text) and path.name not in ALLOW:
                violations.append(str(path))
    if violations:
        print('Potential secrets found:\n' + '\n'.join(sorted(set(violations))))
        return 2
    print('OK: no obvious secrets')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
