import io
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from knowledge.pdf_processor import process_pdf

load_dotenv()

app = FastAPI(title="Doc Intelligence AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://Keshaavraj.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory document registry  {doc_id: DocumentResult}
# Replaced by LanceDB in CP05
DOC_REGISTRY: dict = {}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "doc-intelligence-ai"}


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit.")

    try:
        result = process_pdf(io.BytesIO(raw), file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF parsing failed: {e}")

    DOC_REGISTRY[result.doc_id] = result

    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "total_pages": result.total_pages,
        "text_pages": result.text_pages,
        "scanned_pages": result.scanned_pages,
    }


@app.get("/api/documents")
async def list_documents():
    return [
        {
            "doc_id": d.doc_id,
            "filename": d.filename,
            "total_pages": d.total_pages,
            "text_pages": d.text_pages,
            "scanned_pages": d.scanned_pages,
        }
        for d in DOC_REGISTRY.values()
    ]


@app.delete("/api/document/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail="Document not found.")
    del DOC_REGISTRY[doc_id]
    return {"deleted": doc_id}
