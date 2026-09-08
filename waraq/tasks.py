from __future__ import annotations

import threading
import time
from collections.abc import Callable
from math import ceil
from typing import Any

from .database import Library, RequestThrottleDelay
from .gemini_client import GeminiClient, GeminiFailure
from .pdf import render_page
from .secrets import SecretStore


ProgressCallback = Callable[[dict[str, Any]], None]


class ConversionRunner:
    """Run one durable conversion task independently from the visible screen."""

    def __init__(self, library: Library, secrets: SecretStore, progress: ProgressCallback | None = None):
        self.library = library
        self.secrets = secrets
        self.progress = progress or (lambda _event: None)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, task_id: str) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("توجد مهمة تحويل جارية")
            self.library.prepare_task_run(task_id)
            self._thread = threading.Thread(target=self._run, args=(task_id,), name=f"waraq-{task_id[:8]}", daemon=True)
            self._thread.start()

    def request_pause(self, task_id: str) -> None:
        self.library.request_task_action(task_id, "pause")

    def request_cancel(self, task_id: str) -> None:
        self.library.request_task_action(task_id, "cancel")

    def request_stop(self, task_id: str) -> None:
        self.request_pause(task_id)

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _run(self, task_id: str) -> None:
        task = self.library.task(task_id)
        try:
            key_meta = self.library.key_metadata(task["key_id"])
            client = GeminiClient(self.secrets.get(key_meta["secret_ref"]))
            pages = self.library.page_numbers_for_task(task)
            batch_size = max(1, int(task.get("pages_per_request", 1)))
            batches = [pages[index:index + batch_size] for index in range(0, len(pages), batch_size)]
            for numbers in batches:
                if self._apply_requested_action(task_id):
                    return
                while True:
                    try:
                        request_id = self.library.start_request(task, numbers)
                        break
                    except RequestThrottleDelay as delay:
                        self.progress({
                            "type": "page", "state": "waiting", "page": numbers[0],
                            "pages": numbers,
                            "task_id": task_id, "wait_seconds": ceil(delay.wait_seconds),
                        })
                        if self._wait_for_throttle(task_id, delay.wait_seconds):
                            return
                self.library.start_task_pages(task_id, numbers)
                self.progress({
                    "type": "page", "state": "sending", "page": numbers[0],
                    "pages": numbers, "task_id": task_id,
                })
                completed_pages: set[int] = set()
                request_finished = False
                try:
                    source = self.library.page_path(task["book_id"])
                    rendered = [
                        (number, render_page(source, number, task["dpi"]))
                        for number in numbers
                    ]
                    if len(rendered) == 1:
                        number, image = rendered[0]
                        single = client.extract(
                            image, model=task["model"], prompt=task["prompt_snapshot"]
                        )
                        result_pages = {number: single.page}
                        raw = single.raw
                        usage = single.usage
                    else:
                        batch = client.extract_pages(
                            rendered, model=task["model"], prompt=task["prompt_snapshot"]
                        )
                        result_pages = batch.pages
                        raw = batch.raw
                        usage = batch.usage
                    self.library.finish_request(
                        request_id, "success", usage=usage, response=raw
                    )
                    request_finished = True
                    for number in numbers:
                        page = result_pages[number]
                        self.library.apply_extraction(
                            task["book_id"], number, page, page.model_dump_json()
                        )
                        self.library.finish_task_page(task_id, number, "completed")
                        completed_pages.add(number)
                        self.progress({
                            "type": "page", "state": "saved", "page": number,
                            "pages": numbers, "task_id": task_id, "usage": usage,
                        })
                except GeminiFailure as exc:
                    self.library.finish_request(request_id, "error", usage=exc.usage, error=str(exc), http_status=exc.status)
                    self._fail_batch(task, task_id, numbers, completed_pages, str(exc))
                    if self._apply_requested_action(task_id):
                        return
                    if exc.status in {401, 403, 404, 429}:
                        self.library.update_task(task_id, state="failed", control_action="", current_page=None)
                        self.progress({"type": "task", "state": "failed", "task_id": task_id, "error": str(exc)})
                        return
                except Exception as exc:
                    message = str(exc)
                    if not request_finished:
                        self.library.finish_request(request_id, "error", error=message)
                    self._fail_batch(task, task_id, numbers, completed_pages, message)
            if self._apply_requested_action(task_id):
                return
            final = self.library.task(task_id)
            state = "completed" if not final["failed"] else "completed_with_errors"
            self.library.update_task(task_id, state=state, control_action="", current_page=None)
            self.progress({"type": "task", "state": state, "task_id": task_id})
        except Exception as exc:
            self.library.update_task(task_id, state="failed", control_action="", current_page=None, error=str(exc))
            self.progress({"type": "task", "state": "failed", "task_id": task_id, "error": str(exc)})

    def _fail_batch(
        self,
        task: dict[str, Any],
        task_id: str,
        numbers: list[int],
        completed_pages: set[int],
        message: str,
    ) -> None:
        for number in numbers:
            if number in completed_pages:
                continue
            self.library.mark_page_failed(task["book_id"], number, message)
            self.library.finish_task_page(task_id, number, "failed", message)
            self.progress({
                "type": "page", "state": "failed", "page": number,
                "pages": numbers, "task_id": task_id, "error": message,
            })

    def _wait_for_throttle(self, task_id: str, wait_seconds: float) -> bool:
        deadline = time.monotonic() + wait_seconds
        while True:
            if self._apply_requested_action(task_id):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.25, remaining))

    def _apply_requested_action(self, task_id: str) -> bool:
        task = self.library.task(task_id)
        action = task.get("control_action")
        if action not in {"pause", "cancel"}:
            return False
        state = "paused" if action == "pause" else "cancelled"
        self.library.update_task(
            task_id, state=state, control_action="", stop_requested=0,
            current_page=None,
        )
        self.progress({"type": "task", "state": state, "task_id": task_id})
        return True
