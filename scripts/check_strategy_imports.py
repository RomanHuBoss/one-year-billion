from __future__ import annotations
import ast
from pathlib import Path

FORBIDDEN = ('app.execution', 'execution', 'bybit_adapter', 'order_router', 'exchange_client')
failed = []
for path in Path('app/strategies').glob('*.py'):
    if path.name == '__init__.py':
        continue
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                names = [node.module or '']
            for name in names:
                if any(f in name for f in FORBIDDEN):
                    failed.append((str(path), name))
if failed:
    raise SystemExit(f'Forbidden strategy imports: {failed}')
print('OK: strategies have no direct execution/Bybit imports')
