"""Extract plain text from uploaded PDF bytes."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def pdf_bytes_to_text(data: bytes, max_pages: int = 80) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    return "\n\n".join(parts)
