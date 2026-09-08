from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from .database import Library, utc_now


def create_backup(library: Library, destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="waraq-backup-") as temporary:
        temp = Path(temporary)
        snapshot = temp / "library.sqlite3"
        source = library.connect()
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close(); source.close()
        manifest = {
            "format": 2,
            "created_at": utc_now(),
            "application": "Warraq",
            "pdf_storage": "external",
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(snapshot, "library.sqlite3")
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return destination


def restore_backup(library: Library, source: Path) -> None:
    source = Path(source)
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if "manifest.json" not in names or "library.sqlite3" not in names:
            raise ValueError("ملف النسخة الاحتياطية غير صالح")
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("تحتوي النسخة الاحتياطية على مسار غير آمن")
        manifest = json.loads(archive.read("manifest.json"))
        backup_format = manifest.get("format")
        if manifest.get("application") != "Warraq" or backup_format not in {1, 2}:
            raise ValueError("إصدار النسخة الاحتياطية غير مدعوم")
        with tempfile.TemporaryDirectory(prefix="waraq-restore-") as temporary:
            temp = Path(temporary)
            archive.extract("library.sqlite3", temp)
            check = sqlite3.connect(temp / "library.sqlite3")
            try:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("قاعدة بيانات النسخة الاحتياطية تالفة")
            finally:
                check.close()
            safety = library.root / f"before-restore-{utc_now().replace(':', '-')}.waraq-backup"
            create_backup(library, safety)
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(library.db_path) + suffix)
                if candidate.exists(): candidate.unlink()
            shutil.copy2(temp / "library.sqlite3", library.db_path)
    library._migrate()
