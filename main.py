#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_dotenv(path: Path = ROOT / '.env') -> None:
    """Минимальный загрузчик .env без внешней зависимости.

    Значения из окружения оператора имеют приоритет над .env. Это важно для
    live/testnet-запуска: случайный файл .env не должен перетереть секреты и
    флаги, заданные shell/service manager-ом.
    """

    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def run_python(args: list[str]) -> int:
    return subprocess.call([sys.executable, *args], cwd=ROOT)


def cmd_serve(args: argparse.Namespace) -> int:
    load_dotenv()
    if args.mode == 'testnet':
        os.environ.setdefault('BYBIT_TESTNET', 'true')
        os.environ.setdefault('APP_ENV', 'local')
    elif args.mode == 'live':
        os.environ.setdefault('BYBIT_TESTNET', 'false')
        os.environ.setdefault('APP_ENV', 'prod')
    import uvicorn

    uvicorn.run('app.main:app', host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    load_dotenv()
    return run_python(['scripts/validate_project.py'])


def cmd_preflight(args: argparse.Namespace) -> int:
    load_dotenv()
    if args.mode == 'testnet':
        os.environ.setdefault('BYBIT_TESTNET', 'true')
    elif args.mode == 'live':
        os.environ.setdefault('BYBIT_TESTNET', 'false')
        os.environ.setdefault('APP_ENV', 'prod')
    return run_python(['scripts/live_preflight.py'])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python main.py',
        description='Единая CLI-точка запуска Crypto Acceleration System 2026.',
    )
    sub = parser.add_subparsers(dest='command')

    serve = sub.add_parser('serve', help='Запустить FastAPI backend и dashboard.')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    serve.add_argument('--reload', action='store_true', help='Включить reload для локальной разработки.')
    serve.add_argument('--mode', choices=['local', 'testnet', 'live'], default='local', help='Контур запуска. Live не включает торговлю сам по себе.')
    serve.set_defaults(func=cmd_serve)

    validate = sub.add_parser('validate', help='Запустить compileall, pytest, static checks и secret scan.')
    validate.set_defaults(func=cmd_validate)

    preflight = sub.add_parser('preflight', help='Проверить live/testnet gates без отправки ордеров.')
    preflight.add_argument('--mode', choices=['testnet', 'live'], default='testnet')
    preflight.set_defaults(func=cmd_preflight)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(argv)
    if parsed.command is None:
        parsed = parser.parse_args(['serve'])
    return parsed.func(parsed)


if __name__ == '__main__':
    raise SystemExit(main())
