from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
os.environ.setdefault("WARRAQ_DISABLE_RICH_EDITOR", "1")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWebEngineQuick import QtWebEngineQuick

from waraq.bridge import Bridge
from waraq.database import Library
from waraq.image_provider import PageImageProvider
from waraq.paths import resource_path
from waraq.secrets import MemorySecretStore


QtWebEngineQuick.initialize()


def _prepare_conversion_window(tmp_path: Path):
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path / "library")
    book = bridge.library.add_book(make_pdf(tmp_path / "range.pdf", 40))
    bridge.library.add_key("مفتاح الاختبار", "secret-ref")
    bridge.openBook(book["id"])
    bridge.go("convert")
    application.processEvents()
    bridge.runner.start = lambda _task_id: None
    return application, engine, window, bridge


def _replace_spinbox_text(application, spinbox: QObject, text: str) -> None:
    editor = spinbox.property("contentItem")
    editor.forceActiveFocus()
    QTest.keyClick(application.focusWindow(), Qt.Key_A, Qt.ControlModifier)
    keys = {str(number): getattr(Qt, f"Key_{number}") for number in range(10)}
    for character in text:
        QTest.keyClick(application.focusWindow(), keys[character])
    application.processEvents()


def _load_window(data_dir: Path):
    application = QGuiApplication.instance() or QGuiApplication([])
    application.setLayoutDirection(Qt.RightToLeft)
    library = Library(data_dir)
    bridge = Bridge(library, MemorySecretStore())
    engine = QQmlApplicationEngine()
    engine.addImageProvider("pages", PageImageProvider(library))
    engine.rootContext().setContextProperty("App", bridge)
    engine.load(QUrl.fromLocalFile(str(resource_path("qml", "Main.qml"))))
    window = engine.rootObjects()[0]
    window.setWidth(1440)
    window.setHeight(920)
    application.processEvents()
    return application, engine, window, bridge


def _color(value) -> str:
    return QColor(value).name().lower()


def test_primary_sidebar_is_on_the_right(tmp_path: Path) -> None:
    application, engine, window, bridge = _load_window(tmp_path)
    candidates = [
        item
        for item in window.findChildren(QObject)
        if item.property("color") is not None
        and _color(item.property("color")) == "#eef0f7"
        and item.property("width") > 200
        and item.property("height") > 600
    ]
    assert len(candidates) == 1
    sidebar = candidates[0]
    left = sidebar.mapToItem(window.contentItem(), QPointF(0, 0)).x()
    assert left > window.width() / 2, f"sidebar starts at x={left}"


def test_text_areas_have_explicit_light_surfaces(tmp_path: Path) -> None:
    application, engine, window, bridge = _load_window(tmp_path)
    bridge.go("settings")
    application.processEvents()
    text_areas = [
        item
        for item in window.findChildren(QObject)
        if "TextArea" in item.metaObject().className()
    ]
    assert text_areas
    for area in text_areas:
        assert _color(area.property("color")) == "#18203a"
        background = area.property("background")
        assert background is not None
        assert _color(background.property("color")) in {"#f8f9fc", "#ffffff"}


def test_rtl_editor_and_opaque_popup_are_explicit_visual_contracts() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    text_field = qml.split("component AppTextField:", 1)[1].split("component AppTextArea:", 1)[0]
    text_area = qml.split("component AppTextArea:", 1)[1].split("component AppComboBox:", 1)[0]
    combo = qml.split("component AppComboBox:", 1)[1].split("component AppSpinBox:", 1)[0]

    assert "LayoutMirroring.enabled: false" in text_field
    assert "LayoutMirroring.enabled: false" in text_area
    assert "horizontalAlignment: Text.AlignRight" in text_field
    assert "horizontalAlignment: Text.AlignRight" in text_area
    assert "contentItem:" in combo
    assert "popup:" in combo
    assert "delegate:" in combo


def test_review_has_one_side_by_side_rich_editor_and_no_matching_controls() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    review = qml.split("// Review", 1)[1].split("// Usage", 1)[0]
    rich_editor = resource_path("qml", "RichEditor.qml").read_text(encoding="utf-8")

    assert 'source: "RichEditor.qml"' in review
    assert 'objectName: "pageRichTextEditor"' in rich_editor
    assert "WebEngineView" in rich_editor
    assert 'Qt.resolvedUrl("../editor/editor.html")' in rich_editor
    assert "webChannel: editorChannel" in rich_editor
    assert "App.updatePageRichText" in rich_editor
    assert "Repeater { model: App.currentPage.flat_lines" not in review
    for removed in (
        "فوق الأصل", "أدوات المطابقة", "شفافية صورة الأصل",
        "شفافية النص المطابق", "حجم النص المطابق", "إزاحة أفقية للطبقة",
        "إزاحة رأسية للطبقة", "بنية الصفحة (متقدم)", "overlayComponent",
        "property string mode", "إضافة منطقة",
    ):
        assert removed not in review


@pytest.mark.skipif(
    os.environ.get("WARRAQ_DISABLE_RICH_EDITOR") == "1",
    reason="requires the macOS WebEngine renderer",
)
def test_long_rich_text_can_scroll_to_its_last_line(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path)
    book = bridge.library.add_book(make_pdf(tmp_path / "long-page.pdf", 1))
    content = "".join(f"<p>سطر عربي طويل رقم {index}</p>" for index in range(120))
    bridge.library.save_page_content(
        book["id"],
        1,
        content + '<p><span style="color: #bc3f54">النهاية المرئية للاختبار</span></p>',
    )
    bridge.openBook(book["id"])
    bridge.openPage(1)

    editor = None
    for _ in range(150):
        application.processEvents()
        editor = window.findChild(QObject, "pageRichTextEditor")
        if editor is not None and editor.property("editorReady"):
            break
        QTest.qWait(20)
    assert editor is not None and editor.property("editorReady")

    window.show()
    assert QTest.qWaitForWindowExposed(window)
    window.requestActivate()
    QTest.qWait(100)

    local_point = editor.mapToItem(
        window.contentItem(), QPointF(editor.property("width") / 2, editor.property("height") - 50)
    ).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, local_point)
    QTest.qWait(100)
    application.processEvents()
    assert editor.property("activeFocus"), "The wheel overlay blocked editor clicks"
    for _ in range(80):
        QTest.wheelEvent(
            window,
            local_point,
            QPoint(0, -120),
        )
        application.processEvents()
    QTest.qWait(100)
    application.processEvents()
    maximum = editor.property("editorMaximumScrollTop")
    assert maximum > 0
    assert editor.property("editorScrollTop") >= maximum - 1


@pytest.mark.skipif(
    os.environ.get("WARRAQ_DISABLE_RICH_EDITOR") == "1",
    reason="requires the macOS WebEngine renderer",
)
def test_non_breaking_spaces_cannot_push_arabic_text_outside_the_editor(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path)
    book = bridge.library.add_book(make_pdf(tmp_path / "non-breaking-spaces.pdf", 1))
    content = "<p>" + "\u00a0".join(["نص عربي طويل"] * 40) + "</p>"
    with bridge.library.transaction() as database:
        database.execute(
            "UPDATE pages SET content_html=? WHERE book_id=? AND number=1",
            (content, book["id"]),
        )
    bridge.openBook(book["id"])
    bridge.openPage(1)

    editor = None
    for _ in range(150):
        application.processEvents()
        editor = window.findChild(QObject, "pageRichTextEditor")
        if editor is not None and editor.property("editorReady"):
            break
        QTest.qWait(20)
    assert editor is not None and editor.property("editorReady")

    for _ in range(100):
        application.processEvents()
        if editor.property("title").startswith("{"):
            break
        QTest.qWait(10)

    bounds = json.loads(editor.property("title"))
    assert not bounds["hasNonBreakingSpace"]
    assert bounds["textLeft"] >= bounds["editorLeft"]
    assert bounds["textRight"] <= bounds["editorRight"]


def test_mirrored_arabic_editors_are_effectively_right_aligned(tmp_path: Path) -> None:
    application, engine, window, bridge = _load_window(tmp_path)
    bridge.go("settings")
    settings = window.findChild(QObject, "settingsScreen")
    settings.setProperty("tab", 1)
    application.processEvents()

    field = window.findChild(QObject, "newPromptName")
    field.setProperty("text", "قصير")
    field.setProperty("cursorPosition", len("قصير"))
    area = window.findChild(QObject, "newPromptText")
    text = "هذا سطر عربي طويل للاختبار\nقصير"
    area.setProperty("text", text)
    area.setProperty("cursorPosition", len(text))
    application.processEvents()

    assert field.property("cursorRectangle").x() > field.property("width") * .75
    assert area.property("cursorRectangle").x() > area.property("width") * .75


def test_review_navigation_and_dynamic_conversion_label_are_explicit() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    review = qml.split("// Review", 1)[1].split("// Usage", 1)[0]

    assert 'objectName: "reviewBookBreadcrumb"' in review
    assert 'objectName: "reviewBackToBookButton"' in review
    assert "App.go(\"book\")" in review
    assert 'objectName: "nextPageButton"' in review
    assert 'text: "‹"' in review and "App.currentPage.number + 1" in review
    assert 'objectName: "previousPageButton"' in review
    assert 'text: "›"' in review and "App.currentPage.number - 1" in review
    assert 'App.currentPage.state === "done" ? "إعادة تحويل الصفحة" : "تحويل الصفحة"' in review
    assert "prepareConversion(App.currentPage.number, App.currentPage.number, App.currentPage.state === \"done\")" in review
    assert "مثال واقعي" not in review
    assert "مقدمة المحقق" not in review


def test_review_navigation_matches_arabic_direction(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path)
    book = bridge.library.add_book(make_pdf(tmp_path / "rtl-navigation.pdf", 3))
    bridge.openBook(book["id"])
    bridge.openPage(2)
    application.processEvents()

    previous_button = window.findChild(QObject, "previousPageButton")
    next_button = window.findChild(QObject, "nextPageButton")
    previous_x = previous_button.mapToItem(window.contentItem(), QPointF(0, 0)).x()
    next_x = next_button.mapToItem(window.contentItem(), QPointF(0, 0)).x()

    assert previous_x > next_x, "زر الصفحة السابقة يجب أن يكون على اليمين"
    assert previous_button.property("text") == "›"
    assert next_button.property("text") == "‹"


def test_review_book_breadcrumb_and_back_button_open_current_book(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path)
    book = bridge.library.add_book(make_pdf(tmp_path / "review-book.pdf", 2), "كتاب الاختبار")
    bridge.openBook(book["id"])
    bridge.openPage(1)
    application.processEvents()

    breadcrumb = window.findChild(QObject, "reviewBookBreadcrumb")
    back_button = window.findChild(QObject, "reviewBackToBookButton")
    assert breadcrumb.property("text") == "كتاب الاختبار"

    bridge.updatePageRichText("<p>تعديل قبل الرجوع</p>")
    breadcrumb.clicked.emit()
    application.processEvents()
    assert bridge.screen == "book"
    assert bridge.currentBook["id"] == book["id"]
    assert bridge.library.get_page(book["id"], 1)["content_html"] == "<p>تعديل قبل الرجوع</p>"

    bridge.openPage(1)
    application.processEvents()
    back_button.clicked.emit()
    application.processEvents()
    assert bridge.screen == "book"
    assert bridge.currentBook["id"] == book["id"]


def test_all_qml_buttons_opt_into_pointer_cursor() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    app_button = qml.split("component AppButton: Button", 1)[1].split("component GhostButton", 1)[0]
    assert "Qt.PointingHandCursor" in app_button


def test_export_has_one_review_decision_and_no_technical_options() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    export = qml.split("// Export", 1)[1]

    assert 'id: exportConfirmationDialog' in qml
    assert 'objectName: "includeUnreviewedPages"' in qml
    assert 'include_unreviewed: includeUnreviewedPages.checked' in qml
    assert 'page.state === "done" && page.reviewed' in export
    assert 'page.state === "done" && !page.reviewed' in export
    for removed in (
        "تصدير الصفحات المعتمدة فقط وتجاوز الباقي",
        "تصدير تجريبي قبل اكتمال المراجعة",
        "السماح بملف غير مفحوص إذا تعذر الفحص",
        "reviewed_only:",
        "allow_unreviewed:",
        "allow_unverified:",
    ):
        assert removed not in export


def test_export_dialog_prefills_the_book_name(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf

    application, engine, window, bridge = _load_window(tmp_path / "library")
    book = bridge.library.add_book(
        make_pdf(tmp_path / "source.pdf", 1),
        name='كتاب: الجزء/الأول?',
    )
    bridge.openBook(book["id"])
    bridge.go("export")
    application.processEvents()

    chooser = window.findChild(QObject, "chooseExportDestinationButton")
    dialog = window.findChild(QObject, "exportDialog")
    chooser.clicked.emit()

    selected = QUrl(dialog.property("selectedFile")).toLocalFile()
    assert Path(selected).name == "كتاب- الجزء-الأول-.docx"
    assert dialog.property("defaultSuffix") == "docx"
    dialog.close()


def test_export_confirmation_counts_only_generated_pages_and_primary_text_is_white(
    tmp_path: Path,
) -> None:
    from tests_desktop.test_library import make_pdf, result

    application, engine, window, bridge = _load_window(tmp_path / "library")
    book = bridge.library.add_book(make_pdf(tmp_path / "export.pdf", 3))
    for number in (1, 2):
        extracted = result(f"صفحة {number}")
        bridge.library.apply_extraction(book["id"], number, extracted, extracted.model_dump_json())
    page = bridge.library.get_page(book["id"], 1)
    bridge.library.save_regions(book["id"], 1, page["regions"], reviewed=True)
    bridge.openBook(book["id"])
    bridge.go("export")
    application.processEvents()

    path = window.findChild(QObject, "exportPath")
    path.setProperty("text", str(tmp_path / "book.docx"))
    application.processEvents()
    button = window.findChild(QObject, "prepareExportButton")
    assert button.property("enabled")
    assert _color(button.property("foregroundColor")) == "#ffffff"
    assert _color(button.property("contentItem").property("color")) == "#ffffff"

    button.clicked.emit()
    application.processEvents()
    dialog = window.findChild(QObject, "exportConfirmationDialog")
    assert dialog.property("visible")
    assert dialog.property("reviewedCount") == 1
    assert dialog.property("unreviewedCount") == 1
    assert dialog.property("ungeneratedCount") == 1


def test_book_management_exposes_rename_relink_and_confirmed_delete() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    book_detail = qml.split("// Book detail", 1)[1].split("// Conversion setup", 1)[0]

    assert "id: relinkBookDialog" in qml
    assert 'title: "اختيار ملف PDF الجديد"' in qml
    assert "App.relinkBookPdf(selectedFile.toString())" in qml
    assert "id: editBookDialog" in qml
    assert "App.renameCurrentBook(editBookName.text)" in qml
    assert "id: deleteBookDialog" in qml
    assert "App.deleteCurrentBook()" in qml
    assert 'text: "تعديل الكتاب"' in book_detail
    assert 'text: "حذف الكتاب"' in book_detail


def test_gemini_settings_use_named_keys_without_project_form() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    conversion = qml.split("// Conversion setup", 1)[1].split("// Task", 1)[0]
    settings = qml.split("// Settings", 1)[1].split("// Export", 1)[0]

    assert "model: App.keys" in conversion
    assert "projectBox" not in conversion
    assert "project_id" not in conversion
    assert "App.createKey(keyName.text,keySecret.text)" in settings
    assert "App.createProject" not in settings
    assert "App.deleteKey(deleteKeyDialog.keyId)" in qml
    assert 'title: "حذف مفتاح Gemini"' in qml


def test_bridge_relinks_missing_pdf_without_losing_the_current_book(
    tmp_path: Path,
) -> None:
    from tests_desktop.test_library import make_pdf, result

    application, engine, window, bridge = _load_window(tmp_path / "library")
    original = make_pdf(tmp_path / "missing.pdf", 2)
    book = bridge.library.add_book(original, "كتاب قديم")
    extracted = result("تحويل قديم")
    bridge.library.apply_extraction(book["id"], 1, extracted, extracted.model_dump_json())
    bridge.openBook(book["id"])
    original.unlink()
    replacement = make_pdf(tmp_path / "found.pdf", 2)

    bridge.relinkBookPdf(QUrl.fromLocalFile(str(replacement)).toString())
    application.processEvents()

    assert bridge.currentBook["id"] == book["id"]
    assert Path(bridge.currentBook["source_path"]) == replacement.resolve()
    assert bridge.library.get_page(book["id"], 1)["content_html"] == "<p>تحويل قديم</p>"
    assert bridge.toast == "حُدّث مسار ملف PDF وبقيت التحويلات محفوظة"


def test_combo_popup_renders_opaque_readable_options(tmp_path: Path) -> None:
    application, engine, window, bridge = _load_window(tmp_path)
    bridge.go("settings")
    settings = window.findChild(QObject, "settingsScreen")
    settings.setProperty("tab", 1)
    application.processEvents()
    combo = next(
        item
        for item in window.findChildren(QObject)
        if "AppComboBox" in item.metaObject().className() and item.property("visible")
    )
    point = combo.mapToItem(window.contentItem(), QPointF(combo.property("width") / 2, combo.property("height") / 2))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
    application.processEvents()

    image = window.grabWindow()
    origin = combo.mapToItem(window.contentItem(), QPointF(0, 0))
    row_y = int(origin.y() + combo.property("height") + 4 + 20)
    background = image.pixelColor(int(origin.x() + combo.property("width") / 2), row_y)
    assert background.name().lower() == "#eceafe"
    dark_pixels = 0
    for y in range(row_y - 15, row_y + 15):
        for x in range(int(origin.x() + combo.property("width") * .65), int(origin.x() + combo.property("width")) - 8):
            color = image.pixelColor(x, y)
            if color.red() + color.green() + color.blue() < 360:
                dark_pixels += 1
    assert dark_pixels > 10


def test_conversion_commits_the_exact_typed_page_range_before_start(tmp_path: Path) -> None:
    application, engine, window, bridge = _prepare_conversion_window(tmp_path)
    start = window.findChild(QObject, "conversionFromPage")
    end = window.findChild(QObject, "conversionToPage")
    pages_per_request = window.findChild(QObject, "conversionPagesPerRequest")
    button = window.findChild(QObject, "startConversionButton")

    _replace_spinbox_text(application, start, "25")
    _replace_spinbox_text(application, end, "26")
    _replace_spinbox_text(application, pages_per_request, "2")
    assert button.property("enabled")
    button.clicked.emit()
    application.processEvents()

    assert bridge.currentTask, (bridge.toast, start.property("value"), end.property("value"),
                                start.property("contentItem").property("text"), end.property("contentItem").property("text"))
    assert bridge.currentTask["start_page"] == 25
    assert bridge.currentTask["end_page"] == 26
    assert bridge.currentTask["pages_per_request"] == 2
    assert bridge.library.page_numbers_for_task(bridge.currentTask) == [25, 26]


def test_page_numbers_use_latin_digits_in_controls_and_review(tmp_path: Path) -> None:
    application, engine, window, bridge = _prepare_conversion_window(tmp_path)
    start = window.findChild(QObject, "conversionFromPage")
    end = window.findChild(QObject, "conversionToPage")
    _replace_spinbox_text(application, start, "25")
    _replace_spinbox_text(application, end, "26")

    assert start.property("contentItem").property("text") == "25"
    bridge.openPage(25)
    application.processEvents()
    indicator = window.findChild(QObject, "reviewPageIndicator")
    assert indicator.property("text") == "صفحة 25 من 40"


def test_rich_editor_is_tiptap_with_modern_formatting_and_local_assets() -> None:
    editor = resource_path("editor", "editor.html").read_text(encoding="utf-8")
    source = resource_path("editor", "editor.js").read_text(encoding="utf-8")
    bundle = resource_path("editor", "editor.bundle.js").read_text(encoding="utf-8")

    assert "new Editor({" in source
    assert "editor.bundle.js" in editor
    assert "qrc:///qtwebchannel/qwebchannel.js" in editor
    for feature in ("bold", "italic", "underline", "strike", "blockquote", "orderedList", "bulletList", "subscript", "superscript", "setColor", "setBackgroundColor", "setTextAlign"):
        assert feature in source
    assert "https://" not in editor
    assert resource_path("editor", "editor.bundle.js").is_file()
    assert resource_path("editor", "THIRD-PARTY-LICENSES.txt").is_file()
    assert "waraqGetHtml" in bundle and "hasNonBreakingSpace" in bundle


def test_repository_has_only_desktop_entrypoints() -> None:
    root = Path(__file__).resolve().parents[1]

    assert not (root / "kitab").exists()
    assert not (root / "run.py").exists()
    assert not (root / "launcher.py").exists()
    assert not (root / "requirements.txt").exists()
    assert not (root / "tests").exists()


def test_rich_editor_toolbar_is_arabic_rtl_and_commits_before_approval() -> None:
    editor = resource_path("editor", "editor.html").read_text(encoding="utf-8")
    source = resource_path("editor", "editor.js").read_text(encoding="utf-8")
    rich_editor = resource_path("qml", "RichEditor.qml").read_text(encoding="utf-8")
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    review = qml.split("// Review", 1)[1].split("// Usage", 1)[0]

    assert 'dir="rtl"' in editor
    assert 'role="toolbar"' in editor
    for arabic_label in ("نص عادي", "عنوان رئيسي", "صغير", "كبير جدًا", "آريال", "بلكس عربي"):
        assert arabic_label in editor
    assert "window.waraqGetHtml" in source
    assert "window.waraqScrollBy" in source
    assert "function commit(approve)" in rich_editor
    assert "onWheel: function(event)" in rich_editor
    assert "pageRichTextEditor.scrollByWheel" in rich_editor
    assert "App.commitPageRichText" in rich_editor
    assert "reviewScreen.commitPage(false)" in review
    assert "reviewScreen.commitPage(true)" in review


def test_task_screen_has_a_centered_animated_state_and_review_return() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    task = qml.split("// Task", 1)[1].split("// Review", 1)[0]

    assert 'objectName: "conversionBusyIndicator"' in task
    assert "running: taskScreen.conversionActive" in task
    assert "anchors.horizontalCenter: parent.horizontalCenter" in task
    assert 'text: "مراجعة الصفحة المحوّلة"' in task
    assert "App.openTaskPage()" in task


def test_task_batch_summary_wraps_without_outdated_per_request_copy() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    task = qml.split("// Task", 1)[1].split("// Review", 1)[0]

    assert 'objectName: "currentBatchCard"' in task
    assert 'objectName: "currentBatchPages"' in task
    assert "wrapMode: Text.WrapAnywhere" in task
    assert "font.pixelSize: 15" in task
    assert "font.weight: Font.Normal" in task
    assert "صفحة في كل استعلام" not in task


def test_rich_editor_keeps_toolbar_visible_and_reserves_bottom_reading_space() -> None:
    editor = resource_path("editor", "editor.html").read_text(encoding="utf-8")

    assert "flex: 0 0 auto" in editor
    assert "padding: 18px 20px 100px" in editor
    assert "overflow-y: auto" in editor


def test_rich_editor_normalizes_non_breaking_spaces_and_contains_long_text() -> None:
    editor = resource_path("editor", "editor.html").read_text(encoding="utf-8")
    source = resource_path("editor", "editor.js").read_text(encoding="utf-8")

    assert "replace(/\\u00a0/g, ' ')" in source
    assert "normalizeSpaces(editor.getHTML())" in source
    assert "overflow-wrap: anywhere" in editor
    assert "overflow-x: hidden" in editor


def test_task_activity_is_visibly_running_in_the_center(tmp_path: Path) -> None:
    application, engine, window, bridge = _prepare_conversion_window(tmp_path)
    button = window.findChild(QObject, "startConversionButton")
    button.clicked.emit()
    application.processEvents()

    indicator = window.findChild(QObject, "conversionBusyIndicator")
    assert indicator is not None
    assert indicator.property("visible")
    assert indicator.property("running")
    point = indicator.mapToItem(window.contentItem(), QPointF(0, 0))
    indicator_center = point.x() + indicator.property("width") / 2
    assert abs(indicator_center - window.width() / 2) < 180

    pages = list(range(1, 81))
    bridge._task = {
        **bridge.currentTask,
        "state": "running",
        "control_action": "",
        "start_page": 1,
        "end_page": 80,
        "current_page": 1,
        "active_pages": pages,
        "total": 80,
        "processed": 0,
        "completed": 0,
        "remaining": 80,
        "failed": 0,
        "error": "",
    }
    bridge._tasks = [{**bridge._task, "display_name": "دفعة طويلة"}]
    bridge._screen = "task"
    bridge.stateChanged.emit()
    application.processEvents()

    card = window.findChild(QObject, "currentBatchCard")
    value = window.findChild(QObject, "currentBatchPages")
    assert card is not None and value is not None
    card_origin = card.mapToItem(window.contentItem(), QPointF(0, 0))
    value_origin = value.mapToItem(window.contentItem(), QPointF(0, 0))
    assert value.property("height") > 20, "the long page list did not wrap"
    assert value_origin.x() >= card_origin.x()
    assert value_origin.x() + value.property("width") <= card_origin.x() + card.property("width")
    assert value_origin.y() + value.property("height") <= card_origin.y() + card.property("height")


def test_conversion_task_can_be_reopened_from_sidebar_after_navigating_away(
    tmp_path: Path,
) -> None:
    application, engine, window, bridge = _prepare_conversion_window(tmp_path)
    button = window.findChild(QObject, "startConversionButton")
    button.clicked.emit()
    application.processEvents()
    task_id = bridge.currentTask["id"]

    bridge.go("usage")
    application.processEvents()

    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    sidebar = qml.split("Repeater {", 1)[1].split("Item { Layout.fillHeight", 1)[0]
    assert '{screen:"task", label:"عمليات التحويل", mark:"ت"}' in sidebar
    bridge.go("task")
    application.processEvents()

    assert bridge.screen == "task"
    assert bridge.currentTask["id"] == task_id


def test_toast_is_anchored_to_the_physical_bottom_right() -> None:
    qml = resource_path("qml", "Main.qml").read_text(encoding="utf-8")
    toast = qml.rsplit("Rectangle {", 1)[1]

    assert "LayoutMirroring.enabled: false" in toast
    assert "anchors.right: parent.right" in toast
    assert "anchors.horizontalCenter" not in toast


def test_toast_runtime_position_is_bottom_right(tmp_path: Path) -> None:
    application, engine, window, bridge = _load_window(tmp_path)
    bridge._notify("رسالة اختبار")
    application.processEvents()

    toast = window.findChild(QObject, "toastNotification")
    point = toast.mapToItem(window.contentItem(), QPointF(0, 0))
    assert point.x() > window.width() / 2
    assert point.y() > window.height() / 2


def test_page_conversion_button_reflects_whether_page_was_converted(tmp_path: Path) -> None:
    from tests_desktop.test_library import make_pdf, result

    application, engine, window, bridge = _load_window(tmp_path / "library")
    book = bridge.library.add_book(make_pdf(tmp_path / "states.pdf", 1))
    bridge.openBook(book["id"])
    bridge.openPage(1)
    application.processEvents()
    button = window.findChild(QObject, "pageConversionButton")
    assert button.property("text") == "تحويل الصفحة"

    extracted = result("نص محول")
    bridge.library.apply_extraction(book["id"], 1, extracted, extracted.model_dump_json())
    bridge.openPage(1)
    application.processEvents()
    assert button.property("text") == "إعادة تحويل الصفحة"


def test_conversion_model_picker_shows_every_loaded_model(tmp_path: Path) -> None:
    application, engine, window, bridge = _prepare_conversion_window(tmp_path)
    bridge._apply_async({"kind": "models", "value": [
        {"id": "gemini-test-flash", "label": "Gemini Test Flash · gemini-test-flash"},
        {"id": "gemini-test-pro", "label": "Gemini Test Pro · gemini-test-pro"},
    ]})
    application.processEvents()

    picker = window.findChild(QObject, "conversionModelBox")
    assert picker.property("count") == 2
    assert not picker.property("editable")
