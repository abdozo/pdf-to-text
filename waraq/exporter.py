from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from .database import Library, utc_now
from .richtext import rich_html_blocks


EXPORT_LOCK = threading.Lock()
ALLOWED_TAG = re.compile(r"(<sup>[^<>]*</sup>)")


def _office_path() -> str | None:
    configured = os.environ.get("WARRAQ_SOFFICE")
    program_files = os.environ.get("PROGRAMFILES")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = (
        configured,
        shutil.which("soffice"),
        str(Path(program_files) / "LibreOffice" / "program" / "soffice.exe") if program_files else None,
        str(Path(program_files_x86) / "LibreOffice" / "program" / "soffice.exe") if program_files_x86 else None,
        str(Path(local_app_data) / "Programs" / "LibreOffice" / "program" / "soffice.exe") if local_app_data else None,
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        str(Path(__file__).resolve().parent / "runtime" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"),
    )
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def _set_cell_margins(cell: Any, top: int = 60, start: int = 80, bottom: int = 60, end: int = 80) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value)); node.set(qn("w:type"), "dxa")


def _set_paragraph_rtl(paragraph: Any) -> None:
    """Write portable RTL paragraph properties in the OOXML schema order."""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    ppr = paragraph._p.get_or_add_pPr()
    bidi = ppr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
    else:
        ppr.remove(bidi)
    bidi.set(qn("w:val"), "1")
    ppr.insert_element_before(
        bidi,
        "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
        "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap",
        "w:jc", "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
        "w:outlineLvl", "w:divId", "w:cnfStyle",
    )


def _set_run_rtl(run: Any) -> None:
    rpr = run._r.get_or_add_rPr()
    for tag in ("rtl", "cs"):
        element = rpr.find(qn(f"w:{tag}"))
        if element is None:
            element = OxmlElement(f"w:{tag}")
            rpr.append(element)
        element.set(qn("w:val"), "1")
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is not None:
        fonts.set(qn("w:cs"), run.font.name or "Arial")
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    lang.set(qn("w:bidi"), "ar-SA")


def _rtl(paragraph: Any, text: str, size: float, *, handwritten: bool = False, bold: bool = False) -> None:
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(1.5)
    paragraph.paragraph_format.line_spacing = 1.15
    _set_paragraph_rtl(paragraph)
    for part in ALLOWED_TAG.split(text):
        superscript = part.startswith("<sup>") and part.endswith("</sup>")
        value = part[5:-6] if superscript else re.sub(r"<[^>]+>", "", part)
        run = paragraph.add_run(value)
        run.font.name = "Arial"
        run.font.size = Pt(size)
        run.font.superscript = superscript
        run.font.italic = handwritten
        run.font.bold = bold
        _set_run_rtl(run)


def _rtl_rich(paragraph: Any, block: dict[str, Any], size: float, scale: float) -> None:
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(1.5)
    paragraph.paragraph_format.line_spacing = 1.15
    if block.get("quote"):
        paragraph.paragraph_format.left_indent = Pt(18)
        paragraph.paragraph_format.right_indent = Pt(18)
    heading_level = block.get("heading_level")
    if heading_level:
        paragraph.style = f"Heading {heading_level}"
    list_kind = next((run.get("list") for run in block.get("runs", []) if run.get("list")), None)
    if list_kind:
        paragraph.style = "List Number" if list_kind == "ordered" else "List Bullet"
    _set_paragraph_rtl(paragraph)
    for item in block.get("runs", []):
        run = paragraph.add_run(item.get("text", ""))
        run.font.name = item.get("font_family") or "Arial"
        run.font.size = Pt(float(item.get("font_size") or size) * scale)
        run.font.bold = bool(item.get("bold"))
        run.font.italic = bool(item.get("italic"))
        run.font.underline = bool(item.get("underline"))
        run.font.superscript = bool(item.get("superscript"))
        run.font.subscript = bool(item.get("subscript"))
        _set_run_rtl(run)


def _page_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for region in sorted(page["regions"], key=lambda item: item["reading_order"]):
        for line in sorted(region["lines"], key=lambda item: item["reading_order"]):
            lines.append({**line, "kind": region["kind"], "source": region["source"], "column": region["column_index"]})
    return lines


def build_docx(pages: list[dict[str, Any]], destination: Path, scale: float = 1.0) -> None:
    doc = Document()
    doc.core_properties.title = "نص الكتاب المطابق لصفحات الأصل"
    doc.core_properties.description = "نص عربي قابل للتحرير. يحتاج إلى مراجعة بشرية مقابل الأصل."
    for index, page in enumerate(pages):
        section = doc.sections[0] if index == 0 else doc.add_section(WD_SECTION_START.NEW_PAGE)
        section.page_width = Pt(page["width"])
        section.page_height = Pt(page["height"])
        margin = min(30, page["width"] * 0.055, page["height"] * 0.055)
        section.top_margin = section.bottom_margin = Pt(margin)
        section.left_margin = section.right_margin = Pt(margin)
        section.header_distance = section.footer_distance = Pt(0)
        section.footer.is_linked_to_previous = False
        if page.get("printed_page"):
            _rtl(section.footer.paragraphs[0], page["printed_page"], 8.5)

        lines = _page_lines(page)
        rich_blocks = rich_html_blocks(page.get("content_html", "")) if page.get("content_html") else []
        page_height = page["height"] - 2 * margin - 18
        page_width = page["width"] - 2 * margin
        estimated_texts = (
            ["".join(run["text"] for run in block["runs"]) for block in rich_blocks]
            if rich_blocks else [line["text"] for line in lines]
        )
        estimated = sum(max(1, math.ceil(len(text) * 5.7 / max(page_width, 1))) for text in estimated_texts)
        size = max(6.5, min(13.5, page_height / max(estimated * 1.35, 1))) * scale
        body = [line for line in lines if line["kind"] not in {"footnote", "page_number", "margin_note"}]
        notes = [line for line in lines if line["kind"] in {"footnote", "margin_note"}]
        columns = max((line["column"] for line in body), default=0) + 1
        if rich_blocks:
            for block in rich_blocks:
                _rtl_rich(doc.add_paragraph(), block, size / scale, scale)
        elif not lines:
            _rtl(doc.add_paragraph(), "", 1)
        elif columns <= 1:
            for line in body:
                _rtl(doc.add_paragraph(), line["text"], size, handwritten=line["source"] == "handwritten", bold=line["kind"] == "heading")
        else:
            table = doc.add_table(rows=1, cols=columns)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            # Right-to-left visual order: logical column zero sits on the right.
            for logical in range(columns):
                cell = table.cell(0, columns - logical - 1)
                cell.width = Pt(page_width / columns)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                _set_cell_margins(cell)
                current = [line for line in body if line["column"] == logical]
                if not current:
                    current = [{"text": "", "source": "printed", "kind": "body"}]
                for line_index, line in enumerate(current):
                    paragraph = cell.paragraphs[0] if line_index == 0 else cell.add_paragraph()
                    _rtl(paragraph, line["text"], size, handwritten=line["source"] == "handwritten", bold=line["kind"] == "heading")
            tbl_pr = table._tbl.tblPr
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                element = OxmlElement(f"w:{edge}"); element.set(qn("w:val"), "nil"); borders.append(element)
            tbl_pr.append(borders)
        if notes:
            first = True
            for line in notes:
                paragraph = doc.add_paragraph()
                if first:
                    paragraph.paragraph_format.space_before = Pt(7)
                    border = OxmlElement("w:pBdr"); top = OxmlElement("w:top")
                    for key, value in {"val": "single", "sz": "4", "space": "4", "color": "777777"}.items():
                        top.set(qn(f"w:{key}"), value)
                    border.append(top); paragraph._p.get_or_add_pPr().append(border); first = False
                _rtl(paragraph, line["text"], size * 0.82, handwritten=line["source"] == "handwritten")
    doc.save(destination)


def _pdf_page_count(path: Path) -> int:
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(path) as pdf:
        return len(pdf)


def export_word(
    library: Library,
    book_id: str,
    start_page: int,
    end_page: int,
    destination: Path,
    *,
    include_unreviewed: bool = False,
) -> dict[str, Any]:
    book = library.get_book(book_id)
    if start_page < 1 or end_page > book["page_count"] or start_page > end_page:
        raise ValueError("نطاق التصدير غير صالح")
    requested_pages = [library.get_page(book_id, number) for number in range(start_page, end_page + 1)]
    generated_pages = [page for page in requested_pages if page["state"] == "done"]
    pages = (
        generated_pages
        if include_unreviewed
        else [page for page in generated_pages if page["reviewed"]]
    )
    skipped_pages = [page["number"] for page in requested_pages if page not in pages]
    skipped_unconverted = [page["number"] for page in requested_pages if page["state"] != "done"]
    skipped_unreviewed = [
        page["number"]
        for page in generated_pages
        if not page["reviewed"] and not include_unreviewed
    ]
    if not pages:
        if generated_pages:
            raise ValueError("لا توجد صفحات معتمدة في النطاق المحدد. اختر تضمين الصفحات المولّدة غير المعتمدة للتصدير.")
        raise ValueError("لا توجد صفحات مولّدة في النطاق المحدد")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    office = _office_path()
    actual_pages = None
    verified = False
    used_scale = 1.0
    with EXPORT_LOCK:
        for scale in (1.0, 0.92, 0.84, 0.76):
            build_docx(pages, destination, scale)
            used_scale = scale
            if not office:
                break
            with tempfile.TemporaryDirectory(prefix="waraq-word-") as temporary:
                temp = Path(temporary)
                profile = (temp / "profile").as_uri()
                process = subprocess.run([office, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", str(temp), str(destination)], capture_output=True, timeout=300)
                rendered = temp / f"{destination.stem}.pdf"
                if process.returncode != 0 or not rendered.exists():
                    break
                actual_pages = _pdf_page_count(rendered)
                if actual_pages == len(pages):
                    verified = True
                    shutil.copy2(rendered, destination.with_suffix(".verification.pdf"))
                    break
    exported_unreviewed = sum(not bool(page["reviewed"]) for page in pages)
    exported_reviewed = len(pages) - exported_unreviewed
    message_parts = [f"أُنشئ الملف من {len(pages)} صفحة مولّدة"]
    if exported_unreviewed:
        message_parts.append(f"منها {exported_unreviewed} غير معتمدة")
    if skipped_unreviewed:
        message_parts.append(f"تُركت {len(skipped_unreviewed)} صفحة مولّدة غير معتمدة")
    if skipped_unconverted:
        message_parts.append(f"لم تُضف {len(skipped_unconverted)} صفحة غير مولّدة")
    message = ". ".join(message_parts) + "."
    if not verified:
        message += " لم يكتمل فحص مطابقة الصفحات؛ راجع الملف في Word قبل اعتماده."
    report = {
        "book": book["name"], "start_page": start_page, "end_page": end_page,
        "expected_pages": len(pages), "actual_pages": actual_pages, "verified": verified,
        "reviewed_pages": exported_reviewed,
        "unreviewed_pages": exported_unreviewed,
        "generated_pages": len(generated_pages),
        "source_pages": [page["number"] for page in pages],
        "skipped_pages": skipped_pages,
        "skipped_unreviewed_pages": skipped_unreviewed,
        "skipped_unconverted_pages": skipped_unconverted,
        "complete_book": start_page == 1 and end_page == book["page_count"] and not skipped_pages,
        "font_scale": used_scale,
        "message": message,
    }
    report_path = destination.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with library.transaction() as db:
        db.execute("INSERT INTO exports VALUES (?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, book_id, start_page, end_page, str(destination), json.dumps(report, ensure_ascii=False), utc_now()))
    return report
