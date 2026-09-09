from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt

from .models import normalize_visual_line_text
from .richtext import sanitize_rich_html


_MARKDOWN = MarkdownIt(
    "commonmark",
    {"html": False, "linkify": False, "typographer": False},
).enable("strikethrough")


def markdown_lines_to_document(lines: list[str]) -> str:
    """Keep each extracted source line as a separate Markdown block."""
    return "\n\n".join(
        line for value in lines if (line := normalize_visual_line_text(str(value)))
    )


def normalize_markdown_document(value: str) -> str:
    return str(value or "").replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n").strip()


def markdown_to_html(value: str) -> str:
    """Render the canonical Markdown into safe compatibility/export HTML."""
    rendered = _MARKDOWN.render(normalize_markdown_document(value)).strip()
    rendered = re.sub(r"<(h[2-6])>", r'<\1 class="ql-align-center">', rendered)
    rendered = rendered.replace("<blockquote>", '<blockquote class="ql-size-small">')
    rendered = re.sub(
        r"<ol>(.*?)</ol>",
        lambda match: "<ol>" + match.group(1).replace(
            "<li>", '<li data-list="ordered">'
        ) + "</ol>",
        rendered,
        flags=re.S,
    )
    rendered = re.sub(
        r"<ul>(.*?)</ul>",
        lambda match: "<ul>" + match.group(1).replace(
            "<li>", '<li data-list="bullet">'
        ) + "</ul>",
        rendered,
        flags=re.S,
    )
    rendered = re.sub(r">\s+<", "><", rendered)
    return sanitize_rich_html(rendered)


def markdown_lines_to_html(lines: list[str]) -> str:
    return markdown_to_html(markdown_lines_to_document(lines))


def _apply_block_alignment(rendered: str, alignment: str) -> str:
    """Attach one extracted row's alignment to its rendered block."""
    class_name = f"ql-align-{alignment}"
    target = r"<(p|h[2-6]|li)([^>]*)>"

    def add_class(match: re.Match[str]) -> str:
        tag, attrs = match.groups()
        class_match = re.search(r'\sclass="([^"]*)"', attrs)
        if class_match:
            classes = [
                name
                for name in class_match.group(1).split()
                if not name.startswith("ql-align-")
            ]
            classes.append(class_name)
            attrs = (
                attrs[:class_match.start()]
                + f' class="{" ".join(classes)}"'
                + attrs[class_match.end():]
            )
        else:
            attrs += f' class="{class_name}"'
        return f"<{tag}{attrs}>"

    return re.sub(target, add_class, rendered, count=1)


def typed_lines_to_html(lines: list[Any]) -> str:
    """Render typed extraction rows while preserving their visual alignment."""
    output: list[str] = []
    pending_list_tag = ""
    pending_list_items: list[str] = []

    def flush_list() -> None:
        nonlocal pending_list_tag, pending_list_items
        if pending_list_items:
            output.append(
                f"<{pending_list_tag}>{''.join(pending_list_items)}</{pending_list_tag}>"
            )
        pending_list_tag = ""
        pending_list_items = []

    for line in lines:
        rendered = markdown_to_html(line.to_markdown())
        if line.type != "hr" and (
            line.align != "right" or line.type.startswith("h")
        ):
            rendered = _apply_block_alignment(rendered, line.align)
        list_match = re.fullmatch(r"<(ol|ul)>(.*)</\1>", rendered, re.S)
        if list_match:
            list_tag, items = list_match.groups()
            list_kind = "ordered" if list_tag == "ol" else "bullet"
            items = re.sub(
                r'<li(?![^>]*\bdata-list=)([^>]*)>',
                rf'<li\1 data-list="{list_kind}">',
                items,
            )
            if pending_list_items and pending_list_tag != list_tag:
                flush_list()
            pending_list_tag = list_tag
            pending_list_items.append(items)
            continue
        flush_list()
        output.append(rendered)

    flush_list()
    return sanitize_rich_html("".join(output))
