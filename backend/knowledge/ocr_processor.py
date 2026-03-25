"""
OCR Processor — CP04
Converts scanned PDF pages to images via PyMuPDF,
sends each to Llama 4 Scout (Groq vision API),
and returns the extracted text per page.
"""

import os
import base64
import fitz          # PyMuPDF
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

OCR_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_OCR_PAGES = 8   # cap Groq vision API calls per upload
OCR_SYSTEM = (
    "You are a precise document OCR engine. "
    "Extract ALL text from the page exactly as it appears. "
    "Preserve tables, lists, headings, and layout as closely as possible. "
    "Return only the extracted text — no commentary, no explanations."
)


def _page_to_base64(pdf_bytes: bytes, page_num: int, zoom: float = 2.0) -> str:
    """Render a single PDF page to a JPEG base64 string."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num - 1]          # fitz is 0-indexed
    mat = fitz.Matrix(zoom, zoom)     # higher zoom = better OCR quality
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pix.tobytes("jpeg")
    doc.close()
    return base64.b64encode(img_bytes).decode("utf-8")


def ocr_page(pdf_bytes: bytes, page_num: int) -> str:
    """
    Run Llama 4 Scout vision on a single scanned page.
    Returns extracted text string.
    """
    b64 = _page_to_base64(pdf_bytes, page_num)

    response = client.chat.completions.create(
        model=OCR_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": OCR_SYSTEM,
                    },
                ],
            }
        ],
        max_tokens=4096,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def ocr_scanned_pages(pdf_bytes: bytes, pages: list) -> list:
    """
    Iterate over PageResult objects.
    For any page flagged as scanned, run OCR and replace its text.
    Returns the updated pages list.
    """
    updated = []
    ocr_count = 0
    for page in pages:
        if page.is_scanned:
            if ocr_count >= MAX_OCR_PAGES:
                # Cap reached — note it but don't call the API
                page.text = f"[OCR skipped — limit of {MAX_OCR_PAGES} scanned pages per upload reached]"
            else:
                try:
                    ocr_text = ocr_page(pdf_bytes, page.page_num)
                    page.text = ocr_text
                    page.is_scanned = False
                    ocr_count += 1
                except Exception as e:
                    page.text = f"[OCR failed for page {page.page_num}: {e}]"
        updated.append(page)
    return updated
