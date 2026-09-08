from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from .backup import create_backup, restore_backup
from .database import Library
from .exporter import export_word
from .gemini_client import DEFAULT_MODEL, GeminiClient
from .secrets import SecretStore
from .tasks import ConversionRunner


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

    def __init__(self, library: Library, secrets: SecretStore):
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
        self._busy = False
        self._exporting = False
        self._toast = ""
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(5_000)
        self._toast_timer.timeout.connect(self.clearToast)
        self._save_state = "محفوظ"
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
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    exporting = Property(bool, lambda self: self._exporting, notify=stateChanged)
    toast = Property(str, lambda self: self._toast, notify=toastChanged)
    saveState = Property(str, lambda self: self._save_state, notify=stateChanged)
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
        self.stateChanged.emit()

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
        if self._page.get("content_html", "") != content_html:
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

    def _mark_dirty(self) -> None:
        self._draft_dirty = True
        self._save_state = "جارٍ الحفظ"
        self._autosave.start()
        self.stateChanged.emit()

    @Slot()
    def savePage(self) -> None:
        self._save_draft()

    def _save_draft(self) -> None:
        if not self._draft_dirty or not self._page or not self._book:
            return
        try:
            self._page = self.library.save_page_content(
                self._book["id"], self._page["number"], self._page.get("content_html", ""),
                reason="manual_edit",
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
            self.refresh(); self._notify("حُفظت نسخة البرومبت")
        except Exception as exc: self._notify(str(exc))

    @Slot(str)
    def startConversion(self, payload: str) -> None:
        try:
            if self.runner.running:
                raise RuntimeError("توجد مهمة تحويل جارية. علّقها أو ألغها قبل بدء مهمة أخرى")
            config = json.loads(payload)
            task_id = self.library.create_task(
                book_id=config.get("book_id") or self._book["id"], start_page=int(config["start_page"]), end_page=int(config["end_page"]),
                key_id=config["key_id"], model=config.get("model") or DEFAULT_MODEL,
                prompt_id=config.get("prompt_id") or ("default-manuscript" if config.get("mode") == "manuscript" else "default-printed"),
                mode=config.get("mode", "printed"), dpi=int(config.get("dpi", 300)),
                overwrite=bool(config.get("overwrite", False)),
                pages_per_request=int(config.get("pages_per_request", 1)),
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
        if data.get("state") == "failed": self._notify(data.get("error", "فشل التحويل"))
        elif data.get("type") == "task" and data.get("state") == "completed": self._notify("اكتملت مهمة التحويل")
        elif data.get("type") == "task" and data.get("state") == "completed_with_errors": self._notify("اكتملت المهمة مع صفحات تحتاج إعادة المحاولة")

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
            book_id = config.get("book_id") or self._book["id"]
            start_page = int(config["start_page"])
            end_page = int(config["end_page"])
            self._exporting = True
            self.stateChanged.emit()
            self._notify("بدأ إنشاء ملف Word. يمكنك متابعة العمل وسيظهر إشعار عند اكتماله.")

            def work() -> None:
                try:
                    report = export_word(
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
