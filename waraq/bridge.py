from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .backup import create_backup, restore_backup
from .database import Library
from .exporter import export_html, export_markdown, export_word
from .gemini_client import DEFAULT_MODEL, GeminiClient
from .notifications import SYSTEM_SOUNDS, SYSTEM_SOUND_IDS, play_system_sound
from .secrets import SecretStore
from .tasks import ConversionRunner
from .summaries import SummaryDocument, export_summary, export_summaries


def local_path(url_or_path: str) -> Path:
    url = QUrl(url_or_path)
    if url.isLocalFile():
        return Path(url.toLocalFile())
    return Path(url_or_path)


class Bridge(QObject):
    stateChanged = Signal()
    toastChanged = Signal()
    taskEvent = Signal(object)
    asyncResult = Signal(object)
    pageLoaded = Signal()

    def __init__(
        self,
        library: Library,
        secrets: SecretStore,
        sound_player: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self.library = library
        self.secrets = secrets
        self.runner = ConversionRunner(library, secrets, self._on_task_event)
        self._screen = "library"
        self._books: list[dict[str, Any]] = []
        self._book: dict[str, Any] = {}
        self._page: dict[str, Any] = {}
        self._keys: list[dict[str, Any]] = []
        self._prompts: list[dict[str, Any]] = []
        self._models: list[dict[str, Any]] = []
        self._requests: list[dict[str, Any]] = []
        self._tasks: list[dict[str, Any]] = []
        self._usage: dict[str, Any] = {}
        self._quotas: list[dict[str, Any]] = []
        self._task: dict[str, Any] = {}
        self._summaries: list[dict[str, Any]] = []
        self._summary: dict[str, Any] = {}
        self._busy = False
        self._exporting = False
        self._toast = ""
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(5_000)
        self._toast_timer.timeout.connect(self.clearToast)
        self._save_state = "محفوظ"
        self._notification_sounds = [dict(sound) for sound in SYSTEM_SOUNDS]
        sound_setting = self.library.setting("completion_sound", {})
        if not isinstance(sound_setting, dict):
            sound_setting = {}
        selected_sound = sound_setting.get("sound_id", SYSTEM_SOUNDS[0]["id"])
        self._notification_sound_id = (
            selected_sound
            if selected_sound in SYSTEM_SOUND_IDS
            else SYSTEM_SOUNDS[0]["id"]
        )
        self._notification_sound_enabled = bool(sound_setting.get("enabled", True))
        self._sound_player = (
            sound_player if sound_player is not None else play_system_sound
        )
        self._draft_dirty = False
        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(650)
        self._autosave.timeout.connect(self._save_draft)
        self.asyncResult.connect(self._apply_async)
        self.taskEvent.connect(self._apply_task_event)
        self.refresh()

    screen = Property(str, lambda self: self._screen, notify=stateChanged)
    books = Property(list, lambda self: self._books, notify=stateChanged)
    currentBook = Property(dict, lambda self: self._book, notify=stateChanged)
    currentPage = Property(dict, lambda self: self._page, notify=stateChanged)
    keys = Property(list, lambda self: self._keys, notify=stateChanged)
    prompts = Property(list, lambda self: self._prompts, notify=stateChanged)
    models = Property(list, lambda self: self._models, notify=stateChanged)
    requests = Property(list, lambda self: self._requests, notify=stateChanged)
    tasks = Property(list, lambda self: self._tasks, notify=stateChanged)
    usage = Property(dict, lambda self: self._usage, notify=stateChanged)
    quotaLimits = Property(list, lambda self: self._quotas, notify=stateChanged)
    currentTask = Property(dict, lambda self: self._task, notify=stateChanged)
    summaries = Property(list, lambda self: self._summaries, notify=stateChanged)
    currentSummary = Property(dict, lambda self: self._summary, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    exporting = Property(bool, lambda self: self._exporting, notify=stateChanged)
    toast = Property(str, lambda self: self._toast, notify=toastChanged)
    saveState = Property(str, lambda self: self._save_state, notify=stateChanged)
    notificationSounds = Property(
        list, lambda self: self._notification_sounds, notify=stateChanged
    )
    notificationSoundId = Property(
        str, lambda self: self._notification_sound_id, notify=stateChanged
    )
    notificationSoundEnabled = Property(
        bool, lambda self: self._notification_sound_enabled, notify=stateChanged
    )
    richEditorEnabled = Property(bool, lambda self: os.environ.get("WARRAQ_DISABLE_RICH_EDITOR") != "1", constant=True)

    @Slot()
    def refresh(self) -> None:
        self._books = self.library.list_books()
        self._keys = self.library.list_keys()
        self._prompts = self.library.list_prompts()
        self._requests = self._serial_requests(self.library.request_rows())
        self._tasks = self.library.list_tasks()
        self._usage = self.library.usage_snapshot() if hasattr(self.library, "usage_snapshot") else self.library.usage_summary()
        self._quotas = self.library.quota_snapshot()
        if self._task:
            try:
                self._task = self.library.task(self._task["id"])
            except KeyError:
                self._task = {}
        elif self._tasks:
            self._task = self._tasks[0]
        if self._book:
            try:
                self._book = self.library.get_book(self._book["id"])
            except KeyError:
                self._book = {}; self._page = {}
        self._summaries = self.library.list_summaries(self._book["id"]) if self._book else []
        self._summary = next((record for record in self._summaries if record["id"] == self._summary.get("id")), {})
        if not self._summary and self._summaries:
            self._summary = self._summaries[-1]
        self.stateChanged.emit()

    @Slot(str)
    def openSummaries(self, book_id: str) -> None:
        try:
            if book_id:
                self._book = self.library.get_book(book_id)
            self._screen = "summaries"
            self.refresh()
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def selectSummary(self, summary_id: str) -> None:
        self._summary = next((record for record in self._summaries if record["id"] == summary_id), {})
        self.stateChanged.emit()

    @Slot(int)
    def openSummarySource(self, number: int) -> None:
        if self._summary and number in self._summary["source_pages"]:
            self.openPage(number)

    @Slot(str)
    def reviewSummaries(self, payload: str) -> None:
        try:
            if self.runner.running:
                raise RuntimeError("توجد مهمة جارية. علّقها أو ألغها قبل مراجعة الملخصات")
            config = json.loads(payload)
            book_id = self._book["id"]
            records = self.library.selected_summaries(book_id, config["ids"])
            pages = sorted({page for record in records for page in record["source_pages"]})
            task_id = self.library.create_task(
                book_id=book_id, start_page=min(pages), end_page=max(pages),
                key_id=config["key_id"], model=config.get("model") or DEFAULT_MODEL,
                prompt_id="default-summary", mode="summary", dpi=300, overwrite=False,
                summary_ids=config["ids"],
                review_batch_size=config.get("review_batch_size", 3),
            )
            self._task = self.library.task(task_id)
            self.runner.start(task_id)
            self._screen = "task"
            self.refresh()
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def deleteSummaries(self, payload: str) -> None:
        try:
            ids = json.loads(payload)
            if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
                raise ValueError("قائمة الملخصات غير صالحة")
            current = self._summary
            self.library.delete_summaries(self._book["id"], ids)
            remaining = self.library.list_summaries(self._book["id"])
            self._summary = next((r for r in remaining if r["id"] == current.get("id")), {})
            if not self._summary:
                self._summary = next((r for r in remaining if (r["task_id"] == current.get("task_id") if current.get("input_ids") else not r["input_ids"])), {})
            self.refresh()
            self._notify(f"حُذف {len(ids)} ملخص. ملف PDF وسجل الاستهلاك محفوظان")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def deleteSummaryReview(self, task_id: str) -> None:
        try:
            self.library.delete_summary_review(self._book["id"], task_id)
            self._summary = next((record for record in self._summaries if not record["input_ids"]), {})
            self.refresh()
            self._notify("حُذفت نتائج المراجعة. الملخصات الأصلية وسجل الاستهلاك محفوظان")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def exportSummary(self, destination: str) -> None:
        try:
            if not self._summary:
                raise ValueError("اختر ملخصًا لعرضه أولاً")
            path = local_path(destination)
            export_summary(SummaryDocument.model_validate(self._summary["document"]), path)
            self._notify("حُفظ الملخص في: " + str(path))
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str, str)
    def exportSummaries(self, destination: str, selection: str) -> None:
        try:
            ids = json.loads(selection)
            if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
                raise ValueError("حدد الملخصات المطلوب تصديرها")
            records = [record for record in self._summaries if record["id"] in ids]
            if len(records) != len(ids):
                raise ValueError("بعض الملخصات المحددة غير موجودة في الكتاب الحالي")
            path = local_path(destination)
            export_summaries(records, path)
            self._notify(f"صُدّر {len(records)} ملخصًا بكل أوراقها إلى: {path}")
        except Exception as exc:
            self._notify(str(exc))

    @staticmethod
    def _serial_requests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            try:
                numbers = [int(number) for number in json.loads(row.get("page_numbers") or "[]")]
            except (ValueError, TypeError):
                numbers = []
            if not numbers:
                numbers = [int(row["page_number"])]
            row["page_numbers"] = numbers
            if len(numbers) == 1:
                row["page_label"] = str(numbers[0])
            elif numbers == list(range(numbers[0], numbers[-1] + 1)):
                row["page_label"] = f"{numbers[0]} إلى {numbers[-1]}"
            else:
                row["page_label"] = "، ".join(map(str, numbers))
            if row.get("usage"):
                try:
                    usage = json.loads(row["usage"])
                    row["token_total"] = usage.get("total_token_count", usage.get("totalTokenCount", ""))
                except (ValueError, TypeError):
                    row["token_total"] = ""
            else:
                row["token_total"] = ""
        return rows

    def _notify(self, message: str) -> None:
        self._toast = message
        self.toastChanged.emit()
        self._toast_timer.start()

    def _save_notification_sound_setting(self) -> None:
        self.library.set_setting(
            "completion_sound",
            {
                "enabled": self._notification_sound_enabled,
                "sound_id": self._notification_sound_id,
            },
        )

    @Slot(bool)
    def setNotificationSoundEnabled(self, enabled: bool) -> None:
        self._notification_sound_enabled = enabled
        self._save_notification_sound_setting()
        self.stateChanged.emit()

    @Slot(str)
    def setNotificationSound(self, sound_id: str) -> None:
        if sound_id not in SYSTEM_SOUND_IDS:
            return
        self._notification_sound_id = sound_id
        self._save_notification_sound_setting()
        self.stateChanged.emit()

    @Slot()
    def previewNotificationSound(self) -> None:
        self._play_notification_sound()

    def _play_notification_sound(self) -> None:
        try:
            self._sound_player(self._notification_sound_id)
        except Exception:
            pass

    @Slot()
    def clearToast(self) -> None:
        self._toast_timer.stop()
        if self._toast:
            self._toast = ""
            self.toastChanged.emit()

    @Slot(str)
    def go(self, screen: str) -> None:
        self._screen = screen
        self.refresh()

    @Slot(str)
    def openTask(self, task_id: str) -> None:
        try:
            self._task = self.library.task(task_id)
            self._screen = "task"
            self.refresh()
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def importBook(self, source: str) -> None:
        try:
            book = self.library.add_book(local_path(source))
            self._book = book
            self._screen = "book"
            self.refresh()
            self._notify("أُضيف الكتاب وحُفظت كل صفحاته")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def renameCurrentBook(self, name: str) -> None:
        if not self._book:
            return
        try:
            self._book = self.library.rename_book(self._book["id"], name)
            self.refresh()
            self._notify("حُفظ اسم الكتاب")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def relinkBookPdf(self, source: str) -> None:
        if not self._book:
            return
        try:
            page_number = self._page.get("number")
            self._book = self.library.relink_book_pdf(
                self._book["id"], local_path(source)
            )
            self.refresh()
            if page_number:
                self.openPage(int(page_number))
            self._notify("حُدّث مسار ملف PDF وبقيت التحويلات محفوظة")
        except Exception as exc:
            self._notify(str(exc))

    @Slot()
    def deleteCurrentBook(self) -> None:
        if not self._book:
            return
        try:
            book_id = self._book["id"]
            self.library.delete_book(book_id)
            if self._task.get("book_id") == book_id:
                self._task = {}
            self._book = {}
            self._page = {}
            self._screen = "library"
            self.refresh()
            self._notify("حُذف الكتاب من المكتبة")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def openBook(self, book_id: str) -> None:
        try:
            self._book = self.library.get_book(book_id)
            self._screen = "book"
            self.stateChanged.emit()
        except Exception as exc:
            self._notify(str(exc))

    @Slot(int)
    def openPage(self, number: int) -> None:
        if not self._book:
            return
        try:
            self._page = self.library.get_page(self._book["id"], number)
            self._page["image_url"] = f"image://pages/{self._book['id']}/{number}?dpi=180"
            self._page["flat_lines"] = self._flatten_lines(self._page)
            self._screen = "review"
            self._draft_dirty = False
            self._save_state = "محفوظ"
            self.stateChanged.emit()
            self.pageLoaded.emit()
        except Exception as exc:
            self._notify(str(exc))

    @staticmethod
    def _flatten_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for region in page.get("regions", []):
            for line in region.get("lines", []):
                result.append({
                    **line,
                    "region_id": region["id"], "kind": region["kind"], "source": region["source"],
                    "column_index": region["column_index"], "region_order": region["reading_order"],
                })
        return sorted(result, key=lambda line: (line["region_order"], line["reading_order"]))

    @Slot(str)
    def updatePageRichText(self, content_html: str) -> None:
        if not self._page:
            return
        if (
            self._page.get("content_html", "") != content_html
            or self._page.get("content_format") != "html"
        ):
            self._page["content_html"] = content_html
            self._page["content_markdown"] = ""
            self._page["content_format"] = "html"
            self._mark_dirty()

    @Slot(str, str, str)
    def updatePageEditorContent(
        self, content_format: str, content_markdown: str, content_html: str
    ) -> None:
        if not self._page:
            return
        next_format = "markdown" if content_format == "markdown" else "html"
        next_markdown = content_markdown if next_format == "markdown" else ""
        if (
            self._page.get("content_format", "html") != next_format
            or self._page.get("content_markdown", "") != next_markdown
            or self._page.get("content_html", "") != content_html
        ):
            self._page["content_format"] = next_format
            self._page["content_markdown"] = next_markdown
            self._page["content_html"] = content_html
            self._mark_dirty()

    @Slot(str, int, str, bool)
    def commitPageRichText(
        self, book_id: str, page_number: int, content_html: str, approve: bool
    ) -> None:
        """Persist the editor's live HTML before saving or approving a page."""
        try:
            saved = self.library.save_page_content(
                book_id,
                page_number,
                content_html,
                reviewed=True if approve else None,
                reason="review" if approve else "manual_edit",
            )
            if (
                self._book.get("id") == book_id
                and self._page.get("number") == page_number
            ):
                saved["image_url"] = f"image://pages/{book_id}/{page_number}?dpi=180"
                saved["flat_lines"] = self._flatten_lines(saved)
                self._page = saved
                self._draft_dirty = False
                self._autosave.stop()
                self._save_state = "محفوظ"
            self.refresh()
            if approve:
                self._notify("اعتُمدت الصفحة")
        except Exception as exc:
            self._save_state = "تعذر الحفظ"
            self.stateChanged.emit()
            self._notify(str(exc))

    @Slot(str, int, str, str, str, bool)
    def commitPageEditorContent(
        self,
        book_id: str,
        page_number: int,
        content_format: str,
        content_markdown: str,
        content_html: str,
        approve: bool,
    ) -> None:
        """Persist Markdown pages while retaining the legacy HTML editor path."""
        try:
            markdown = content_markdown if content_format == "markdown" else None
            saved = self.library.save_page_content(
                book_id,
                page_number,
                content_html,
                reviewed=True if approve else None,
                reason="review" if approve else "manual_edit",
                content_markdown=markdown,
            )
            if (
                self._book.get("id") == book_id
                and self._page.get("number") == page_number
            ):
                saved["image_url"] = f"image://pages/{book_id}/{page_number}?dpi=180"
                saved["flat_lines"] = self._flatten_lines(saved)
                self._page = saved
                self._draft_dirty = False
                self._autosave.stop()
                self._save_state = "محفوظ"
            self.refresh()
            if approve:
                self._notify("اعتُمدت الصفحة")
        except Exception as exc:
            self._save_state = "تعذر الحفظ"
            self.stateChanged.emit()
            self._notify(str(exc))

    @Slot(str)
    def copyMarkdown(self, content_markdown: str) -> None:
        QGuiApplication.clipboard().setText(content_markdown)
        self._notify("نُسخ Markdown")

    def _mark_dirty(self) -> None:
        self._draft_dirty = True
        self._save_state = "جارٍ الحفظ"
        self._autosave.start()
        self.stateChanged.emit()

    @Slot()
    def savePage(self) -> None:
        self._save_draft()

    @Slot()
    def resetCurrentPageToExtraction(self) -> None:
        if not self._page or not self._book:
            return
        was_dirty = self._draft_dirty
        self._autosave.stop()
        self._draft_dirty = False
        try:
            self._page = self.library.reset_page_to_extraction(
                self._book["id"], self._page["number"]
            )
            self._page["image_url"] = (
                f"image://pages/{self._book['id']}/{self._page['number']}?dpi=180"
            )
            self._page["flat_lines"] = self._flatten_lines(self._page)
            self._save_state = "محفوظ"
            self.refresh()
            self.pageLoaded.emit()
            self._notify("أُعيد نص الصفحة إلى التحويل الأصلي")
        except Exception as exc:
            self._draft_dirty = was_dirty
            if was_dirty:
                self._autosave.start()
            self._save_state = "جارٍ الحفظ" if was_dirty else "تعذر الحفظ"
            self.stateChanged.emit()
            self._notify(str(exc))

    def _save_draft(self) -> None:
        if not self._draft_dirty or not self._page or not self._book:
            return
        try:
            self._page = self.library.save_page_content(
                self._book["id"], self._page["number"], self._page.get("content_html", ""),
                reason="manual_edit",
                content_markdown=(
                    self._page.get("content_markdown", "")
                    if self._page.get("content_format") == "markdown"
                    else None
                ),
            )
            self._page["image_url"] = f"image://pages/{self._book['id']}/{self._page['number']}?dpi=180"
            self._page["flat_lines"] = self._flatten_lines(self._page)
            self._draft_dirty = False; self._save_state = "محفوظ"
            self.refresh()
        except Exception as exc:
            self._save_state = "تعذر الحفظ"; self.stateChanged.emit(); self._notify(str(exc))

    @Slot()
    def approvePage(self) -> None:
        if not self._page or not self._book: return
        self._save_draft()
        try:
            self._page = self.library.save_page_content(
                self._book["id"], self._page["number"], self._page.get("content_html", ""),
                reviewed=True, reason="review",
                content_markdown=(
                    self._page.get("content_markdown", "")
                    if self._page.get("content_format") == "markdown"
                    else None
                ),
            )
            self._page["image_url"] = f"image://pages/{self._book['id']}/{self._page['number']}?dpi=180"
            self._page["flat_lines"] = self._flatten_lines(self._page)
            self.refresh(); self._notify("اعتُمدت الصفحة")
        except Exception as exc: self._notify(str(exc))

    @Slot(str, str)
    def createKey(self, name: str, secret: str) -> None:
        reference = uuid.uuid4().hex
        try:
            if not name.strip():
                raise ValueError("اكتب اسم المفتاح")
            self.secrets.set(reference, secret)
            self.library.add_key(name, reference)
            self.refresh(); self._notify("حُفظ المفتاح في مخزن كلمات المرور")
        except Exception as exc:
            self.secrets.delete(reference); self._notify(str(exc))

    @Slot(str)
    def deleteKey(self, key_id: str) -> None:
        secret: str | None = None
        try:
            metadata = self.library.key_metadata(key_id)
            try:
                secret = self.secrets.get(metadata["secret_ref"])
            except KeyError:
                pass
            self.secrets.delete(metadata["secret_ref"])
            try:
                self.library.delete_key(key_id)
            except Exception:
                if secret is not None:
                    self.secrets.set(metadata["secret_ref"], secret)
                raise
            self.refresh(); self._notify("حُذف المفتاح من ورّاق ومخزن كلمات المرور")
        except Exception as exc:
            self._notify(str(exc))

    @Slot(str)
    def refreshModels(self, key_id: str) -> None:
        if self._busy: return
        self._busy = True; self.stateChanged.emit()
        def work() -> None:
            try:
                meta = self.library.key_metadata(key_id)
                models = GeminiClient(self.secrets.get(meta["secret_ref"])).list_models()
                self.asyncResult.emit({"kind": "models", "value": models})
            except Exception as exc:
                self.asyncResult.emit({"kind": "error", "value": str(exc)})
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def resetUsageMeasurement(self) -> None:
        self._usage = self.library.reset_usage_measurement()
        self.stateChanged.emit(); self._notify("بدأت فترة قياس جديدة. لم يُحذف سجل الطلبات أو تتغير حصة Google.")

    @Slot(str, str, int, int, int)
    def setQuotaLimit(self, key_id: str, model: str, rpm: int, input_tpm: int, rpd: int) -> None:
        try:
            self.library.set_quota_limit(key_id, model, rpm, input_tpm, rpd)
            self.refresh(); self._notify("حُفظت الحدود المرجعية")
        except Exception as exc: self._notify(str(exc))

    @Slot(str, str, str, str)
    def savePrompt(self, prompt_id: str, name: str, mode: str, instructions: str) -> None:
        try:
            self.library.save_prompt(name, mode, instructions, prompt_id or None)
            self.refresh(); self._notify("حُفظ البرومبت")
        except Exception as exc: self._notify(str(exc))

    @Slot(str)
    def startConversion(self, payload: str) -> None:
        try:
            if self.runner.running:
                raise RuntimeError("توجد مهمة تحويل جارية. علّقها أو ألغها قبل بدء مهمة أخرى")
            config = json.loads(payload)
            mode = config.get("mode", "printed")
            default_prompts = {
                "printed": "default-printed", "manuscript": "default-manuscript",
                "translation": "default-translation", "summary": "default-summary",
            }
            task_id = self.library.create_task(
                book_id=config.get("book_id") or self._book["id"], start_page=int(config["start_page"]), end_page=int(config["end_page"]),
                key_id=config["key_id"], model=config.get("model") or DEFAULT_MODEL,
                prompt_id=config.get("prompt_id") or default_prompts.get(mode, "default-printed"),
                mode=mode, dpi=int(config.get("dpi", 300)),
                overwrite=bool(config.get("overwrite", False)),
                pages_per_request=int(config.get("pages_per_request", 1)),
                target_language=config.get("target_language", ""),
                summary_level=config.get("summary_level", ""),
                text_direction=config.get("text_direction", "rtl"),
                additional_instructions=config.get("additional_instructions", ""),
            )
            self._task = self.library.task(task_id); self._screen = "task"; self.stateChanged.emit()
            self.runner.start(task_id)
            self._task = self.library.task(task_id)
            self.refresh()
        except Exception as exc: self._notify(str(exc))

    @Slot()
    def pauseTask(self) -> None:
        try:
            if not self._task:
                return
            self.runner.request_pause(self._task["id"])
            self._task = self.library.task(self._task["id"])
            self.refresh()
            self._notify("سيُعلّق التحويل بعد حفظ الدفعة الحالية")
        except Exception as exc:
            self._notify(str(exc))

    @Slot()
    def stopTask(self) -> None:
        self.pauseTask()

    @Slot()
    def cancelTask(self) -> None:
        try:
            if not self._task:
                return
            self.runner.request_cancel(self._task["id"])
            self._task = self.library.task(self._task["id"])
            self.refresh()
            message = (
                "سيُلغى التحويل بعد حفظ الدفعة الحالية"
                if self._task.get("control_action") == "cancel"
                else "أُلغيت المهمة وبقيت الصفحات المحفوظة"
            )
            self._notify(message)
        except Exception as exc:
            self._notify(str(exc))

    @Slot()
    def resumeTask(self) -> None:
        try:
            if not self._task: return
            self.runner.start(self._task["id"])
            self._task = self.library.task(self._task["id"])
            self.refresh()
        except Exception as exc: self._notify(str(exc))

    @Slot()
    def openTaskPage(self) -> None:
        if not self._task:
            return
        try:
            self._book = self.library.get_book(self._task["book_id"])
            if self._task["mode"] == "summary" and self._task.get("summary_contract"):
                self.openSummaries(self._task["book_id"])
                records = [record for record in self._summaries if record["task_id"] == self._task["id"]]
                if records:
                    self.selectSummary(records[0 if self._task.get("summary_review_version") == 2 else -1]["id"])
                return
            page_number = int(
                self._task.get("current_page") or self._task.get("start_page") or 1
            )
            self.openPage(page_number)
        except Exception as exc:
            self._notify(str(exc))

    def _on_task_event(self, event: dict[str, Any]) -> None:
        self.taskEvent.emit(event)

    @Slot(object)
    def _apply_task_event(self, event: object) -> None:
        data = dict(event)
        if self._task and self._task.get("id") == data.get("task_id"):
            try: self._task = self.library.task(self._task["id"])
            except KeyError: pass
        self.refresh()
        state = data.get("state")
        if data.get("type") == "task" and state in {
            "completed", "completed_with_errors", "failed", "cancelled",
        }:
            messages = {
                "completed": "اكتملت مهمة التحويل",
                "completed_with_errors": "اكتملت المهمة مع صفحات تحتاج إعادة المحاولة",
                "failed": data.get("error", "فشل التحويل"),
                "cancelled": "أُلغيت مهمة التحويل وبقيت الصفحات المحفوظة",
            }
            if state == "completed" and self._task.get("summary_review_version") == 2 and self._task.get("id") == data.get("task_id"):
                messages["completed"] = f"اكتملت مراجعة {self._task['completed']} دفعات؛ النتائج في سلسلة مراجعة مستقلة"
                results = [record for record in self._summaries if record["task_id"] == data["task_id"]]
                if results:
                    self.selectSummary(results[0]["id"])
            self._notify(messages[state])
            if self._notification_sound_enabled:
                self._play_notification_sound()
        elif state == "failed":
            self._notify(data.get("error", "فشل التحويل"))

    @Slot(object)
    def _apply_async(self, result: object) -> None:
        data = dict(result)
        if data["kind"] == "models":
            self._busy = False
            self._models = data["value"]; self._notify("حُدّثت قائمة النماذج")
        elif data["kind"] == "export":
            self._exporting = False
            self._notify(data["value"]["message"] + " حُفظ في: " + data["path"])
        elif data["kind"] == "export_error":
            self._exporting = False
            self._notify(data["value"])
        else:
            self._busy = False
            self._notify(data["value"])
        self.stateChanged.emit()

    @Slot(str)
    def createBackup(self, destination: str) -> None:
        try:
            path = local_path(destination)
            if path.suffix != ".waraq-backup": path = path.with_suffix(".waraq-backup")
            create_backup(self.library, path); self._notify("اكتملت النسخة الاحتياطية")
        except Exception as exc: self._notify(str(exc))

    @Slot(str)
    def restoreBackup(self, source: str) -> None:
        try:
            restore_backup(self.library, local_path(source)); self._book = {}; self._page = {}; self.refresh(); self._screen = "library"; self._notify("استُعيدت النسخة الاحتياطية")
        except Exception as exc: self._notify(str(exc))

    @Slot(str)
    def exportBook(self, payload: str) -> None:
        if self._exporting:
            return
        try:
            config = json.loads(payload)
            destination = local_path(config["destination"])
            if not str(destination):
                raise ValueError("اختر مكان حفظ الملف")
            export_format = str(config.get("format") or "word").lower()
            export_options = {
                "word": (export_word, ".docx", "Word"),
                "markdown": (export_markdown, ".md", "Markdown"),
                "html": (export_html, ".html", "HTML"),
            }
            if export_format not in export_options:
                raise ValueError("صيغة التصدير غير مدعومة")
            exporter, suffix, format_label = export_options[export_format]
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            book_id = config.get("book_id") or self._book["id"]
            start_page = int(config["start_page"])
            end_page = int(config["end_page"])
            self._exporting = True
            self.stateChanged.emit()
            self._notify(
                f"بدأ إنشاء ملف {format_label}. يمكنك متابعة العمل وسيظهر إشعار عند اكتماله."
            )

            def work() -> None:
                try:
                    report = exporter(
                        self.library,
                        book_id,
                        start_page,
                        end_page,
                        destination,
                        include_unreviewed=bool(config.get("include_unreviewed")),
                    )
                    self.asyncResult.emit({"kind": "export", "value": report, "path": str(destination)})
                except Exception as exc:
                    self.asyncResult.emit({"kind": "export_error", "value": str(exc)})

            threading.Thread(target=work, daemon=True).start()
        except Exception as exc:
            self._exporting = False
            self.stateChanged.emit()
            self._notify(str(exc))

    @Slot(str)
    def reveal(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(local_path(path))))
