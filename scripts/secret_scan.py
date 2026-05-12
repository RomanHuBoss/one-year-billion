from __future__ import annotations
import re
from pathlib import Path

PATTERNS = [
    re.compile(r'BYBIT_API_SECRET\s*=\s*[^\n]+'),
    re.compile(r'api[_-]?secret["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', re.I),
    re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', re.I),
]
ALLOW = {'.env.example', 'README.md'}
violations = []
for path in Path('.').rglob('*'):
    if not path.is_file() or '.venv' in path.parts or path.suffix in {'.png','.jpg','.zip','.pyc'}:
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
    raise SystemExit('Potential secrets found:\n' + '\n'.join(sorted(set(violations))))
print('OK: no obvious secrets')
