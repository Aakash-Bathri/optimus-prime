#!/usr/bin/env python3
"""Run inside the backend container. SQLite backup API includes committed WAL contents."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

folder = Path('/data/backups')
folder.mkdir(mode=0o700, exist_ok=True)
now = datetime.now(timezone.utc)
target = folder / (now.strftime('%Y%m%dT%H%M%SZ') + '.sqlite3')
with sqlite3.connect('file:/data/cloudpilot.sqlite3?mode=ro', uri=True) as source:
    with sqlite3.connect(target) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
for old in folder.glob('*.sqlite3'):
    if old.stat().st_mtime < (now - timedelta(days=7)).timestamp():
        old.unlink()
print('SQLite backup completed and integrity checked')
