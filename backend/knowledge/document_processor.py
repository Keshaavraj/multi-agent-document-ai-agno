"""
Document Processor — multi-format dispatcher.
Routes uploads to the right extractor based on file extension.
Supported: PDF, DOCX/DOC, TXT, PNG, JPG/JPEG
"""

import uuid
import io
from pathlib import Path

import fitz  # PyMuPDF — handles image → PDF conversion

from knowledge.pdf_processor import process_pdf, DocumentResult, PageResult

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
MAX_TXT_PAGES      = 40   # virtual page cap for TXT/DOCX (matches PDF cap)
PAGE_CHARS         = 1500  # characters per virtual page for DOCX/TXT


def process_document(file_bytes: bytes, filename: str) -> DocumentResult:
    """Dispatch to the right processor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Accepted: PDF, DOCX, TXT, PNG, JPG"
        )
    if ext == ".pdf":
        return process_pdf(file_bytes, filename)
    if ext in (".docx", ".doc"):
        return _process_docx(file_bytes, filename)
    if ext == ".txt":
        return _process_txt(file_bytes, filename)
    # PNG / JPG / JPEG — convert to 1-page PDF so existing OCR pipeline works
    return _process_image(file_bytes, filename, ext)


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _process_docx(file_bytes: bytes, filename: str) -> DocumentResult:
    from docx import Document as Docx  # lazy import — only needed for DOCX files
    doc_id = str(uuid.uuid4())
    doc    = Docx(io.BytesIO(file_bytes))

    # Group paragraphs into virtual pages of ~PAGE_CHARS characters
    pages: list[PageResult] = []
    buf: list[str] = []
    buf_len = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        buf.append(text)
        buf_len += len(text)
        if buf_len >= PAGE_CHARS:
            pages.append(PageResult(page_num=len(pages) + 1, text="\n".join(buf), is_scanned=False))
            buf, buf_len = [], 0
            if len(pages) >= MAX_TXT_PAGES:
                break

    if buf and len(pages) < MAX_TXT_PAGES:
        pages.append(PageResult(page_num=len(pages) + 1, text="\n".join(buf), is_scanned=False))

    if not pages:
        raise ValueError("Document appears to be empty.")

    return DocumentResult(
        doc_id=doc_id, filename=filename,
        total_pages=len(pages), text_pages=len(pages), scanned_pages=0,
        pages=pages,
    )


# ── TXT ───────────────────────────────────────────────────────────────────────

def _process_txt(file_bytes: bytes, filename: str) -> DocumentResult:
    doc_id = str(uuid.uuid4())
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="replace")

    text = text.strip()
    if not text:
        raise ValueError("Text file appears to be empty.")

    # Split into virtual pages
    pages: list[PageResult] = []
    for i in range(0, len(text), PAGE_CHARS):
        chunk = text[i : i + PAGE_CHARS].strip()
        if chunk:
            pages.append(PageResult(page_num=len(pages) + 1, text=chunk, is_scanned=False))
        if len(pages) >= MAX_TXT_PAGES:
            break

    return DocumentResult(
        doc_id=doc_id, filename=filename,
        total_pages=len(pages), text_pages=len(pages), scanned_pages=0,
        pages=pages,
    )


# ── Image (PNG / JPG) ─────────────────────────────────────────────────────────

def _process_image(file_bytes: bytes, filename: str, ext: str) -> DocumentResult:
    """
    Convert a single image to a 1-page PDF so the existing OCR pipeline
    (PyMuPDF + Llama 4 Scout) handles it without any special-casing.
    """
    filetype = "jpeg" if ext in (".jpg", ".jpeg") else ext.lstrip(".")
    img_doc  = fitz.open(stream=file_bytes, filetype=filetype)
    pdf_bytes = img_doc.convert_to_pdf()
    img_doc.close()

    # process_pdf will flag the page as scanned (no text), OCR runs automatically
    return process_pdf(pdf_bytes, filename)
