from __future__ import annotations

import re
from html import escape as html_escape
from io import BytesIO
import textwrap

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

from .write_file import _ensure_extension, _write_content


# Matches markdown bold **text** / __text__ and italic *text* / _text_.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_UNDERLINE_RE = re.compile(r"__(.+?)__")


def _md_to_reportlab_xml(text: str) -> str:
    """Convert markdown inline formatting to reportlab-compatible XML.

    Call AFTER ``html_escape()`` so escaped ``&lt;`` / ``&amp;`` stay
    safe, but ``**`` / ``__`` / ``*`` markers are still available for
    conversion.  ``html_escape`` does NOT touch ``*`` or ``_``.
    """
    # Bold **text** → <b>text</b>
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    # Underline __text__ → <u>text</u> (reportlab Paragraph supports <u>)
    text = _UNDERLINE_RE.sub(r"<u>\1</u>", text)
    return text


def _normalise_pdf_lines(content: str, title: str = "") -> list[str]:
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("### "):
            line = line[4:]
        elif line.startswith("## "):
            line = line[3:]
        elif line.startswith("# "):
            line = line[2:]
        elif line.startswith("- "):
            line = f"* {line[2:]}"
        lines.extend(textwrap.wrap(line, width=90) or [""])
    while lines and not lines[-1]:
        lines.pop()
    return lines or [title or "Document"]


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^[\s|:\-]+$", line)) and "---" in line


def _strip_table_pipes(line: str) -> str:
    """Remove ``|`` separators from a table row and return cells as plain text."""
    cells = [c.strip() for c in line.split("|") if c.strip()]
    return "    ".join(cells) if cells else line


def _build_pdf_with_reportlab(content: str, title: str = "") -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    if title:
        story.append(Paragraph(html_escape(title), styles["Title"]))
        story.append(Spacer(1, 12))

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue

        # Skip markdown table separator rows (| --- | --- |)
        if _is_table_separator(line):
            story.append(Spacer(1, 4))
            continue

        # Detect table rows (contain |)
        is_table_row = "|" in line and line.count("|") >= 2

        if line.startswith("### "):
            style = styles["Heading3"]
            line = _md_to_reportlab_xml(html_escape(line[4:]))
        elif line.startswith("## "):
            style = styles["Heading2"]
            line = _md_to_reportlab_xml(html_escape(line[3:]))
        elif line.startswith("# "):
            style = styles["Heading1"]
            line = _md_to_reportlab_xml(html_escape(line[2:]))
        elif is_table_row:
            style = styles["BodyText"]
            line = _strip_table_pipes(line)
            line = _md_to_reportlab_xml(html_escape(line))
        else:
            style = styles["BodyText"]
            if line.startswith("- ") or line.startswith("* "):
                prefix = 2
                line = f"&bull; {_md_to_reportlab_xml(html_escape(line[prefix:]))}"
                story.append(Paragraph(line, style))
                story.append(Spacer(1, 4))
                continue
            line = _md_to_reportlab_xml(html_escape(line))

        story.append(Paragraph(line, style))
        story.append(Spacer(1, 4))

    document.build(story)
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


_PAGE_WIDTH = 612
_PAGE_HEIGHT = 792
_LEFT_MARGIN = 72
_TOP_Y = 770
_BOTTOM_Y = 72
_FONT_SIZE = 12
_LEADING = 14


def _build_pdf_fallback(content: str, title: str = "") -> bytes:
    lines = _normalise_pdf_lines(content, title=title)

    # Break content into page streams
    pages: list[list[str]] = []
    current: list[str] = []
    y = _TOP_Y
    for line in lines:
        if y - _LEADING < _BOTTOM_Y and current:
            current.append("ET")
            pages.append(current)
            current = []
            y = _TOP_Y
        if not current:
            current = ["BT", f"/F1 {_FONT_SIZE} Tf", f"{_LEFT_MARGIN} {y} Td", f"{_LEADING} TL"]
        current.append(f"({_pdf_escape(line)}) Tj")
        current.append("T*")
        y -= _LEADING
    if current:
        current.append("ET")
        pages.append(current)
    if not pages:
        pages.append(["BT", f"/F1 {_FONT_SIZE} Tf", f"{_LEFT_MARGIN} {_TOP_Y} Td", f"{_LEADING} TL",
                       "(Document) Tj", "T*", "ET"])

    # Build PDF objects
    obj_catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
    num_pages = len(pages)
    page_refs: list[int] = []
    stream_refs: list[int] = []

    objects: list[bytes] = [obj_catalog]  # obj 1
    objects.append(b"")  # placeholder for obj 2 (Pages), filled below

    for page_stream in pages:
        stream_bytes = "\n".join(page_stream).encode("latin-1", "replace")
        page_ref = len(objects) + 1
        stream_ref = page_ref + 1
        page_refs.append(page_ref)
        stream_refs.append(stream_ref)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {num_pages + 3} 0 R >> >> "
                f"/Contents {stream_ref} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(stream_bytes)).encode("ascii") +
            b" >>\nstream\n" + stream_bytes + b"\nendstream"
        )

    # Font object
    font_ref = len(objects) + 1
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Patch the Pages object (obj 2)
    kids_str = " ".join(f"{r} 0 R" for r in page_refs)
    objects[1] = f"<< /Type /Pages /Count {num_pages} /Kids [{kids_str}] >>".encode("ascii")

    # Assemble PDF
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


class GeneratePDFTool(OrchidTool):
    name = "generate_pdf"
    description = "Generate a PDF file from Markdown-like content"
    parameters_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Document content in Markdown format",
            },
            "filename": {
                "type": "string",
                "description": "Output filename without extension",
            },
            "title": {
                "type": "string",
                "description": "Optional document title",
                "default": "",
            },
        },
        "required": ["content", "filename"],
    }
    parallel_safe = False

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        parameters = tool_input.parameters
        content = str(parameters["content"])
        title = str(parameters.get("title", "") or "")

        try:
            pdf_bytes = _build_pdf_with_reportlab(content, title=title)
            generator = "reportlab"
        except ModuleNotFoundError:
            pdf_bytes = _build_pdf_fallback(content, title=title)
            generator = "fallback"

        filepath = str(_ensure_extension(str(parameters["filename"]), ".pdf"))
        path, size, download_url = _write_content(
            pdf_bytes,
            filepath=filepath,
            mode="binary",
            context=tool_input.context,
            content_sources=tool_input.content_sources,
            auth_context=tool_input.auth_context,
        )
        return OrchidToolOutput(
            result={"path": str(path), "size_bytes": size, "format": "pdf", "download_url": download_url},
            metadata={"generator": generator, "mime": "application/pdf"},
        )
