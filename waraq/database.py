from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import pypdfium2 as pdfium

from .markdown_text import (
    markdown_lines_to_document,
    markdown_to_html,
    normalize_markdown_document,
    typed_lines_to_html,
)
from .models import DEFAULT_MANUSCRIPT_PROMPT, DEFAULT_PRINTED_PROMPT, ExtractedPage, normalize_visual_line_text
from .richtext import extracted_lines_to_html, regions_to_html, rich_html_lines, sanitize_rich_html


DEFAULT_QUOTAS = {
    "gemini-2.5-flash-lite": (10, 250_000, 20),
    "gemini-2.5-flash": (5, 250_000, 20),
    "gemini-3-flash-preview": (5, 250_000, 20),
    "gemini-3.1-flash-lite": (15, 250_000, 500),
    "gemini-3.5-flash-lite": (15, 250_000, 500),
    "gemini-3.5-flash": (5, 250_000, 20),
    "gemini-3.6-flash": (5, 250_000, 20),
    "gemini-3.7-flash": (5, 250_000, 20),
    "gemini-3.8-flash": (5, 250_000, 20),
    "gemini-2.5-pro": (0, 0, 0),
    "gemini-3.1-pro-preview": (0, 0, 0),
}

RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_WINDOW_BUFFER_SECONDS = 1.0
RATE_LIMIT_SPACING_BUFFER_SECONDS = 0.25


def safe_rpm(rpm: int) -> int:
    return max(0, int(rpm) - 1)


class RequestThrottleDelay(RuntimeError):
    """Tell the caller how long to wait before reserving an API request."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = max(0.0, wait_seconds)
        super().__init__(f"انتظر {self.wait_seconds:.1f} ثانية قبل طلب Gemini التالي")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE books (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, source_path TEXT NOT NULL,
      page_count INTEGER NOT NULL CHECK(page_count > 0), created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL, last_page INTEGER NOT NULL DEFAULT 1,
      deleted_at TEXT
    );
    CREATE TABLE pages (
      id TEXT PRIMARY KEY, book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
      number INTEGER NOT NULL, width REAL NOT NULL, height REAL NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending', reviewed INTEGER NOT NULL DEFAULT 0,
      printed_page TEXT NOT NULL DEFAULT '', is_blank INTEGER NOT NULL DEFAULT 0,
      error TEXT NOT NULL DEFAULT '', raw_result TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL, UNIQUE(book_id, number)
    );
    CREATE TABLE regions (
      id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      kind TEXT NOT NULL, source TEXT NOT NULL, column_index INTEGER NOT NULL,
      reading_order INTEGER NOT NULL, x REAL NOT NULL, y REAL NOT NULL,
      width REAL NOT NULL, height REAL NOT NULL
    );
    CREATE TABLE lines (
      id TEXT PRIMARY KEY, region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
      reading_order INTEGER NOT NULL, text TEXT NOT NULL, x REAL NOT NULL,
      y REAL NOT NULL, width REAL NOT NULL, height REAL NOT NULL,
      marks TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE page_versions (
      id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      reason TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE projects (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE api_keys (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      name TEXT NOT NULL, secret_ref TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
      last_used_at TEXT
    );
    CREATE TABLE prompts (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL,
      instructions TEXT NOT NULL, is_default INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE tasks (
      id TEXT PRIMARY KEY, book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
      start_page INTEGER NOT NULL, end_page INTEGER NOT NULL, state TEXT NOT NULL,
      project_id TEXT, key_id TEXT, model TEXT NOT NULL, prompt_id TEXT NOT NULL,
      prompt_snapshot TEXT NOT NULL, mode TEXT NOT NULL, dpi INTEGER NOT NULL,
      overwrite INTEGER NOT NULL DEFAULT 0, stop_requested INTEGER NOT NULL DEFAULT 0,
      current_page INTEGER, completed INTEGER NOT NULL DEFAULT 0,
      failed INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE requests (
      id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      book_id TEXT NOT NULL, page_number INTEGER NOT NULL, project_id TEXT,
      key_id TEXT, model TEXT NOT NULL, prompt_snapshot TEXT NOT NULL,
      settings TEXT NOT NULL, state TEXT NOT NULL, http_status INTEGER,
      error TEXT NOT NULL DEFAULT '', usage TEXT, response TEXT,
      started_at TEXT NOT NULL, finished_at TEXT
    );
    CREATE TABLE quota_limits (
      project_id TEXT NOT NULL, model TEXT NOT NULL, rpm INTEGER NOT NULL,
      input_tpm INTEGER NOT NULL, rpd INTEGER NOT NULL, updated_at TEXT NOT NULL,
      PRIMARY KEY(project_id, model)
    );
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE exports (
      id TEXT PRIMARY KEY, book_id TEXT NOT NULL, start_page INTEGER NOT NULL,
      end_page INTEGER NOT NULL, path TEXT NOT NULL, report TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX requests_project_model_time ON requests(project_id, model, started_at);
    CREATE INDEX regions_page_order ON regions(page_id, reading_order);
    CREATE INDEX lines_region_order ON lines(region_id, reading_order);
    """,
    """
    ALTER TABLE pages ADD COLUMN content_html TEXT NOT NULL DEFAULT '';
    """,
    """
    ALTER TABLE tasks ADD COLUMN control_action TEXT NOT NULL DEFAULT '';
    CREATE TABLE task_pages (
      task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      page_number INTEGER NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending',
      error TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      PRIMARY KEY(task_id, page_number)
    );
    CREATE INDEX task_pages_state ON task_pages(task_id, state, page_number);
    INSERT INTO task_pages (task_id, page_number, state, error, updated_at)
    SELECT t.id, p.number,
      CASE
        WHEN EXISTS (
          SELECT 1 FROM requests r
          WHERE r.task_id=t.id AND r.page_number=p.number AND r.state='success'
        ) THEN 'completed'
        WHEN EXISTS (
          SELECT 1 FROM requests r
          WHERE r.task_id=t.id AND r.page_number=p.number AND r.state='error'
        ) THEN 'failed'
        WHEN p.state='done' AND t.overwrite=0 THEN 'skipped'
        ELSE 'pending'
      END,
      CASE WHEN p.state='failed' THEN p.error ELSE '' END,
      t.updated_at
    FROM tasks t
    JOIN pages p ON p.book_id=t.book_id
      AND p.number BETWEEN t.start_page AND t.end_page;
    UPDATE tasks SET
      completed=(SELECT COUNT(*) FROM task_pages tp WHERE tp.task_id=tasks.id AND tp.state='completed'),
      failed=(SELECT COUNT(*) FROM task_pages tp WHERE tp.task_id=tasks.id AND tp.state='failed');
    """,
    """
    ALTER TABLE quota_limits ADD COLUMN safe_rpm INTEGER NOT NULL DEFAULT 0;
    UPDATE quota_limits SET safe_rpm=CASE WHEN rpm>0 THEN rpm-1 ELSE 0 END;
    """,
    """
    ALTER TABLE tasks ADD COLUMN pages_per_request INTEGER NOT NULL DEFAULT 1
      CHECK(pages_per_request > 0);
    ALTER TABLE requests ADD COLUMN page_numbers TEXT NOT NULL DEFAULT '[]';
    UPDATE requests SET page_numbers='[' || page_number || ']';
    """,
    """
    CREATE TABLE api_keys_new (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, secret_ref TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL, last_used_at TEXT
    );
    INSERT INTO api_keys_new (id,name,secret_ref,created_at,last_used_at)
    SELECT id,name,secret_ref,created_at,last_used_at FROM api_keys;

    CREATE TABLE quota_limits_new (
      key_id TEXT NOT NULL REFERENCES api_keys_new(id) ON DELETE CASCADE,
      model TEXT NOT NULL, rpm INTEGER NOT NULL, input_tpm INTEGER NOT NULL,
      rpd INTEGER NOT NULL, updated_at TEXT NOT NULL,
      safe_rpm INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(key_id, model)
    );
    INSERT INTO quota_limits_new
      (key_id,model,rpm,input_tpm,rpd,updated_at,safe_rpm)
    SELECT k.id,q.model,q.rpm,q.input_tpm,q.rpd,q.updated_at,q.safe_rpm
    FROM api_keys k JOIN quota_limits q ON q.project_id=k.project_id;

    DROP TABLE quota_limits;
    DROP TABLE api_keys;
    ALTER TABLE api_keys_new RENAME TO api_keys;
    ALTER TABLE quota_limits_new RENAME TO quota_limits;
    DROP TABLE projects;
    DROP INDEX requests_project_model_time;
    CREATE INDEX requests_key_model_time ON requests(key_id, model, started_at);
    """,
    """
    ALTER TABLE pages ADD COLUMN original_content_html TEXT NOT NULL DEFAULT '';
    """,
    """
    ALTER TABLE pages ADD COLUMN content_markdown TEXT NOT NULL DEFAULT '';
    ALTER TABLE pages ADD COLUMN original_content_markdown TEXT NOT NULL DEFAULT '';
    ALTER TABLE pages ADD COLUMN content_format TEXT NOT NULL DEFAULT 'html';
    ALTER TABLE pages ADD COLUMN original_content_format TEXT NOT NULL DEFAULT 'html';
    """,
)


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.db_path = self.root / "library.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _migrate(self) -> None:
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            current = db.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            for version, script in enumerate(MIGRATIONS, 1):
                if version <= current:
                    continue
                db.executescript(script)
                db.execute("INSERT INTO schema_migrations VALUES (?, ?)", (version, utc_now()))
            now = utc_now()
            if not db.execute("SELECT 1 FROM prompts").fetchone():
                db.executemany(
                    "INSERT INTO prompts VALUES (?, ?, ?, ?, 1, ?, ?)",
                    [
                        ("default-printed", "المطبوعات العربية", "printed", DEFAULT_PRINTED_PROMPT, now, now),
                        ("default-manuscript", "المخطوطات", "manuscript", DEFAULT_MANUSCRIPT_PROMPT, now, now),
                    ],
                )
            db.executemany(
                "UPDATE prompts SET instructions=?, updated_at=? WHERE id=? AND is_default=1",
                [
                    (DEFAULT_PRINTED_PROMPT, now, "default-printed"),
                    (DEFAULT_MANUSCRIPT_PROMPT, now, "default-manuscript"),
                ],
            )
            for key in db.execute("SELECT id FROM api_keys"):
                db.executemany("""INSERT OR IGNORE INTO quota_limits
                    (key_id,model,rpm,input_tpm,rpd,updated_at,safe_rpm)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", [
                    (key["id"], model, rpm, tpm, rpd, now, safe_rpm(rpm))
                    for model, (rpm, tpm, rpd) in DEFAULT_QUOTAS.items()
                ])
            db.execute("UPDATE task_pages SET state='pending', updated_at=? WHERE state='running'", (now,))
            db.execute("UPDATE tasks SET state='interrupted', control_action='', current_page=NULL, error='أغلق التطبيق قبل اكتمال المهمة', updated_at=? WHERE state='running'", (now,))
            db.execute("UPDATE requests SET state='unresolved', error='أغلق التطبيق قبل وصول الرد', finished_at=? WHERE state IN ('sending','received')", (now,))

    @staticmethod
    def _pdf_page_sizes(source: Path) -> tuple[Path, list[tuple[float, float]]]:
        source = Path(source).expanduser().resolve()
        if source.suffix.lower() != ".pdf" or not source.is_file():
            raise ValueError("اختر ملف PDF صالحًا")
        try:
            with pdfium.PdfDocument(source) as pdf:
                if not len(pdf):
                    raise ValueError("ملف PDF خالٍ من الصفحات")
                if len(pdf) > 5000:
                    raise ValueError("الحد الأقصى 5000 صفحة للكتاب")
                sizes = [tuple(map(float, pdf[index].get_size())) for index in range(len(pdf))]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"تعذر فتح ملف PDF: {exc}") from exc
        return source, sizes

    @staticmethod
    def _book_dict(row: sqlite3.Row) -> dict[str, Any]:
        book = dict(row)
        source = Path(book["source_path"])
        book["source_available"] = source.is_file()
        book["source_name"] = source.name
        return book

    def add_book(self, source: Path, name: str | None = None) -> dict[str, Any]:
        source, sizes = self._pdf_page_sizes(source)
        book_id = uuid.uuid4().hex
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, 1, NULL)",
                (book_id, name or source.stem, str(source), len(sizes), now, now),
            )
            db.executemany(
                """INSERT INTO pages
                   (id,book_id,number,width,height,state,reviewed,printed_page,is_blank,error,raw_result,updated_at,content_html)
                   VALUES (?, ?, ?, ?, ?, 'pending', 0, '', 0, '', '', ?, '')""",
                [(uuid.uuid4().hex, book_id, i, w, h, now) for i, (w, h) in enumerate(sizes, 1)],
            )
        return self.get_book(book_id)

    def rename_book(self, book_id: str, name: str) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("اكتب اسم الكتاب")
        with self.transaction() as db:
            changed = db.execute(
                "UPDATE books SET name=?,updated_at=? WHERE id=? AND deleted_at IS NULL",
                (clean_name, utc_now(), book_id),
            ).rowcount
            if not changed:
                raise KeyError("الكتاب غير موجود")
        return self.get_book(book_id)

    def relink_book_pdf(self, book_id: str, source: Path) -> dict[str, Any]:
        source, sizes = self._pdf_page_sizes(source)
        with self.transaction() as db:
            book = db.execute(
                "SELECT page_count FROM books WHERE id=? AND deleted_at IS NULL",
                (book_id,),
            ).fetchone()
            if book is None:
                raise KeyError("الكتاب غير موجود")
            if len(sizes) != book["page_count"]:
                raise ValueError(
                    f"عدد صفحات الملف المختار هو {len(sizes)}، بينما الكتاب المحفوظ "
                    f"يتكون من {book['page_count']} صفحة. اختر ملف PDF المطابق حتى لا "
                    "ترتبط التحويلات بصفحات خاطئة."
                )
            if db.execute(
                "SELECT 1 FROM tasks WHERE book_id=? AND state='running' LIMIT 1",
                (book_id,),
            ).fetchone():
                raise RuntimeError("علّق مهمة التحويل الجارية قبل تغيير ملف PDF")
            now = utc_now()
            db.execute(
                "UPDATE books SET source_path=?,updated_at=? WHERE id=?",
                (str(source), now, book_id),
            )
            db.executemany(
                "UPDATE pages SET width=?,height=? WHERE book_id=? AND number=?",
                [(width, height, book_id, number) for number, (width, height) in enumerate(sizes, 1)],
            )
        return self.get_book(book_id)

    def delete_book(self, book_id: str) -> None:
        with self.transaction() as db:
            if db.execute(
                "SELECT 1 FROM tasks WHERE book_id=? AND state='running' LIMIT 1",
                (book_id,),
            ).fetchone():
                raise RuntimeError("علّق مهمة التحويل الجارية قبل حذف الكتاب")
            changed = db.execute(
                "UPDATE books SET deleted_at=?,updated_at=? WHERE id=? AND deleted_at IS NULL",
                (utc_now(), utc_now(), book_id),
            ).rowcount
            if not changed:
                raise KeyError("الكتاب غير موجود")

    def list_books(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        with self.connect() as db:
            rows = db.execute(
                """SELECT b.*, SUM(p.state='done') converted, SUM(p.reviewed) reviewed,
                   SUM(p.state='failed') failed
                   FROM books b JOIN pages p ON p.book_id=b.id
                   WHERE b.deleted_at IS NULL AND b.name LIKE ?
                   GROUP BY b.id ORDER BY b.updated_at DESC""",
                (pattern,),
            )
            return [self._book_dict(row) for row in rows]

    def get_book(self, book_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM books WHERE id=? AND deleted_at IS NULL", (book_id,)).fetchone()
            if row is None:
                raise KeyError("الكتاب غير موجود")
            book = self._book_dict(row)
            book["pages"] = [dict(p) for p in db.execute(
                "SELECT id,number,state,reviewed,error,is_blank FROM pages WHERE book_id=? ORDER BY number", (book_id,)
            )]
            return book

    def page_versions(self, book_id: str, page_number: int) -> list[dict[str, Any]]:
        with self.connect() as db:
            page = db.execute("SELECT id FROM pages WHERE book_id=? AND number=?", (book_id, page_number)).fetchone()
            if page is None:
                raise KeyError("الصفحة غير موجودة")
            return [dict(row) for row in db.execute("SELECT id,reason,created_at FROM page_versions WHERE page_id=? ORDER BY created_at DESC", (page["id"],))]

    def page_path(self, book_id: str) -> Path:
        with self.connect() as db:
            row = db.execute(
                "SELECT source_path FROM books WHERE id=? AND deleted_at IS NULL",
                (book_id,),
            ).fetchone()
            if row is None:
                raise KeyError("الكتاب غير موجود")
            path = Path(row[0])
            if not path.is_file():
                raise FileNotFoundError(
                    "تعذر العثور على ملف PDF الأصلي. أعد ربط الكتاب بالملف من مساره الجديد."
                )
            return path

    def get_page(self, book_id: str, number: int) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM pages WHERE book_id=? AND number=?", (book_id, number)).fetchone()
            if row is None:
                raise KeyError("الصفحة غير موجودة")
            page = dict(row)
            page["regions"] = []
            for region_row in db.execute("SELECT * FROM regions WHERE page_id=? ORDER BY reading_order", (page["id"],)):
                region = dict(region_row)
                region["lines"] = []
                for line_row in db.execute("SELECT * FROM lines WHERE region_id=? ORDER BY reading_order", (region["id"],)):
                    line = dict(line_row)
                    line["text"] = normalize_visual_line_text(line["text"])
                    line["marks"] = json.loads(line["marks"])
                    region["lines"].append(line)
                page["regions"].append(region)
            if not page.get("content_html") and page["regions"]:
                page["content_html"] = regions_to_html(page["regions"])
            page["can_reset_to_extraction"] = bool(
                page["state"] == "done"
                and (
                    page.get("original_content_markdown")
                    or page.get("original_content_html")
                    or page.get("raw_result")
                )
            )
            db.execute("UPDATE books SET last_page=?, updated_at=? WHERE id=?", (number, utc_now(), book_id))
            return page

    def _snapshot(self, db: sqlite3.Connection, page_id: str) -> dict[str, Any]:
        page = dict(db.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone())
        page["regions"] = []
        for rr in db.execute("SELECT * FROM regions WHERE page_id=? ORDER BY reading_order", (page_id,)):
            region = dict(rr)
            region["lines"] = [dict(line) for line in db.execute("SELECT * FROM lines WHERE region_id=? ORDER BY reading_order", (region["id"],))]
            page["regions"].append(region)
        return page

    def save_regions(self, book_id: str, page_number: int, regions: list[dict[str, Any]], reviewed: bool | None = None, reason: str = "edit") -> dict[str, Any]:
        now = utc_now()
        with self.transaction() as db:
            page = db.execute("SELECT * FROM pages WHERE book_id=? AND number=?", (book_id, page_number)).fetchone()
            if page is None:
                raise KeyError("الصفحة غير موجودة")
            old = self._snapshot(db, page["id"])
            normalized = self._normalize_regions(regions)
            old_comparable = [{k: r[k] for k in ("kind", "source", "column_index", "reading_order", "x", "y", "width", "height") if k in r} | {"lines": [{**{k: l[k] for k in ("reading_order", "text", "x", "y", "width", "height") if k in l}, "marks": json.loads(l.get("marks", "[]")) if isinstance(l.get("marks"), str) else l.get("marks", [])} for l in r["lines"]]} for r in old["regions"]]
            changed = normalized != old_comparable
            if changed and old["regions"]:
                db.execute("INSERT INTO page_versions VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, page["id"], reason, json.dumps(old, ensure_ascii=False), now))
            db.execute("DELETE FROM regions WHERE page_id=?", (page["id"],))
            self._insert_regions(db, page["id"], normalized)
            next_reviewed = int(reviewed) if reviewed is not None else (0 if changed else page["reviewed"])
            db.execute(
                "UPDATE pages SET state='done', reviewed=?, error='', content_html=?, content_markdown='', content_format='html', updated_at=? WHERE id=?",
                (next_reviewed, regions_to_html(normalized), now, page["id"]),
            )
            db.execute("UPDATE books SET updated_at=?, last_page=? WHERE id=?", (now, page_number, book_id))
        return self.get_page(book_id, page_number)

    def save_page_content(
        self,
        book_id: str,
        page_number: int,
        content_html: str,
        reviewed: bool | None = None,
        reason: str = "edit",
        content_markdown: str | None = None,
    ) -> dict[str, Any]:
        """Save canonical Markdown or legacy HTML and a plain-line compatibility view."""
        now = utc_now()
        safe_markdown = (
            normalize_markdown_document(content_markdown)
            if content_markdown is not None
            else ""
        )
        if content_markdown is not None:
            rendered_markdown = markdown_to_html(safe_markdown)
            editor_html = sanitize_rich_html(content_html)
            safe_html = (
                editor_html
                if editor_html
                and rich_html_lines(editor_html) == rich_html_lines(rendered_markdown)
                else rendered_markdown
            )
        else:
            safe_html = sanitize_rich_html(content_html)
        plain_lines = rich_html_lines(safe_html)
        with self.transaction() as db:
            page = db.execute(
                "SELECT * FROM pages WHERE book_id=? AND number=?", (book_id, page_number)
            ).fetchone()
            if page is None:
                raise KeyError("الصفحة غير موجودة")
            old = self._snapshot(db, page["id"])
            old_html = page["content_html"] or regions_to_html(old["regions"])
            changed = (
                page["content_markdown"] != safe_markdown
                if content_markdown is not None and page["content_markdown"]
                else sanitize_rich_html(old_html) != safe_html
            )
            if changed and (old["regions"] or old_html):
                db.execute(
                    "INSERT INTO page_versions VALUES (?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, page["id"], reason, json.dumps(old, ensure_ascii=False), now),
                )
            if changed:
                db.execute("DELETE FROM regions WHERE page_id=?", (page["id"],))
                self._insert_regions(db, page["id"], self._compatibility_regions(plain_lines))
            next_reviewed = int(reviewed) if reviewed is not None else (0 if changed else page["reviewed"])
            db.execute(
                "UPDATE pages SET state='done', reviewed=?, error='', content_html=?, content_markdown=?, content_format=?, updated_at=? WHERE id=?",
                (
                    next_reviewed,
                    safe_html,
                    safe_markdown,
                    "markdown" if content_markdown is not None else "html",
                    now,
                    page["id"],
                ),
            )
            db.execute("UPDATE books SET updated_at=?, last_page=? WHERE id=?", (now, page_number, book_id))
        return self.get_page(book_id, page_number)

    def reset_page_to_extraction(
        self, book_id: str, page_number: int
    ) -> dict[str, Any]:
        """Restore the last AI extraction without changing its saved baseline."""
        now = utc_now()
        with self.transaction() as db:
            page = db.execute(
                "SELECT * FROM pages WHERE book_id=? AND number=?",
                (book_id, page_number),
            ).fetchone()
            if page is None:
                raise KeyError("الصفحة غير موجودة")
            if page["state"] != "done" or not (
                page["original_content_markdown"]
                or page["original_content_html"]
                or page["raw_result"]
            ):
                raise ValueError("لا يوجد نص محوّل لإعادته في هذه الصفحة")

            original_format = page["original_content_format"]
            original_markdown = page["original_content_markdown"]
            original_html = page["original_content_html"]
            if original_format == "markdown" and original_markdown and not original_html:
                original_html = markdown_to_html(original_markdown)
            elif not original_html:
                try:
                    raw_result = json.loads(page["raw_result"])
                    if "lines" in raw_result:
                        extracted = ExtractedPage.model_validate(raw_result)
                        original_format = "markdown"
                        original_markdown = markdown_lines_to_document(
                            extracted.content_markdown
                        )
                        original_html = markdown_to_html(original_markdown)
                    elif "content_markdown" in raw_result:
                        original_format = "markdown"
                        original_markdown = markdown_lines_to_document(
                            raw_result["content_markdown"]
                        )
                        original_html = markdown_to_html(original_markdown)
                    elif "content_html" in raw_result:
                        original_html = extracted_lines_to_html(raw_result["content_html"])
                    else:
                        raise ValueError
                except (ValueError, TypeError, json.JSONDecodeError):
                    raise ValueError(
                        "تعذر العثور على نسخة التحويل الأصلية لهذه الصفحة"
                    ) from None
            original_html = sanitize_rich_html(original_html)

            old = self._snapshot(db, page["id"])
            old_html = sanitize_rich_html(
                page["content_html"] or regions_to_html(old["regions"])
            )
            reset_changes_content = (
                old_html != original_html
                or page["content_format"] != original_format
                or (
                    original_format == "markdown"
                    and page["content_markdown"] != original_markdown
                )
            )
            if reset_changes_content:
                db.execute(
                    "INSERT INTO page_versions VALUES (?, ?, ?, ?, ?)",
                    (
                        uuid.uuid4().hex,
                        page["id"],
                        "reset_to_extraction",
                        json.dumps(old, ensure_ascii=False),
                        now,
                    ),
                )
                db.execute("DELETE FROM regions WHERE page_id=?", (page["id"],))
                self._insert_regions(
                    db,
                    page["id"],
                    self._compatibility_regions(rich_html_lines(original_html)),
                )
            db.execute(
                """UPDATE pages
                   SET state='done', reviewed=0, error='', content_html=?,
                       original_content_html=?, content_markdown=?,
                       original_content_markdown=?, content_format=?,
                       original_content_format=?, updated_at=? WHERE id=?""",
                (
                    original_html,
                    original_html,
                    original_markdown,
                    original_markdown,
                    original_format,
                    original_format,
                    now,
                    page["id"],
                ),
            )
            db.execute(
                "UPDATE books SET updated_at=?, last_page=? WHERE id=?",
                (now, page_number, book_id),
            )
        return self.get_page(book_id, page_number)

    def apply_extraction(self, book_id: str, page_number: int, result: ExtractedPage, raw: str, reason: str = "extraction") -> None:
        now = utc_now()
        content_markdown = markdown_lines_to_document(result.content_markdown)
        content_html = typed_lines_to_html(result.lines)
        regions = self._compatibility_regions(rich_html_lines(content_html))
        with self.transaction() as db:
            page = db.execute("SELECT * FROM pages WHERE book_id=? AND number=?", (book_id, page_number)).fetchone()
            if page is None:
                raise KeyError("الصفحة غير موجودة")
            old = self._snapshot(db, page["id"])
            if old["regions"] or old["raw_result"]:
                db.execute("INSERT INTO page_versions VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, page["id"], reason, json.dumps(old, ensure_ascii=False), now))
            db.execute("DELETE FROM regions WHERE page_id=?", (page["id"],))
            self._insert_regions(db, page["id"], regions)
            db.execute(
                """UPDATE pages
                   SET state='done', reviewed=0, printed_page=?, is_blank=?, error='',
                       raw_result=?, content_html=?, original_content_html=?,
                       content_markdown=?, original_content_markdown=?,
                       content_format='markdown', original_content_format='markdown',
                       updated_at=?
                   WHERE id=?""",
                (
                    result.printed_page or "",
                    int(result.is_blank),
                    raw,
                    content_html,
                    content_html,
                    content_markdown,
                    content_markdown,
                    now,
                    page["id"],
                ),
            )

    def mark_page_failed(self, book_id: str, page_number: int, error: str) -> None:
        with self.transaction() as db:
            page = db.execute("SELECT state,raw_result FROM pages WHERE book_id=? AND number=?", (book_id, page_number)).fetchone()
            state = "done" if page and page["raw_result"] else "failed"
            db.execute("UPDATE pages SET state=?, error=?, updated_at=? WHERE book_id=? AND number=?", (state, error, utc_now(), book_id, page_number))

    @staticmethod
    def _normalize_regions(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for index, region in enumerate(regions):
            output.append({
                "kind": region.get("kind", "body"), "source": region.get("source", "printed"),
                "column_index": int(region.get("column_index", region.get("column", 0))),
                "reading_order": int(region.get("reading_order", region.get("order", index))),
                "x": round(float(region.get("x", 0.05)), 5), "y": round(float(region.get("y", 0.05)), 5),
                "width": round(float(region.get("width", region.get("w", 0.9))), 5),
                "height": round(float(region.get("height", region.get("h", 0.08))), 5),
                "lines": [{
                    "reading_order": int(line.get("reading_order", line.get("order", li))),
                    "text": normalize_visual_line_text(str(line.get("text", ""))), "x": round(float(line.get("x", 0)), 5),
                    "y": round(float(line.get("y", 0)), 5), "width": round(float(line.get("width", line.get("w", 1))), 5),
                    "height": round(float(line.get("height", line.get("h", 1))), 5), "marks": list(line.get("marks", [])),
                } for li, line in enumerate(region.get("lines", []))],
            })
        return output

    @staticmethod
    def _compatibility_regions(lines: list[str]) -> list[dict[str, Any]]:
        if not lines:
            return []
        count = len(lines)
        return [{
            "kind": "body", "source": "printed", "column_index": 0,
            "reading_order": 0, "x": .06, "y": .05, "width": .88, "height": .9,
            "lines": [
                {
                    "reading_order": index, "text": line,
                    "x": .06, "y": .05 + (.9 * index / count),
                    "width": .88, "height": .9 / count, "marks": [],
                }
                for index, line in enumerate(lines)
            ],
        }]

    @staticmethod
    def _insert_regions(db: sqlite3.Connection, page_id: str, regions: list[dict[str, Any]]) -> None:
        for region in regions:
            region_id = uuid.uuid4().hex
            db.execute("INSERT INTO regions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                region_id, page_id, region["kind"], region["source"], region["column_index"], region["reading_order"],
                region["x"], region["y"], region["width"], region["height"],
            ))
            db.executemany("INSERT INTO lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                (uuid.uuid4().hex, region_id, line["reading_order"], line["text"], line["x"], line["y"], line["width"], line["height"], json.dumps(line["marks"], ensure_ascii=False))
                for line in region["lines"]
            ])

    def list_keys(self) -> list[dict[str, Any]]:
        """Return named Gemini keys without exposing secret-store references."""
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT id,name,last_used_at,created_at
                       FROM api_keys ORDER BY created_at"""
                )
            ]

    def add_key(self, name: str, secret_ref: str) -> str:
        """Create a named key and its quota limits in one transaction."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("اكتب اسم المفتاح")
        key_id = uuid.uuid4().hex
        now = utc_now()
        with self.transaction() as db:
            if db.execute(
                "SELECT 1 FROM api_keys WHERE name=? COLLATE NOCASE", (clean_name,)
            ).fetchone():
                raise ValueError("يوجد مفتاح بهذا الاسم")
            db.execute(
                "INSERT INTO api_keys VALUES (?, ?, ?, ?, NULL)",
                (key_id, clean_name, secret_ref, now),
            )
            db.executemany(
                """INSERT INTO quota_limits
                   (key_id,model,rpm,input_tpm,rpd,updated_at,safe_rpm)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (key_id, model, rpm, tpm, rpd, now, safe_rpm(rpm))
                    for model, (rpm, tpm, rpd) in DEFAULT_QUOTAS.items()
                ],
            )
        return key_id

    def delete_key(self, key_id: str) -> dict[str, Any]:
        """Delete key metadata and its quota limits."""
        with self.transaction() as db:
            row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
            if row is None:
                raise KeyError("المفتاح غير موجود")
            if db.execute(
                """SELECT 1 FROM tasks
                   WHERE key_id=? AND state IN
                     ('queued','running','paused','interrupted','failed','completed_with_errors')
                   LIMIT 1""",
                (key_id,),
            ).fetchone():
                raise RuntimeError(
                    "أكمل أو ألغِ مهام التحويل المرتبطة بهذا المفتاح قبل حذفه"
                )
            metadata = dict(row)
            db.execute("DELETE FROM quota_limits WHERE key_id=?", (key_id,))
            db.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            return metadata

    def key_metadata(self, key_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
            if row is None:
                raise KeyError("المفتاح غير موجود")
            return dict(row)

    def list_prompts(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM prompts ORDER BY is_default DESC, created_at")]

    def save_prompt(self, name: str, mode: str, instructions: str, prompt_id: str | None = None) -> str:
        now = utc_now()
        with self.transaction() as db:
            if prompt_id:
                if db.execute("SELECT is_default FROM prompts WHERE id=?", (prompt_id,)).fetchone()[0]:
                    raise ValueError("احفظ نسخة مخصصة بدل تعديل البرومبت الافتراضي")
                db.execute("UPDATE prompts SET name=?, mode=?, instructions=?, updated_at=? WHERE id=?", (name.strip(), mode, instructions.strip(), now, prompt_id))
                return prompt_id
            prompt_id = uuid.uuid4().hex
            db.execute("INSERT INTO prompts VALUES (?, ?, ?, ?, 0, ?, ?)", (prompt_id, name.strip(), mode, instructions.strip(), now, now))
            return prompt_id

    def create_task(
        self,
        *,
        book_id: str,
        start_page: int,
        end_page: int,
        key_id: str,
        model: str,
        prompt_id: str,
        mode: str,
        dpi: int,
        overwrite: bool,
        pages_per_request: int = 1,
    ) -> str:
        book = self.get_book(book_id)
        if start_page < 1 or end_page > book["page_count"] or start_page > end_page:
            raise ValueError("نطاق الصفحات غير صالح")
        pages_per_request = int(pages_per_request)
        if pages_per_request < 1:
            raise ValueError("عدد الصفحات في الطلب يجب أن يكون صفحة واحدة على الأقل")
        pages_per_request = min(pages_per_request, end_page - start_page + 1)
        with self.connect() as db:
            prompt = db.execute("SELECT instructions FROM prompts WHERE id=?", (prompt_id,)).fetchone()
            if prompt is None:
                raise ValueError("نسخة البرومبت غير موجودة")
            if not db.execute("SELECT 1 FROM api_keys WHERE id=?", (key_id,)).fetchone():
                raise ValueError("مفتاح Gemini غير موجود")
        task_id = uuid.uuid4().hex
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                """INSERT INTO tasks
                   (id,book_id,start_page,end_page,state,project_id,key_id,model,prompt_id,
                    prompt_snapshot,mode,dpi,overwrite,stop_requested,current_page,completed,
                    failed,error,created_at,updated_at,control_action,pages_per_request)
                   VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 0, 0, '', ?, ?, '', ?)""",
                (task_id, book_id, start_page, end_page, None, key_id, model,
                 prompt_id, prompt[0], mode, dpi, int(overwrite), now, now,
                 pages_per_request),
            )
            db.execute(
                """INSERT INTO task_pages (task_id,page_number,state,error,updated_at)
                   SELECT ?,number,
                     CASE WHEN state='done' AND ?=0 THEN 'skipped' ELSE 'pending' END,
                     '',?
                   FROM pages WHERE book_id=? AND number BETWEEN ? AND ?
                   ORDER BY number""",
                (task_id, int(overwrite), now, book_id, start_page, end_page),
            )
        return task_id

    def task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                """SELECT t.*, b.name AS book_name
                   FROM tasks t JOIN books b ON b.id=t.book_id WHERE t.id=?""",
                (task_id,),
            ).fetchone()
            if row is None:
                raise KeyError("المهمة غير موجودة")
            return self._task_snapshot(db, row)

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT t.*, b.name AS book_name
                   FROM tasks t JOIN books b ON b.id=t.book_id
                   WHERE b.deleted_at IS NULL
                   ORDER BY CASE WHEN t.state IN ('queued','running','paused','interrupted') THEN 0 ELSE 1 END,
                            t.updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [self._task_snapshot(db, row) for row in rows]

    @staticmethod
    def _task_snapshot(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        task = dict(row)
        counts = {
            item["state"]: item["count"]
            for item in db.execute(
                "SELECT state,COUNT(*) AS count FROM task_pages WHERE task_id=? GROUP BY state",
                (task["id"],),
            )
        }
        task["total"] = sum(counts.values())
        task["completed"] = counts.get("completed", 0)
        task["failed"] = counts.get("failed", 0)
        task["skipped"] = counts.get("skipped", 0)
        task["remaining"] = counts.get("pending", 0) + counts.get("running", 0)
        task["processed"] = task["completed"] + task["failed"] + task["skipped"]
        task["active_pages"] = [
            item["page_number"]
            for item in db.execute(
                """SELECT page_number FROM task_pages
                   WHERE task_id=? AND state='running' ORDER BY page_number""",
                (task["id"],),
            )
        ]
        task["display_name"] = (
            f'{task.get("book_name", "")}، من صفحة {task["start_page"]} إلى {task["end_page"]}'
        )
        return task

    def update_task(self, task_id: str, **fields: Any) -> None:
        allowed = {"state", "stop_requested", "control_action", "current_page", "completed", "failed", "error", "key_id", "model"}
        if not fields or not fields.keys() <= allowed:
            raise ValueError("حقول المهمة غير صالحة")
        fields["updated_at"] = utc_now()
        with self.transaction() as db:
            db.execute("UPDATE tasks SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?", (*fields.values(), task_id))

    def page_numbers_for_task(self, task: dict[str, Any]) -> list[int]:
        with self.connect() as db:
            return [
                row["page_number"]
                for row in db.execute(
                    "SELECT page_number FROM task_pages WHERE task_id=? AND state='pending' ORDER BY page_number",
                    (task["id"],),
                )
            ]

    def prepare_task_run(self, task_id: str) -> None:
        with self.transaction() as db:
            task = db.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()
            if task is None:
                raise KeyError("المهمة غير موجودة")
            if task["state"] not in {"queued", "paused", "interrupted", "failed", "completed_with_errors"}:
                raise RuntimeError("لا يمكن تشغيل مهمة التحويل في حالتها الحالية")
            if task["state"] in {"failed", "completed_with_errors"}:
                db.execute(
                    "UPDATE task_pages SET state='pending',error='',updated_at=? WHERE task_id=? AND state='failed'",
                    (utc_now(), task_id),
                )
            now = utc_now()
            db.execute(
                """UPDATE tasks SET state='running',stop_requested=0,control_action='',
                   current_page=NULL,error='',updated_at=? WHERE id=?""",
                (now, task_id),
            )
            self._sync_task_counts(db, task_id, now)

    def request_task_action(self, task_id: str, action: str) -> None:
        if action not in {"pause", "cancel"}:
            raise ValueError("أمر المهمة غير صالح")
        with self.transaction() as db:
            task = db.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()
            if task is None:
                raise KeyError("المهمة غير موجودة")
            state = task["state"]
            if state in {"completed", "cancelled"}:
                raise RuntimeError("انتهت مهمة التحويل بالفعل")
            now = utc_now()
            if action == "cancel":
                db.execute(
                    """UPDATE task_pages SET state='pending',error='',updated_at=?
                       WHERE task_id=? AND state='running'""",
                    (now, task_id),
                )
                db.execute(
                    """UPDATE tasks SET state='cancelled',control_action='',stop_requested=0,
                       current_page=NULL,updated_at=? WHERE id=?""",
                    (now, task_id),
                )
            elif action == "pause" and state == "paused":
                return
            elif state not in {"queued", "running"}:
                raise RuntimeError("لا يمكن تعليق المهمة في حالتها الحالية")
            else:
                db.execute(
                    "UPDATE tasks SET control_action=?,stop_requested=1,updated_at=? WHERE id=?",
                    (action, now, task_id),
                )

    def start_task_page(self, task_id: str, page_number: int) -> None:
        self.start_task_pages(task_id, [page_number])

    def start_task_pages(self, task_id: str, page_numbers: list[int]) -> None:
        numbers = [int(number) for number in page_numbers]
        if not numbers or len(numbers) != len(set(numbers)):
            raise ValueError("دفعة الصفحات غير صالحة")
        now = utc_now()
        with self.transaction() as db:
            for number in numbers:
                changed = db.execute(
                    """UPDATE task_pages SET state='running',error='',updated_at=?
                       WHERE task_id=? AND page_number=? AND state='pending'""",
                    (now, task_id, number),
                ).rowcount
                if not changed:
                    raise RuntimeError("إحدى الصفحات ليست معلقة في هذه المهمة")
            db.execute(
                "UPDATE tasks SET current_page=?,updated_at=? WHERE id=?",
                (numbers[0], now, task_id),
            )

    def finish_task_page(self, task_id: str, page_number: int, state: str, error: str = "") -> None:
        if state not in {"completed", "failed"}:
            raise ValueError("حالة صفحة المهمة غير صالحة")
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                """UPDATE task_pages SET state=?,error=?,updated_at=?
                   WHERE task_id=? AND page_number=?""",
                (state, error, now, task_id, page_number),
            )
            db.execute(
                """UPDATE tasks SET
                     current_page=(SELECT MIN(page_number) FROM task_pages
                                   WHERE task_id=? AND state='running'),
                     error=?,updated_at=? WHERE id=?""",
                (task_id, error if state == "failed" else "", now, task_id),
            )
            self._sync_task_counts(db, task_id, now)

    @staticmethod
    def _sync_task_counts(db: sqlite3.Connection, task_id: str, now: str) -> None:
        db.execute(
            """UPDATE tasks SET
                 completed=(SELECT COUNT(*) FROM task_pages WHERE task_id=? AND state='completed'),
                 failed=(SELECT COUNT(*) FROM task_pages WHERE task_id=? AND state='failed'),
                 updated_at=? WHERE id=?""",
            (task_id, task_id, now, task_id),
        )

    @staticmethod
    def _request_throttle_delay(
        db: sqlite3.Connection,
        key_id: str | None,
        model: str,
        now: datetime,
    ) -> float:
        if not key_id:
            return 0.0
        quota = db.execute(
            "SELECT rpm,safe_rpm FROM quota_limits WHERE key_id=? AND model=?",
            (key_id, model),
        ).fetchone()
        if quota is None:
            return 0.0
        provider_rpm = int(quota["rpm"])
        rpm = min(int(quota["safe_rpm"]), safe_rpm(provider_rpm))
        if rpm <= 0:
            raise RuntimeError("هذا النموذج غير متاح ضمن حصة المفتاح الحالية")

        rows = db.execute(
            """SELECT started_at FROM requests
               WHERE key_id=? AND model=?
               ORDER BY started_at DESC, rowid DESC LIMIT ?""",
            (key_id, model, rpm),
        ).fetchall()
        if not rows:
            return 0.0

        starts = [datetime.fromisoformat(row["started_at"]) for row in rows]
        next_start = starts[0] + timedelta(
            seconds=(RATE_LIMIT_WINDOW_SECONDS / rpm) + RATE_LIMIT_SPACING_BUFFER_SECONDS
        )
        if len(starts) == rpm:
            window_start = starts[-1] + timedelta(
                seconds=RATE_LIMIT_WINDOW_SECONDS + RATE_LIMIT_WINDOW_BUFFER_SECONDS
            )
            next_start = max(next_start, window_start)
        return max(0.0, (next_start - now).total_seconds())

    def request_throttle_delay(
        self,
        key_id: str | None,
        model: str,
        *,
        now: datetime | None = None,
    ) -> float:
        current = now or datetime.now(timezone.utc)
        with self.connect() as db:
            return self._request_throttle_delay(db, key_id, model, current)

    def start_request(
        self, task: dict[str, Any], page_numbers: int | list[int] | tuple[int, ...]
    ) -> str:
        if isinstance(page_numbers, int):
            numbers = [page_numbers]
        else:
            numbers = [int(number) for number in page_numbers]
        if not numbers or any(number <= 0 for number in numbers):
            raise ValueError("طلب Gemini يجب أن يرتبط بصفحة واحدة على الأقل")
        if len(numbers) != len(set(numbers)):
            raise ValueError("أرقام صفحات الطلب مكررة")
        request_id = uuid.uuid4().hex
        settings = json.dumps({
            "dpi": task["dpi"],
            "mode": task["mode"],
            "overwrite": bool(task["overwrite"]),
            "pages_per_request": len(numbers),
        }, ensure_ascii=False)
        started_at = datetime.now(timezone.utc)
        with self.transaction() as db:
            delay = self._request_throttle_delay(
                db, task.get("key_id"), task["model"], started_at
            )
            if delay > 0:
                raise RequestThrottleDelay(delay)
            db.execute(
                """INSERT INTO requests
                   (id,task_id,book_id,page_number,project_id,key_id,model,
                    prompt_snapshot,settings,state,http_status,error,usage,response,
                    started_at,finished_at,page_numbers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sending', NULL, '', NULL,
                           NULL, ?, NULL, ?)""",
                (
                    request_id,
                    task["id"],
                    task["book_id"],
                    numbers[0],
                    None,
                    task["key_id"],
                    task["model"],
                    task["prompt_snapshot"],
                    settings,
                    started_at.isoformat(timespec="microseconds"),
                    json.dumps(numbers),
                ),
            )
        return request_id

    def finish_request(self, request_id: str, state: str, *, usage: dict[str, Any] | None = None, response: str | None = None, error: str = "", http_status: int | None = None) -> None:
        with self.transaction() as db:
            db.execute("UPDATE requests SET state=?,usage=?,response=?,error=?,http_status=?,finished_at=? WHERE id=?", (
                state, json.dumps(usage, ensure_ascii=False) if usage is not None else None, response,
                error, http_status, utc_now(), request_id,
            ))

    def request_rows(self, limit: int = 250) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM requests ORDER BY started_at DESC LIMIT ?", (limit,))]

    def usage_summary(self, key_id: str | None = None, model: str | None = None) -> dict[str, Any]:
        clauses, args = [], []
        measurement_start = self.setting("measurement_started_at")
        if measurement_start:
            clauses.append("started_at>=?"); args.append(measurement_start)
        if key_id:
            clauses.append("key_id=?"); args.append(key_id)
        if model:
            clauses.append("model=?"); args.append(model)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = list(db.execute(f"SELECT usage,state,started_at,model,key_id FROM requests {where}", args))
        totals = {"input": 0, "output": 0, "thinking": 0, "total": 0, "requests": len(rows), "unknown": 0, "failed": 0}
        for row in rows:
            if row["state"] == "error": totals["failed"] += 1
            if not row["usage"]:
                totals["unknown"] += 1; continue
            usage = json.loads(row["usage"])
            totals["input"] += usage.get("prompt_token_count", usage.get("promptTokenCount", 0)) or 0
            totals["output"] += usage.get("candidates_token_count", usage.get("candidatesTokenCount", 0)) or 0
            totals["thinking"] += usage.get("thoughts_token_count", usage.get("thoughtsTokenCount", 0)) or 0
            totals["total"] += usage.get("total_token_count", usage.get("totalTokenCount", 0)) or 0
        return totals

    def usage_snapshot(self) -> dict[str, Any]:
        return self.usage_summary()

    def reset_usage_measurement(self) -> dict[str, Any]:
        self.set_setting("measurement_started_at", utc_now())
        return self.usage_summary()

    def quota_snapshot(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        pacific = now.astimezone(ZoneInfo("America/Los_Angeles"))
        pacific_midnight = pacific.replace(hour=0, minute=0, second=0, microsecond=0)
        next_pacific_midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = pacific_midnight.astimezone(timezone.utc).isoformat(timespec="seconds")
        minute_start = datetime.fromtimestamp(now.timestamp() - 60, timezone.utc).isoformat(timespec="seconds")
        with self.connect() as db:
            limits = list(db.execute(
                """SELECT q.*,k.name AS key_name
                   FROM quota_limits q JOIN api_keys k ON k.id=q.key_id
                   ORDER BY k.name,q.rpd DESC,q.model"""
            ))
            output = []
            for limit in limits:
                daily = db.execute("SELECT state,usage FROM requests WHERE key_id=? AND model=? AND started_at>=?", (limit["key_id"], limit["model"], day_start)).fetchall()
                minute = db.execute("SELECT usage FROM requests WHERE key_id=? AND model=? AND started_at>=?", (limit["key_id"], limit["model"], minute_start)).fetchall()
                known_input, unknown_input = 0, 0
                for row in minute:
                    if not row["usage"]:
                        unknown_input += 1; continue
                    usage = json.loads(row["usage"])
                    known_input += usage.get("prompt_token_count", usage.get("promptTokenCount", 0)) or 0
                output.append({
                    **dict(limit), "attempts_today": len(daily),
                    "successful_today": sum(row["state"] == "success" for row in daily),
                    "failed_today": sum(row["state"] == "error" for row in daily),
                    "remaining_estimate": max(0, limit["rpd"] - len(daily)),
                    "requests_last_minute": len(minute), "known_input_last_minute": known_input,
                    "input_partially_known": bool(unknown_input),
                    "resets_at": next_pacific_midnight.astimezone(timezone.utc).isoformat(timespec="seconds"),
                })
        return output

    def set_quota_limit(self, key_id: str, model: str, rpm: int, input_tpm: int, rpd: int) -> None:
        with self.transaction() as db:
            db.execute("""INSERT INTO quota_limits
                (key_id,model,rpm,input_tpm,rpd,updated_at,safe_rpm)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key_id,model) DO UPDATE SET
                  rpm=excluded.rpm,input_tpm=excluded.input_tpm,rpd=excluded.rpd,
                  updated_at=excluded.updated_at,safe_rpm=excluded.safe_rpm""",
                (key_id, model, rpm, input_tpm, rpd, utc_now(), safe_rpm(rpm)))

    def set_setting(self, key: str, value: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value, ensure_ascii=False)))

    def setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default
