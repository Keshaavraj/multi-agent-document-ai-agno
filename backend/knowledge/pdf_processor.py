"""
PDF Processor — CP03 + CP04
Extracts text from each page using pdfplumber.
Pages with < 80 characters are flagged as scanned.
OCR is applied to scanned pages in server.py after this step.
"""

import uuid
import io
import pdfplumber
from dataclasses import dataclass, field


SCANNED_THRESHOLD = 80   # chars per page below this → treat as scanned
MAX_PAGES = 60           # hard cap per PDF — protects Render 512 MB RAM


@dataclass
class PageResult:
    page_num: int          # 1-indexed
    text: str
    is_scanned: bool


@dataclass
class DocumentResult:
    doc_id: str
    filename: str
    total_pages: int
    text_pages: int
    scanned_pages: int
    pages: list[PageResult] = field(default_factory=list)


def process_pdf(file_bytes: bytes, filename: str) -> DocumentResult:
    """
    Parse a PDF from raw bytes.
    Returns a DocumentResult with per-page text and scanned flags.
    OCR for scanned pages is handled separately by ocr_processor.
    """
    doc_id = str(uuid.uuid4())
    pages: list[PageResult] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise ValueError(
                f"PDF has {len(pdf.pages)} pages — maximum allowed is {MAX_PAGES}. "
                "Please split the document and upload sections separately."
            )
        for i, page in enumerate(pdf.pages):
            try:
                raw = page.extract_text() or ""
                text = raw.strip()
            except Exception:
                text = ""   # treat unreadable page as scanned
            is_scanned = len(text) < SCANNED_THRESHOLD

            pages.append(PageResult(
                page_num=i + 1,
                text=text,
                is_scanned=is_scanned,
            ))

    text_pages = sum(1 for p in pages if not p.is_scanned)
    scanned_pages = sum(1 for p in pages if p.is_scanned)

    return DocumentResult(
        doc_id=doc_id,
        filename=filename,
        total_pages=len(pages),
        text_pages=text_pages,
        scanned_pages=scanned_pages,
        pages=pages,
    )
