from __future__ import annotations

from html import escape as html_escape
from io import BytesIO
import textwrap

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

from .write_file import _ensure_extension, _write_content


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
        if line.startswith("### "):
            style = styles["Heading3"]
            line = line[4:]
        elif line.startswith("## "):
            style = styles["Heading2"]
            line = line[3:]
        elif line.startswith("# "):
            style = styles["Heading1"]
            line = line[2:]
        else:
            style = styles["BodyText"]
            if line.startswith("- "):
                line = f"&bull; {html_escape(line[2:])}"
                story.append(Paragraph(line, style))
                story.append(Spacer(1, 4))
                continue
        story.append(Paragraph(html_escape(line), style))
        story.append(Spacer(1, 4))

    document.build(story)
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_fallback(content: str, title: str = "") -> bytes:
    lines = _normalise_pdf_lines(content, title=title)
    stream_lines = ["BT", "/F1 12 Tf", "72 770 Td", "14 TL"]
    for line in lines[:50]:
        stream_lines.append(f"({_pdf_escape(line)}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
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
        path, size = _write_content(
            pdf_bytes,
            filepath=filepath,
            mode="binary",
            context=tool_input.context,
            content_sources=tool_input.content_sources,
            auth_context=tool_input.auth_context,
        )
        return OrchidToolOutput(
            result={"path": str(path), "size_bytes": size, "format": "pdf"},
            metadata={"generator": generator, "mime": "application/pdf"},
        )
