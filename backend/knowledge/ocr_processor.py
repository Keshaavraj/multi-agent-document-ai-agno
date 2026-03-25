"""
OCR Processor — CP04 (updated: concurrent OCR, single PDF open)
Converts scanned PDF pages to images via PyMuPDF,
sends all pages concurrently to Llama 4 Scout (Groq vision API),
and returns the extracted text per page.
"""

import os
import base64
import fitz          # PyMuPDF
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

OCR_MODEL     = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_OCR_PAGES = 8      # cap Groq vision API calls per upload
OCR_ZOOM      = 1.5    # lower than original 2.0 — reduces memory & payload size
OCR_SYSTEM    = (
    "You are a precise document OCR engine. "
    "Extract ALL text from the page exactly as it appears. "
    "Preserve tables, lists, headings, and layout as closely as possible. "
    "Return only the extracted text — no commentary, no explanations."
)


def _render_pages(pdf_bytes: bytes, page_nums: list[int]) -> dict[int, str]:
    """Open PDF once and render the requested pages to base64 JPEG strings."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    result: dict[int, str] = {}
    for pn in page_nums:
        page = doc[pn - 1]              # fitz is 0-indexed
        pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        result[pn] = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
    doc.close()
    return result


def _ocr_one(page_num: int, b64: str) -> tuple[int, str]:
    """Call Groq vision on a single page. Returns (page_num, extracted_text)."""
    resp = client.chat.completions.create(
        model=OCR_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text",      "text": OCR_SYSTEM},
            ],
        }],
        max_tokens=4096,
        temperature=0,
    )
    return page_num, resp.choices[0].message.content.strip()


def ocr_scanned_pages(pdf_bytes: bytes, pages: list) -> list:
    """
    OCR scanned pages concurrently (all API calls in parallel).
    Up to MAX_OCR_PAGES pages are processed; the rest are skipped with a note.
    """
    scanned  = [p for p in pages if p.is_scanned]
    to_ocr   = scanned[:MAX_OCR_PAGES]
    skipped  = scanned[MAX_OCR_PAGES:]

    for page in skipped:
        page.text = f"[OCR skipped — limit of {MAX_OCR_PAGES} scanned pages per upload reached]"

    if not to_ocr:
        return pages

    # Render all pages in one fitz pass
    page_nums = [p.page_num for p in to_ocr]
    b64_map   = _render_pages(pdf_bytes, page_nums)

    lookup = {p.page_num: p for p in to_ocr}

    # Fire all Groq calls concurrently
    with ThreadPoolExecutor(max_workers=MAX_OCR_PAGES) as pool:
        futures = {pool.submit(_ocr_one, pn, b64): pn for pn, b64 in b64_map.items()}
        for future in as_completed(futures):
            pn = futures[future]
            try:
                _, text = future.result()
                lookup[pn].text       = text
                lookup[pn].is_scanned = False
            except Exception as e:
                lookup[pn].text = f"[OCR failed for page {pn}: {e}]"

    return pages
