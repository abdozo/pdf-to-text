from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image

from waraq.gemini_client import GeminiClient, GeminiFailure
from waraq.models import BATCH_EXTRACTION_SCHEMA, EXTRACTION_SCHEMA


def test_extraction_schema_is_limited_to_page_metadata_and_visual_html_lines():
    assert set(EXTRACTION_SCHEMA["properties"]) == {
        "is_blank", "printed_page", "content_html",
    }
    assert EXTRACTION_SCHEMA["properties"]["content_html"]["type"] == "array"


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


def test_structured_page_uses_one_image_request(monkeypatch):
    raw = json.dumps({
        "is_blank": False,
        "printed_page": "١",
        "content_html": ["<p>نص</p>"],
    }, ensure_ascii=False)
    calls = []
    fake_models = SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(text=raw, candidates=[SimpleNamespace(finish_reason="STOP")], usage_metadata=None))
    client = object.__new__(GeminiClient)
    client.api_key = "test-key"
    client.client = SimpleNamespace(models=fake_models)
    page = client.extract(Image.new("RGB", (100, 120), "white"), model="gemini-3.5-flash-lite", prompt="انسخ")
    assert len(calls) == 1
    assert page.page.content_html == ["<p>نص</p>"]


def test_multiple_pages_are_sent_as_separate_labeled_images():
    raw = json.dumps({
        "pages": [
            {"pdf_page": 12, "is_blank": False, "printed_page": "١٠", "content_html": ["<p>الثانية</p>"]},
            {"pdf_page": 11, "is_blank": False, "printed_page": "٩", "content_html": ["<p>الأولى</p>"]},
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
    assert result.pages[11].content_html == ["<p>الأولى</p>"]
    parts = calls[0]["contents"][0].parts
    assert len(parts) == 5
    assert parts[1].text == "صورة صفحة PDF رقم 11"
    assert parts[2].inline_data.mime_type == "image/jpeg"
    assert parts[3].text == "صورة صفحة PDF رقم 12"
    assert calls[0]["config"].response_json_schema == BATCH_EXTRACTION_SCHEMA


def test_multiple_page_response_must_cover_the_requested_pdf_pages():
    raw = json.dumps({
        "pages": [
            {"pdf_page": 11, "is_blank": False, "printed_page": "٩", "content_html": ["<p>الأولى</p>"]},
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
