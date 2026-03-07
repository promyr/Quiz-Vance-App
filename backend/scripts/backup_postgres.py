# -*- coding: utf-8 -*-
"""Backup do Postgres para rotina operacional do beta."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import os
import shutil
import subprocess
from pathlib import Path


def _run_backup(database_url: str, output_file: Path) -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump nao encontrado no PATH.")

    cmd = [
        pg_dump,
        f"--dbname={database_url}",
        "--no-owner",
        "--no-privileges",
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        assert proc.stdout is not None
        with gzip.open(output_file, "wb") as gz:
            shutil.copyfileobj(proc.stdout, gz)
        stderr = (proc.stderr.read() or b"").decode("utf-8", errors="ignore")
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"pg_dump falhou (exit={code}): {stderr.strip()}")


def _cleanup_old_backups(output_dir: Path, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    removed = 0
    for item in output_dir.glob("quiz_vance_backup_*.sql.gz"):
        try:
            age = now - dt.datetime.fromtimestamp(item.stat().st_mtime, tz=dt.timezone.utc)
            if age.days >= retention_days:
                item.unlink(missing_ok=True)
                removed += 1
        except Exception:
            continue
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup Postgres do Quiz Vance")
    parser.add_argument("--database-url", default=(os.getenv("DATABASE_URL") or "").strip(), help="URL do Postgres")
    parser.add_argument("--output-dir", default="backend/backups", help="Diretorio de destino dos backups")
    parser.add_argument("--retention-days", type=int, default=7, help="Dias de retencao (0 desativa limpeza)")
    args = parser.parse_args()

    database_url = str(args.database_url or "").strip()
    if not database_url:
        raise SystemExit("Defina --database-url ou DATABASE_URL.")

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve()
    output_file = output_dir / f"quiz_vance_backup_{ts}.sql.gz"

    _run_backup(database_url, output_file)
    removed = _cleanup_old_backups(output_dir, int(args.retention_days or 0))

    print(f"backup_ok={output_file}")
    print(f"removed_old={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

