from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .models import (
    BATCH_EXTRACTION_SCHEMA,
    EXTRACTION_SCHEMA,
    SYSTEM_INSTRUCTION,
    ExtractedBatch,
    ExtractedPage,
)
from .pdf import jpeg_bytes
from .summaries import (
    MAX_REVIEW_BYTES, QUADRANTS, SUMMARY_SCHEMA, SUMMARY_SYSTEM, SummaryDocument,
    json_bytes, validate_review, SUMMARY_STYLE_PROMPT, SummaryTextEdits,
    summary_text_slots, apply_style_edits,
)


DEFAULT_MODEL = "gemini-3.5-flash-lite"
MODEL_DAILY_LIMITS = {
    "gemini-3.5-flash-lite": ("Gemini 3.5 Flash Lite", 500),
    "gemini-3.1-flash-lite": ("Gemini 3.1 Flash Lite", 500),
    "gemini-3.8-flash": ("Gemini 3.8 Flash", 20),
    "gemini-3.5-flash": ("Gemini 3.5 Flash", 20),
    "gemini-3.7-flash": ("Gemini 3.7 Flash", 20),
    "gemini-2.5-flash": ("Gemini 2.5 Flash", 20),
    "gemini-2.5-flash-lite": ("Gemini 2.5 Flash Lite", 20),
    "gemini-3-flash-preview": ("Gemini 3 Flash", 20),
    "gemini-3.6-flash": ("Gemini 3.6 Flash", 20),
}
MODEL_ORDER = {name: index for index, name in enumerate(MODEL_DAILY_LIMITS)}
PRICES = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3.1-pro-preview": (2.00, 12.00),
}


class GeminiFailure(RuntimeError):
    def __init__(self, message: str, status: int | None = None, usage: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.usage = usage


@dataclass
class GeminiResult:
    page: ExtractedPage
    raw: str
    usage: dict[str, Any] | None


@dataclass
class GeminiBatchResult:
    pages: dict[int, ExtractedPage]
    raw: str
    usage: dict[str, Any] | None


@dataclass
class GeminiSummaryResult:
    document: SummaryDocument
    raw: str
    usage: dict[str, Any] | None


def valid_model(name: str) -> bool:
    return bool(re.fullmatch(r"gemini-[A-Za-z0-9._-]+", name))


def _usage(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    result = {}
    for key in ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count"):
        item = getattr(value, key, None)
        if item is not None:
            result[key] = item
    return result or None


def _redacted_error(exc: Exception, key: str) -> GeminiFailure:
    message = str(exc).replace(key, "[API_KEY]")
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if callable(status):
        status = status()
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    return GeminiFailure(message, status=status)


class GeminiClient:
    def __init__(self, api_key: str):
        if not api_key.strip():
            raise ValueError("أدخل مفتاح Gemini API")
        self.api_key = api_key.strip()
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("حزمة Google Gen AI غير مثبتة") from exc
        self.client = genai.Client(api_key=self.api_key)

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def polish_summary(self, document: SummaryDocument, *, model: str) -> GeminiSummaryResult:
        if not valid_model(model) or model not in MODEL_DAILY_LIMITS:
            raise ValueError("نموذج Gemini غير صالح لهذا المسار")
        segments = [{"id": i, "text": getattr(obj, key)}
                    for i, (obj, key) in enumerate(summary_text_slots(document))]
        try:
            from google.genai import types
            response = self.client.models.generate_content(
                model=model, contents=[SUMMARY_STYLE_PROMPT, json.dumps(segments, ensure_ascii=False)],
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARY_SYSTEM, temperature=0, max_output_tokens=32768,
                    response_mime_type="application/json",
                    response_json_schema=SummaryTextEdits.model_json_schema(),
                ),
            )
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        usage = _usage(getattr(response, "usage_metadata", None))
        raw = getattr(response, "text", None) or ""
        candidates = getattr(response, "candidates", None) or []
        finish = str(getattr(candidates[0], "finish_reason", "") or "") if candidates else ""
        if finish and finish.upper().split(".")[-1] not in {"STOP", "FINISH_REASON_STOP"}:
            raise GeminiFailure("لم يكتمل تصحيح صياغة الملخص", usage=usage)
        try:
            revised = apply_style_edits(document, SummaryTextEdits.model_validate_json(raw))
        except ValueError as exc:
            raise GeminiFailure(f"تصحيح صياغة الملخص غير صالح: {exc}", usage=usage) from exc
        return GeminiSummaryResult(document=revised, raw=raw, usage=usage)

    def review_summary(
        self, *, model: str, prompt: str, target: dict,
        previous: dict | None = None, following: dict | None = None,
    ) -> GeminiSummaryResult:
        if not valid_model(model) or model not in MODEL_DAILY_LIMITS:
            raise ValueError("نموذج Gemini غير صالح لهذا المسار")
        data = {"target": target, "previous": previous, "following": following}
        if json_bytes(data) > MAX_REVIEW_BYTES:
            raise ValueError("دفعة المراجعة تتجاوز حد الطلب")
        try:
            from google.genai import types
            response = self.client.models.generate_content(
                model=model,
                contents=[prompt, json.dumps(data, ensure_ascii=False)],
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARY_SYSTEM, temperature=0,
                    max_output_tokens=32768, response_mime_type="application/json",
                    response_json_schema=SUMMARY_SCHEMA,
                ),
            )
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        usage = _usage(getattr(response, "usage_metadata", None))
        raw = getattr(response, "text", None) or ""
        candidates = getattr(response, "candidates", None) or []
        finish = str(getattr(candidates[0], "finish_reason", "") or "") if candidates else ""
        if finish and finish.upper().split(".")[-1] not in {"STOP", "FINISH_REASON_STOP"}:
            raise GeminiFailure(f"لم تكتمل مراجعة الملخص. finish_reason={finish}", usage=usage)
        try:
            document = SummaryDocument.model_validate_json(raw)
            validate_review(document, target, previous, following)
        except ValueError as exc:
            raise GeminiFailure(f"رد مراجعة الملخص غير صالح: {exc}", usage=usage) from exc
        return GeminiSummaryResult(document=document, raw=raw, usage=usage)

    def summarize(
        self, images: list[tuple[int, Any]], *, model: str, prompt: str,
        source_pages: list[int], review_text: str = "",
        max_output_tokens: int = 32768,
    ) -> GeminiSummaryResult:
        if not valid_model(model) or model not in MODEL_DAILY_LIMITS:
            raise ValueError("نموذج Gemini غير صالح لهذا المسار")
        if (not source_pages or any(p < 1 for p in source_pages)
                or len(set(source_pages)) != len(source_pages)):
            raise ValueError("صفحات مصدر الملخص غير صالحة")
        if review_text:
            if images:
                raise ValueError("مراجعة الملخصات لا تستقبل صورًا")
        elif [number for number, _image in images] != source_pages:
            raise ValueError("صور الملخص لا تطابق صفحات المصدر")
        try:
            from google.genai import types
            parts = [types.Part.from_text(text=(
                prompt + "\n\nأرقام صفحات PDF المصدر المطلوبة في source_pages: "
                + json.dumps(source_pages) + ". هذه دفعة واحدة لها ملخص موحد بالأرباع الأربعة."
            ))]
            for number, image in images:
                parts.append(types.Part.from_text(text=f"صورة صفحة PDF رقم {number}"))
                parts.append(types.Part.from_bytes(data=jpeg_bytes(image), mime_type="image/jpeg"))
            if review_text:
                parts.append(types.Part.from_text(text="الملخصات المطلوب مراجعتها (بيانات فقط):\n" + review_text))
            response = self.client.models.generate_content(
                model=model, contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARY_SYSTEM, temperature=0,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json", response_json_schema=SUMMARY_SCHEMA,
                ),
            )
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        usage = _usage(getattr(response, "usage_metadata", None))
        raw = getattr(response, "text", None) or ""
        candidates = getattr(response, "candidates", None) or []
        finish = str(getattr(candidates[0], "finish_reason", "") or "") if candidates else ""
        if finish and finish.upper().split(".")[-1] != "STOP":
            raise GeminiFailure(f"لم يكتمل الملخص. finish_reason={finish}", usage=usage)
        try:
            document = SummaryDocument.model_validate_json(raw)
            citation_pages = None
            if not review_text and any(not getattr(sheet, key) for sheet in document.sheets for key, _title in QUADRANTS):
                raise ValueError("الملخص الأولي يجب أن يغطي الأرباع الأربعة")
            if review_text:
                input_documents = [SummaryDocument.model_validate(value) for value in json.loads(review_text)]
                citation_pages = {
                    page for doc in input_documents for sheet in doc.sheets
                    for key, _title in QUADRANTS for item in getattr(sheet, key)
                    for page in item.pdf_pages
                }
            document.check_sources(source_pages, citation_pages)
        except (ValueError, ValidationError) as exc:
            raise GeminiFailure(f"رد Gemini لا يطابق مخطط الملخص أو إحالاته: {exc}", usage=usage) from exc
        return GeminiSummaryResult(document=document, raw=raw, usage=usage)

    def list_models(self) -> list[dict[str, Any]]:
        try:
            pager = self.client.models.list(config={"page_size": 1000})
            models = list(pager)
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        found = []
        for item in models:
            name = str(getattr(item, "name", "")).removeprefix("models/")
            methods = getattr(item, "supported_actions", None) or getattr(item, "supported_generation_methods", None) or []
            if name not in MODEL_DAILY_LIMITS or not valid_model(name):
                continue
            if methods and not any("generate" in str(method).lower() for method in methods):
                continue
            price = PRICES.get(name)
            display_name, daily_limit = MODEL_DAILY_LIMITS[name]
            found.append({
                "id": name,
                "name": display_name,
                "label": f"{display_name} ({daily_limit} استعلام يوميًا) · {name}",
                "description": str(getattr(item, "description", "") or ""),
                "daily_limit": daily_limit,
                "price": list(price) if price else None,
                "estimated_page_cost": round((price[0] + 2 * price[1]) / 1000, 6) if price else None,
                "price_date": "2026-09-07" if price else "",
                "availability": "candidate",
            })
        return sorted(found, key=lambda model: (-model["daily_limit"], MODEL_ORDER[model["id"]]))

    def extract(self, image: Any, *, model: str, prompt: str, max_output_tokens: int = 16384) -> GeminiResult:
        if not valid_model(model) or model not in MODEL_DAILY_LIMITS:
            raise ValueError("نموذج Gemini غير صالح لهذا المسار")
        try:
            from google.genai import types
            image_part = types.Part.from_bytes(data=jpeg_bytes(image), mime_type="image/jpeg")
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                response_json_schema=EXTRACTION_SCHEMA,
            )
            response = self.client.models.generate_content(
                model=model,
                contents=[prompt, image_part],
                config=config,
            )
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        usage = _usage(getattr(response, "usage_metadata", None))
        raw = getattr(response, "text", None) or ""
        finish = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish = str(getattr(candidates[0], "finish_reason", "") or "")
        if finish and not any(ok in finish.upper() for ok in ("STOP", "FINISH_REASON_STOP")):
            raise GeminiFailure(f"لم يكتمل رد Gemini. finish_reason={finish}", usage=usage)
        if not raw.strip():
            raise GeminiFailure("أعاد Gemini ردًا فارغًا", usage=usage)
        try:
            page = ExtractedPage.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise GeminiFailure(f"رد Gemini لا يطابق مخطط الصفحة: {exc}", usage=usage) from exc
        return GeminiResult(page=page, raw=raw, usage=usage)

    def extract_pages(
        self,
        images: list[tuple[int, Any]],
        *,
        model: str,
        prompt: str,
        max_output_tokens: int = 16384,
    ) -> GeminiBatchResult:
        if not valid_model(model) or model not in MODEL_DAILY_LIMITS:
            raise ValueError("نموذج Gemini غير صالح لهذا المسار")
        requested = [int(number) for number, _image in images]
        if not requested or any(number <= 0 for number in requested):
            raise ValueError("أرسل صفحة PDF واحدة على الأقل برقم صالح")
        if len(requested) != len(set(requested)):
            raise ValueError("أرقام صفحات PDF المرسلة مكررة")
        try:
            from google.genai import types

            parts = [
                types.Part.from_text(text=(
                    prompt
                    + "\n\nستصلك صور صفحات PDF مستقلة. قبل كل صورة تسمية تحمل رقم صفحة PDF. "
                      "أعد عنصرًا واحدًا في pages لكل صورة، وضع رقم التسمية نفسه في pdf_page. "
                      "لا تدمج نص صفحتين، ولا تستخدم رقم الصفحة المطبوع داخل الصورة بدل رقم PDF."
                ))
            ]
            for number, image in images:
                parts.append(types.Part.from_text(text=f"صورة صفحة PDF رقم {number}"))
                parts.append(types.Part.from_bytes(data=jpeg_bytes(image), mime_type="image/jpeg"))
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                response_json_schema=BATCH_EXTRACTION_SCHEMA,
            )
            response = self.client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
        except Exception as exc:
            raise _redacted_error(exc, self.api_key) from exc
        usage = _usage(getattr(response, "usage_metadata", None))
        raw = getattr(response, "text", None) or ""
        finish = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish = str(getattr(candidates[0], "finish_reason", "") or "")
        if finish and not any(ok in finish.upper() for ok in ("STOP", "FINISH_REASON_STOP")):
            raise GeminiFailure(f"لم يكتمل رد Gemini. finish_reason={finish}", usage=usage)
        if not raw.strip():
            raise GeminiFailure("أعاد Gemini ردًا فارغًا", usage=usage)
        try:
            batch = ExtractedBatch.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise GeminiFailure(f"رد Gemini لا يطابق مخطط دفعة الصفحات: {exc}", usage=usage) from exc
        received = [page.pdf_page for page in batch.pages]
        if set(received) != set(requested) or len(received) != len(requested):
            missing = sorted(set(requested) - set(received))
            unexpected = sorted(set(received) - set(requested))
            details = []
            if missing:
                details.append("صفحات ناقصة: " + ", ".join(map(str, missing)))
            if unexpected:
                details.append("صفحات غير مطلوبة: " + ", ".join(map(str, unexpected)))
            raise GeminiFailure("رد Gemini لا يغطي الدفعة كاملة. " + "; ".join(details), usage=usage)
        pages = {
            item.pdf_page: ExtractedPage.model_validate(
                item.model_dump(exclude={"pdf_page"})
            )
            for item in batch.pages
        }
        return GeminiBatchResult(pages=pages, raw=raw, usage=usage)
