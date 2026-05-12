import ast
from pathlib import Path


def test_strategies_do_not_import_execution():
    forbidden = ('app.execution', 'bybit_adapter', 'order_router', 'exchange_client')
    for path in Path('app/strategies').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            else:
                continue
            assert not any(any(f in name for f in forbidden) for name in names), (path, names)
