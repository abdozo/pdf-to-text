from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image

from waraq.gemini_client import GeminiClient, GeminiFailure
from waraq.models import (
    BATCH_EXTRACTION_SCHEMA,
    DEFAULT_MANUSCRIPT_PROMPT,
    DEFAULT_PRINTED_PROMPT,
    EXTRACTION_SCHEMA,
    ExtractedPage,
)


def test_extraction_schema_uses_compact_typed_lines():
    assert set(EXTRACTION_SCHEMA["properties"]) == {
        "is_blank", "printed_page", "lines",
    }
    assert EXTRACTION_SCHEMA["properties"]["lines"]["type"] == "array"
    line_schema = EXTRACTION_SCHEMA["$defs"]["ExtractedLine"]["properties"]
    assert set(line_schema) == {"type", "align", "md"}
    assert set(line_schema["type"]["enum"]) == {
        "p", "h2", "h3", "h4", "h5", "h6", "note", "hr",
    }
    assert set(line_schema["align"]["enum"]) == {
        "right", "center", "left", "justify",
    }
    assert set(EXTRACTION_SCHEMA["$defs"]["ExtractedLine"]["required"]) == {
        "type", "align", "md",
    }


def test_printed_extraction_contract_covers_small_notes_and_visible_separators():
    description = EXTRACTION_SCHEMA["properties"]["lines"]["description"]

    assert "transcription prompt" in description
    assert "translation and summary prompts" in description
    assert '"type":"hr","align":"center","md":""' in DEFAULT_PRINTED_PROMPT
    assert '"type":"note","align":"right"' in DEFAULT_PRINTED_PROMPT
    assert "Markdown داخل md" in DEFAULT_PRINTED_PROMPT
    assert '"type":"hr","align":"center","md":""' in DEFAULT_MANUSCRIPT_PROMPT


@pytest.mark.parametrize(
    "prompt",
    [DEFAULT_PRINTED_PROMPT, DEFAULT_MANUSCRIPT_PROMPT],
)
def test_footnote_contract_forbids_grouping_a_numbered_note(prompt: str) -> None:
    assert "لا تجعل الحاشية المرقمة كلها عنصرًا واحدًا" in prompt
    assert "حتى إن كان تابعًا للحاشية نفسها ولا يبدأ برقم" in prompt
    assert (
        '"type":"note","align":"right","md":"٢٧ - أخرجه من حديث بريدة: الترمذي (٢٦٢١)،"'
        in prompt
    )
    assert (
        '"type":"note","align":"right","md":"والنسائي (١/ ٢٣١ - ٢٣٢)، وابن ماجه (١٠٧٩)."'
        in prompt
    )


@pytest.mark.parametrize(
    "prompt",
    [DEFAULT_PRINTED_PROMPT, DEFAULT_MANUSCRIPT_PROMPT],
)
def test_arabic_extraction_contract_preserves_heading_language_and_marker_fidelity(
    prompt: str,
) -> None:
    description = EXTRACTION_SCHEMA["properties"]["lines"]["description"]

    assert "h2-h6" in description
    assert "inline Markdown only" in description
    assert '"type":"h2","align":"center"' in prompt
    assert "لا تضع # أو > أو ---" in prompt
    assert "انسخ الحروف الأجنبية فقط" in prompt
    assert "ولا تستنتجها من زخرفة أو تشويش" in prompt
    assert "حافظ على التشكيل والأرقام والأقواس" in prompt
    assert "إذا ظهر «أحمد [بن](٢) عثمان»" in prompt


@pytest.mark.parametrize(
    "prompt",
    [DEFAULT_PRINTED_PROMPT, DEFAULT_MANUSCRIPT_PROMPT],
)
def test_heading_contract_prioritizes_visual_centering_and_independent_levels(
    prompt: str,
) -> None:
    assert "سجّل محاذاة كل صف في align" in prompt
    assert "مثل البسملة أو الدعاء" in prompt
    assert "قيّم كل سطر مستقلًا" in prompt
    assert "كل عنوان ظاهر في الوسط يجب أن يحمل align بقيمة center" in prompt
    assert "لا تحاول صنع التوسيط بمسافات داخل md" in prompt
    assert '"type":"h3","align":"center","md":"بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ"' in prompt
    assert '"type":"h2","align":"center","md":"رَبِّ يَسِّرْ وَأَعِنْ"' in prompt


def test_printed_prompt_starts_with_the_book_replica_goal() -> None:
    assert DEFAULT_PRINTED_PROMPT.startswith(
        "نحن نحوّل كتابًا مصورًا إلى كتاب مكتوب مطابق للمطبوع"
    )


def test_legacy_typed_lines_infer_alignment_without_weakening_the_schema() -> None:
    page = ExtractedPage(
        is_blank=False,
        printed_page="١",
        lines=[
            {"type": "h2", "md": "عنوان"},
            {"type": "p", "md": "متن"},
        ],
    )

    assert [line.align for line in page.lines] == ["center", "right"]


def test_page_with_a_visible_separator_cannot_be_marked_blank():
    with pytest.raises(ValueError, match="blank page contains extracted content"):
        ExtractedPage(
            is_blank=True,
            printed_page="",
            lines=[{"type": "hr", "md": ""}],
        )


def test_page_number_alone_cannot_be_marked_blank():
    with pytest.raises(ValueError, match="blank page contains extracted content"):
        ExtractedPage(is_blank=True, printed_page="١", lines=[])


def test_markdown_extraction_rejects_html_tags():
    with pytest.raises(ValueError, match="HTML is not allowed"):
        ExtractedPage(
            is_blank=False,
            printed_page="١",
            lines=[{"type": "p", "md": "<p>نص</p>"}],
        )


def test_markdown_extraction_rejects_line_breaks_inside_one_block():
    with pytest.raises(ValueError, match="single text block"):
        ExtractedPage(
            is_blank=False,
            printed_page="١",
            lines=[{"type": "note", "md": "السطر الأول\nالسطر الثاني"}],
        )


def test_model_catalog_only_keeps_supported_models_and_orders_by_daily_limit():
    models = [
        SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-2.5-pro", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.6-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.1-flash-lite", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-2.5-flash-tts", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.7-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-2.5-flash-lite", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3-flash-preview", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash-lite", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash-lite-latest", supported_actions=["generateContent"]),
    ]
    client = object.__new__(GeminiClient)
    client.api_key = "test-key"
    client.client = SimpleNamespace(models=SimpleNamespace(list=lambda **_kwargs: models))

    catalog = client.list_models()

    assert [item["id"] for item in catalog] == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3-flash-preview",
        "gemini-3.6-flash",
    ]
    assert catalog[0]["label"] == "Gemini 3.5 Flash Lite (500 استعلام يوميًا) · gemini-3.5-flash-lite"
    assert catalog[6]["label"] == "Gemini 2.5 Flash Lite (20 استعلام يوميًا) · gemini-2.5-flash-lite"
    assert [item["daily_limit"] for item in catalog] == [500, 500, 20, 20, 20, 20, 20, 20, 20]


def test_extract_rejects_models_outside_the_supported_conversion_list():
    client = object.__new__(GeminiClient)

    with pytest.raises(ValueError, match="غير صالح"):
        client.extract(Image.new("RGB", (100, 120), "white"), model="gemini-2.5-pro", prompt="انسخ")


def test_gemini_client_can_close_its_network_transport():
    closed: list[bool] = []
    client = object.__new__(GeminiClient)
    client.client = SimpleNamespace(close=lambda: closed.append(True))

    client.close()

    assert closed == [True]


def test_structured_page_uses_one_image_request(monkeypatch):
    raw = json.dumps({
        "is_blank": False,
        "printed_page": "١",
        "lines": [{"type": "p", "md": "نص"}],
    }, ensure_ascii=False)
    calls = []
    fake_models = SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(text=raw, candidates=[SimpleNamespace(finish_reason="STOP")], usage_metadata=None))
    client = object.__new__(GeminiClient)
    client.api_key = "test-key"
    client.client = SimpleNamespace(models=fake_models)
    page = client.extract(Image.new("RGB", (100, 120), "white"), model="gemini-3.5-flash-lite", prompt="انسخ")
    assert len(calls) == 1
    assert page.page.content_markdown == ["نص"]


def test_multiple_pages_are_sent_as_separate_labeled_images():
    raw = json.dumps({
        "pages": [
            {"pdf_page": 12, "is_blank": False, "printed_page": "١٠", "lines": [{"type": "p", "md": "الثانية"}]},
            {"pdf_page": 11, "is_blank": False, "printed_page": "٩", "lines": [{"type": "p", "md": "الأولى"}]},
        ],
    }, ensure_ascii=False)
    calls = []
    fake_models = SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(
        text=raw, candidates=[SimpleNamespace(finish_reason="STOP")], usage_metadata=None,
    ))
    client = object.__new__(GeminiClient)
    client.api_key = "test-key"
    client.client = SimpleNamespace(models=fake_models)

    result = client.extract_pages(
        [(11, Image.new("RGB", (100, 120), "white")), (12, Image.new("RGB", (100, 120), "white"))],
        model="gemini-3.5-flash-lite",
        prompt="انسخ",
    )

    assert list(result.pages) == [12, 11]
    assert result.pages[11].content_markdown == ["الأولى"]
    parts = calls[0]["contents"][0].parts
    assert len(parts) == 5
    assert parts[1].text == "صورة صفحة PDF رقم 11"
    assert parts[2].inline_data.mime_type == "image/jpeg"
    assert parts[3].text == "صورة صفحة PDF رقم 12"
    assert calls[0]["config"].response_json_schema == BATCH_EXTRACTION_SCHEMA


def test_multiple_page_response_must_cover_the_requested_pdf_pages():
    raw = json.dumps({
        "pages": [
            {"pdf_page": 11, "is_blank": False, "printed_page": "٩", "lines": [{"type": "p", "md": "الأولى"}]},
        ],
    }, ensure_ascii=False)
    client = object.__new__(GeminiClient)
    client.api_key = "test-key"
    client.client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_kwargs: SimpleNamespace(
        text=raw, candidates=[SimpleNamespace(finish_reason="STOP")], usage_metadata=None,
    )))

    with pytest.raises(GeminiFailure, match="صفحات ناقصة: 12"):
        client.extract_pages(
            [(11, Image.new("RGB", (100, 120), "white")), (12, Image.new("RGB", (100, 120), "white"))],
            model="gemini-3.5-flash-lite",
            prompt="انسخ",
        )
