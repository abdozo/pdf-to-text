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
from .summaries import author_framing, review_context, review_input, validate_review


ProgressCallback = Callable[[dict[str, Any]], None]


class ConversionRunner:
    """Run one durable conversion task independently from the visible screen."""

    def __init__(self, library: Library, secrets: SecretStore, progress: ProgressCallback | None = None):
        self.library = library
        self.secrets = secrets
        self.progress = progress or (lambda _event: None)
        self._thread: threading.Thread | None = None
        self._active_task_id: str | None = None
        self._cancel_events: dict[str, threading.Event] = {}
        self._clients: dict[str, Any] = {}
        self._request_ids: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, task_id: str) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("توجد مهمة تحويل جارية")
            self.library.prepare_task_run(task_id)
            cancel_event = threading.Event()
            self._cancel_events[task_id] = cancel_event
            self._active_task_id = task_id
            self._thread = threading.Thread(
                target=self._run,
                args=(task_id, cancel_event),
                name=f"waraq-{task_id[:8]}",
                daemon=True,
            )
            self._thread.start()

    def request_pause(self, task_id: str) -> None:
        self.library.request_task_action(task_id, "pause")

    def request_cancel(self, task_id: str) -> None:
        with self._lock:
            cancel_event = self._cancel_events.get(task_id)
            if cancel_event is not None:
                cancel_event.set()
            client = self._clients.pop(task_id, None)
            request_id = self._request_ids.get(task_id)
            if self._active_task_id == task_id:
                self._active_task_id = None
                self._thread = None
        self.library.request_task_action(task_id, "cancel")
        if request_id:
            self.library.finish_request(
                request_id,
                "cancelled",
                error="ألغى المستخدم مهمة التحويل",
            )
        if client is not None:
            threading.Thread(
                target=self._close_client,
                args=(client,),
                name=f"waraq-cancel-{task_id[:8]}",
                daemon=True,
            ).start()
        self.progress({"type": "task", "state": "cancelled", "task_id": task_id})

    def request_stop(self, task_id: str) -> None:
        self.request_pause(task_id)

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def _run(self, task_id: str, cancel_event: threading.Event) -> None:
        client: Any = None
        task = self.library.task(task_id)
        try:
            key_meta = self.library.key_metadata(task["key_id"])
            client = GeminiClient(self.secrets.get(key_meta["secret_ref"]))
            with self._lock:
                cancelled_before_client_ready = cancel_event.is_set()
                if not cancelled_before_client_ready:
                    self._clients[task_id] = client
            if cancelled_before_client_ready:
                self._close_client(client)
                return
            if task.get("summary_review_version") == 2:
                self._run_summary_review(task, client, cancel_event)
                return
            pages = self.library.page_numbers_for_task(task)
            batch_size = max(1, int(task.get("pages_per_request", 1)))
            batches = [pages[index:index + batch_size] for index in range(0, len(pages), batch_size)]
            is_summary = task["mode"] == "summary" and bool(task.get("summary_contract"))
            review_text = ""
            if is_summary:
                import json
                input_ids = json.loads(task.get("summary_input_ids") or "[]")
                if input_ids:
                    review_text, review_pages = review_input(
                        self.library.selected_summaries(task["book_id"], input_ids)
                    )
                    if pages and pages != review_pages:
                        raise ValueError("صفحات مراجعة الملخصات غير متطابقة")
                    batches = [pages] if pages else []
                else:
                    # Retry the original batches, rather than joining gaps after errors.
                    groups: dict[int, list[int]] = {}
                    for number in pages:
                        groups.setdefault((number - task["start_page"]) // batch_size, []).append(number)
                    batches = list(groups.values())
            for numbers in batches:
                if cancel_event.is_set():
                    return
                if self._apply_requested_action(task_id):
                    return
                while True:
                    try:
                        request_id = self.library.start_request(task, numbers)
                        with self._lock:
                            self._request_ids[task_id] = request_id
                        break
                    except RequestThrottleDelay as delay:
                        self.progress({
                            "type": "page", "state": "waiting", "page": numbers[0],
                            "pages": numbers,
                            "task_id": task_id, "wait_seconds": ceil(delay.wait_seconds),
                        })
                        if self._wait_for_throttle(task_id, delay.wait_seconds):
                            return
                if cancel_event.is_set():
                    return
                self.library.start_task_pages(task_id, numbers)
                self.progress({
                    "type": "page", "state": "sending", "page": numbers[0],
                    "pages": numbers, "task_id": task_id,
                })
                completed_pages: set[int] = set()
                request_finished = False
                try:
                    rendered = []
                    if not review_text:
                        source = self.library.page_path(task["book_id"])
                        rendered = [
                            (number, render_page(source, number, task["dpi"]))
                            for number in numbers
                        ]
                    if is_summary:
                        summary = client.summarize(
                            rendered, model=task["model"], prompt=task["prompt_snapshot"],
                            source_pages=numbers, review_text=review_text,
                        )
                        raw, usage = summary.raw, summary.usage
                    elif len(rendered) == 1:
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
                    if cancel_event.is_set():
                        return
                    self.library.finish_request(
                        request_id, "success", usage=usage, response=raw
                    )
                    with self._lock:
                        if self._request_ids.get(task_id) == request_id:
                            self._request_ids.pop(task_id, None)
                    request_finished = True
                    if is_summary:
                        summary = self._polish_summary(task, client, summary, cancel_event)
                        if cancel_event.is_set():
                            return
                        summary_id = self.library.save_summary(task_id, numbers, summary.document)
                        completed_pages.update(numbers)
                        self.progress({
                            "type": "page", "state": "saved", "page": numbers[0],
                            "pages": numbers, "task_id": task_id, "usage": usage,
                            "summary_id": summary_id,
                        })
                        continue
                    for number in numbers:
                        if cancel_event.is_set():
                            return
                        page = result_pages[number]
                        self.library.apply_extraction(
                            task["book_id"], number, page, page.model_dump_json(),
                            text_direction=(task["text_direction"] if task["mode"] == "translation" else "auto"),
                        )
                        self.library.finish_task_page(task_id, number, "completed")
                        completed_pages.add(number)
                        self.progress({
                            "type": "page", "state": "saved", "page": number,
                            "pages": numbers, "task_id": task_id, "usage": usage,
                        })
                except GeminiFailure as exc:
                    if cancel_event.is_set():
                        return
                    if not request_finished:
                        self.library.finish_request(request_id, "error", usage=exc.usage, error=str(exc), http_status=exc.status)
                    with self._lock:
                        if self._request_ids.get(task_id) == request_id:
                            self._request_ids.pop(task_id, None)
                    self._fail_batch(task, task_id, numbers, completed_pages, str(exc))
                    if self._apply_requested_action(task_id):
                        return
                    if exc.status in {401, 403, 404, 429}:
                        self.library.update_task(task_id, state="failed", control_action="", current_page=None)
                        self.progress({"type": "task", "state": "failed", "task_id": task_id, "error": str(exc)})
                        return
                except Exception as exc:
                    if cancel_event.is_set():
                        return
                    message = str(exc)
                    if not request_finished:
                        self.library.finish_request(request_id, "error", error=message)
                        with self._lock:
                            if self._request_ids.get(task_id) == request_id:
                                self._request_ids.pop(task_id, None)
                    self._fail_batch(task, task_id, numbers, completed_pages, message)
            if cancel_event.is_set():
                return
            if self._apply_requested_action(task_id):
                return
            final = self.library.task(task_id)
            state = "completed" if not final["failed"] else "completed_with_errors"
            self.library.update_task(task_id, state=state, control_action="", current_page=None)
            self.progress({"type": "task", "state": state, "task_id": task_id})
        except Exception as exc:
            if cancel_event.is_set():
                return
            self.library.update_task(task_id, state="failed", control_action="", current_page=None, error=str(exc))
            self.progress({"type": "task", "state": "failed", "task_id": task_id, "error": str(exc)})
        finally:
            current_thread = threading.current_thread()
            with self._lock:
                client_to_close = self._clients.pop(task_id, None)
                self._request_ids.pop(task_id, None)
                self._cancel_events.pop(task_id, None)
                if self._thread is current_thread:
                    self._thread = None
                    self._active_task_id = None
            self._close_client(client_to_close)

    @staticmethod
    def _close_client(client: Any) -> None:
        close = getattr(client, "close", None)
        if not callable(close):
            return
        try:
            close()
        except Exception:
            pass

    def _run_summary_review(self, task: dict[str, Any], client: Any, cancel: threading.Event) -> None:
        task_id = task["id"]
        units = self.library.review_units(task_id)
        for index, unit in enumerate(units):
            if unit["state"] == "completed":
                continue
            if cancel.is_set() or self._apply_requested_action(task_id):
                return
            if index and units[index - 1]["result"] is None:
                raise RuntimeError("أكمل دفعة المراجعة السابقة قبل متابعة الترابط")
            previous = review_context(units[index - 1]["result"], tail=True) if index else None
            following = review_context(units[index + 1]["target"], tail=False) if index + 1 < len(units) else None
            numbers = sorted({page for doc in (unit["target"], previous, following) if doc for page in doc["source_pages"]})
            while True:
                if cancel.is_set() or self._apply_requested_action(task_id):
                    return
                try:
                    request_id = self.library.start_request(task, numbers)
                    with self._lock:
                        self._request_ids[task_id] = request_id
                    break
                except RequestThrottleDelay as delay:
                    self.progress({"type": "page", "state": "waiting", "task_id": task_id,
                                   "pages": numbers, "page": numbers[0], "wait_seconds": ceil(delay.wait_seconds)})
                    if self._wait_for_throttle(task_id, delay.wait_seconds):
                        return
            request_finished = False
            try:
                if cancel.is_set():
                    return
                self.library.start_review_unit(task_id, unit["ordinal"])
                self.progress({"type": "review", "state": "sending", "task_id": task_id,
                               "review_current": index + 1, "review_total": len(units)})
                result = client.review_summary(
                    model=task["model"], prompt=task["prompt_snapshot"],
                    target=unit["target"], previous=previous, following=following,
                )
                if cancel.is_set():
                    return
                validate_review(result.document, unit["target"], previous, following)
                self.library.finish_request(request_id, "success", response=result.raw, usage=result.usage)
                request_finished = True
                with self._lock:
                    self._request_ids.pop(task_id, None)
                result = self._polish_summary(task, client, result, cancel)
                if cancel.is_set():
                    return
                validate_review(result.document, unit["target"], previous, following)
                result_id = self.library.save_review_unit(task_id, unit["ordinal"], result.document)
                unit["result"] = result.document.model_dump()
                unit["state"] = "completed"
                self.progress({"type": "review", "state": "saved", "task_id": task_id,
                               "summary_id": result_id, "review_current": index + 1, "review_total": len(units)})
            except Exception as exc:
                if cancel.is_set():
                    return
                if not request_finished:
                    self.library.finish_request(request_id, "error", error=str(exc),
                                                usage=getattr(exc, "usage", None), http_status=getattr(exc, "status", None))
                self.library.fail_review_unit(task_id, unit["ordinal"], str(exc))
                self.progress({"type": "task", "state": "failed", "task_id": task_id, "error": str(exc)})
                return
            finally:
                with self._lock:
                    if self._request_ids.get(task_id) == request_id:
                        self._request_ids.pop(task_id, None)
        if not cancel.is_set() and not self._apply_requested_action(task_id):
            self.library.update_task(task_id, state="completed", control_action="", current_page=None)
            self.progress({"type": "task", "state": "completed", "task_id": task_id})

    def _polish_summary(self, task, client, result, cancel):
        """Bounded editorial repair, with each real request accounted for separately."""
        task_id = task["id"]
        for _attempt in range(2):
            if cancel.is_set() or not author_framing(result.document):
                return result
            while True:
                if cancel.is_set():
                    return result
                try:
                    request_id = self.library.start_request(task, result.document.source_pages)
                    with self._lock:
                        self._request_ids[task_id] = request_id
                    break
                except RequestThrottleDelay as delay:
                    self.progress({"type": "page", "state": "waiting", "task_id": task_id,
                                   "wait_seconds": ceil(delay.wait_seconds)})
                    # Finish this batch before honoring pause; cancellation remains immediate.
                    if cancel.wait(delay.wait_seconds):
                        return result
            try:
                self.progress({"type": "review", "state": "polishing", "task_id": task_id})
                result = client.polish_summary(result.document, model=task["model"])
                if cancel.is_set():
                    return result
                self.library.finish_request(request_id, "success", response=result.raw, usage=result.usage)
            except Exception as exc:
                if not cancel.is_set():
                    self.library.finish_request(request_id, "error", error=str(exc),
                                                usage=getattr(exc, "usage", None), http_status=getattr(exc, "status", None))
                raise
            finally:
                with self._lock:
                    if self._request_ids.get(task_id) == request_id:
                        self._request_ids.pop(task_id, None)
        # Editorial wording is advisory. A valid, referenced result must not block
        # the remaining batches merely because an author mention remains.
        return result

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
            if not (task["mode"] == "summary" and task.get("summary_contract")):
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
        if task.get("state") == "cancelled":
            return True
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
