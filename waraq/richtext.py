from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any


_HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
_BLOCK_TAGS = {"p", "div", "blockquote", "li"} | _HEADING_TAGS
_ALLOWED_TAGS = _BLOCK_TAGS | {"br", "strong", "b", "em", "i", "u", "s", "sup", "sub", "span", "ol", "ul"}
_ALLOWED_STYLES = {
    "background-color", "color", "direction", "font-family", "font-size",
    "font-style", "font-weight", "margin-left", "margin-right",
    "text-align", "text-decoration",
}
_ALLOWED_CLASS = re.compile(
    r"^(?:ql-(?:font-(?:naskh|arial|plex)|size-(?:small|large|huge)|"
    r"align-(?:center|right|justify)|direction-rtl|indent-[1-8]))$"
)


def _safe_style(value: str) -> str:
    declarations: list[str] = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        key, raw = declaration.split(":", 1)
        key = key.strip().lower()
        raw = raw.strip()
        if key not in _ALLOWED_STYLES or not raw:
            continue
        if re.search(r"url\s*\(|expression\s*\(|javascript:", raw, re.I):
            continue
        declarations.append(f"{key}: {raw}")
    return "; ".join(declarations)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"head", "script", "style"}:
            self._skip += 1
            return
        if self._skip or tag not in _ALLOWED_TAGS:
            return
        rendered: list[str] = []
        if tag in _BLOCK_TAGS | {"span"}:
            style = next((value for key, value in attrs if key.lower() == "style" and value), "")
            style = _safe_style(style)
            if style:
                rendered.append(f'style="{html.escape(style, quote=True)}"')
            classes = next((value for key, value in attrs if key.lower() == "class" and value), "")
            safe_classes = [name for name in classes.split() if _ALLOWED_CLASS.fullmatch(name)]
            if safe_classes:
                rendered.append(f'class="{html.escape(" ".join(safe_classes), quote=True)}"')
            if tag == "li":
                list_kind = next((value for key, value in attrs if key.lower() == "data-list"), None)
                if list_kind in {"ordered", "bullet", "checked", "unchecked"}:
                    rendered.append(f'data-list="{list_kind}"')
        rendered_attrs = (" " + " ".join(rendered)) if rendered else ""
        self.output.append(f"<{tag}{rendered_attrs}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._skip and tag.lower() == "br":
            self.output.append("<br>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"head", "script", "style"}:
            self._skip = max(0, self._skip - 1)
            return
        if not self._skip and tag in _ALLOWED_TAGS and tag != "br":
            self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.output.append(html.escape(data.replace("\xa0", " ")))


def sanitize_rich_html(value: str) -> str:
    value = str(value or "")
    if "<" not in value:
        return "".join(f"<p>{html.escape(line)}</p>" for line in value.splitlines())
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.output).strip()


def extracted_lines_to_html(lines: list[str]) -> str:
    """Sanitize visual-line HTML and join adjacent list items into one list."""
    output: list[str] = []
    list_items: list[str] = []
    list_kind = ""

    def flush_list() -> None:
        nonlocal list_items, list_kind
        if list_items:
            container = "ol" if list_kind == "ordered" else "ul"
            output.append(f"<{container}>{''.join(list_items)}</{container}>")
        list_items = []
        list_kind = ""

    for line in lines:
        safe = sanitize_rich_html(line)
        if not safe:
            continue
        item_match = re.fullmatch(r'<li(?:\s[^>]*)?data-list="(ordered|bullet)"(?:\s[^>]*)?>(.*)</li>', safe, re.S)
        if item_match:
            current_kind = item_match.group(1)
            if list_items and current_kind != list_kind:
                flush_list()
            list_kind = current_kind
            list_items.append(safe)
            continue
        flush_list()
        if not re.match(r"^<(?:p|div|blockquote|h[1-6]|ol|ul)(?:\s|>)", safe):
            safe = f"<p>{safe}</p>"
        output.append(safe)
    flush_list()
    return "".join(output)


def regions_to_html(regions: list[dict[str, Any]]) -> str:
    paragraphs: list[str] = []
    for region in sorted(regions, key=lambda item: item.get("reading_order", 0)):
        for line in sorted(region.get("lines", []), key=lambda item: item.get("reading_order", 0)):
            value = html.escape(str(line.get("text", "")))
            marks = set(line.get("marks", []))
            if "superscript" in marks:
                value = f"<sup>{value}</sup>"
            if "highlight" in marks:
                value = f'<span style="background-color: #fff1a8">{value}</span>'
            if "bold" in marks or region.get("kind") == "heading":
                value = f"<strong>{value}</strong>"
            if region.get("source") == "handwritten":
                value = f"<em>{value}</em>"
            paragraphs.append(f"<p>{value}</p>")
    return "".join(paragraphs)


class _PlainBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current: list[str] = []

    def _flush(self) -> None:
        value = "".join(self.current).replace("\xa0", " ").strip()
        if value or self.current:
            self.blocks.append(value)
        self.current = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _BLOCK_TAGS and self.current:
            self._flush()
        elif tag.lower() == "br":
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        self.current.append(data)


def rich_html_lines(value: str) -> list[str]:
    parser = _PlainBlocks()
    parser.feed(sanitize_rich_html(value))
    parser.close()
    if parser.current:
        parser._flush()
    return parser.blocks


class _RichBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.states: list[dict[str, Any]] = [{}]

    def _flush(self) -> None:
        if self.runs:
            self.blocks.append({
                "quote": bool(self.states[-1].get("quote")),
                "heading_level": self.states[-1].get("heading_level"),
                "runs": self.runs,
            })
        self.runs = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self._flush()
            return
        if tag in _BLOCK_TAGS and self.runs:
            self._flush()
        state = dict(self.states[-1])
        if tag in {"strong", "b"} | _HEADING_TAGS:
            state["bold"] = True
        if tag in _HEADING_TAGS:
            state["heading_level"] = int(tag[1:])
        if tag in {"em", "i"}:
            state["italic"] = True
        if tag == "u":
            state["underline"] = True
        if tag == "sup":
            state["superscript"] = True
        if tag == "sub":
            state["subscript"] = True
        if tag == "blockquote":
            state["quote"] = True
        style = next((value for key, value in attrs if key.lower() == "style" and value), "")
        for declaration in _safe_style(style).split(";"):
            if ":" not in declaration:
                continue
            key, raw = (part.strip() for part in declaration.split(":", 1))
            if key == "font-family":
                state["font_family"] = raw.strip("'\"").split(",", 1)[0]
            elif key == "font-size":
                match = re.search(r"([0-9.]+)\s*(pt|px)?", raw)
                if match:
                    size = float(match.group(1))
                    state["font_size"] = size * .75 if match.group(2) == "px" else size
            elif key == "font-weight" and ("bold" in raw or raw.isdigit() and int(raw) >= 600):
                state["bold"] = True
            elif key == "font-style" and "italic" in raw:
                state["italic"] = True
            elif key == "text-decoration" and "underline" in raw:
                state["underline"] = True
        classes = next((value for key, value in attrs if key.lower() == "class" and value), "")
        for name in classes.split():
            if name.startswith("ql-font-"):
                state["font_family"] = {
                    "ql-font-naskh": "Noto Naskh Arabic",
                    "ql-font-arial": "Arial",
                    "ql-font-plex": "IBM Plex Sans Arabic",
                }.get(name, state.get("font_family"))
            elif name.startswith("ql-size-"):
                state["font_size"] = {"ql-size-small": 10, "ql-size-large": 18, "ql-size-huge": 24}.get(name)
            elif name.startswith("ql-align-"):
                state["align"] = name.removeprefix("ql-align-")
        if tag == "li":
            state["list"] = next((value for key, value in attrs if key.lower() == "data-list"), "bullet")
        self.states.append(state)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag != "br" and len(self.states) > 1:
            self.states.pop()

    def handle_data(self, data: str) -> None:
        if not data or (not self.runs and not data.strip()):
            return
        self.runs.append({"text": data.replace("\xa0", " "), **self.states[-1]})


def rich_html_blocks(value: str) -> list[dict[str, Any]]:
    parser = _RichBlocks()
    parser.feed(sanitize_rich_html(value))
    parser.close()
    parser._flush()
    return parser.blocks
