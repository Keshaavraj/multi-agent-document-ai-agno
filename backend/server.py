import io
import json
import asyncio
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from knowledge.pdf_processor import process_pdf
from knowledge.ocr_processor import ocr_scanned_pages
from storage.vector_store import ingest_document, retrieve, delete_document_vectors
from agents.rag_agent import build_context, create_rag_agent, format_retrieval_meta

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

# In-memory document registry {doc_id: DocumentResult}
DOC_REGISTRY: dict = {}


# ── Request models ────────────────────────────────────────
class ChatRequest(BaseModel):
    message:    str
    doc_ids:    list[str]       # which documents to search
    session_id: str = "default"


# ── Health ────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "doc-intelligence-ai"}


# ── Upload ────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit.")

    try:
        result = process_pdf(raw, file.filename)

        if result.scanned_pages > 0:
            result.pages = ocr_scanned_pages(raw, result.pages)
            result.text_pages    = sum(1 for p in result.pages if not p.is_scanned)
            result.scanned_pages = sum(1 for p in result.pages if p.is_scanned)

        chunk_count = ingest_document(result)

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF processing failed: {e}")

    DOC_REGISTRY[result.doc_id] = result

    return {
        "doc_id":        result.doc_id,
        "filename":      result.filename,
        "total_pages":   result.total_pages,
        "text_pages":    result.text_pages,
        "scanned_pages": result.scanned_pages,
        "chunks":        chunk_count,
    }


# ── Chat (SSE) ────────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.doc_ids:
        raise HTTPException(status_code=400, detail="Select at least one document.")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Retrieve relevant chunks
    chunks = retrieve(req.message, req.doc_ids)
    retrieval_meta = format_retrieval_meta(chunks)
    context = build_context(chunks)

    # Build agent with injected context
    agent = create_rag_agent(context)

    async def event_stream():
        # Event 1 — send retrieval metadata so UI can show inner workings
        yield (
            f"data: {json.dumps({'type': 'retrieval_meta', 'chunks': retrieval_meta})}\n\n"
        )

        # Event 2+ — stream agent tokens
        try:
            loop = asyncio.get_event_loop()

            def run_agent():
                return list(agent.run(req.message, stream=True))

            # Run sync Agno streaming in a thread to avoid blocking the event loop
            chunks_iter = await loop.run_in_executor(None, run_agent)

            for chunk in chunks_iter:
                content = getattr(chunk, "content", None) or ""
                if content:
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Documents ─────────────────────────────────────────────
@app.get("/api/documents")
async def list_documents():
    return [
        {
            "doc_id":        d.doc_id,
            "filename":      d.filename,
            "total_pages":   d.total_pages,
            "text_pages":    d.text_pages,
            "scanned_pages": d.scanned_pages,
        }
        for d in DOC_REGISTRY.values()
    ]


@app.delete("/api/document/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_document_vectors(doc_id)
    del DOC_REGISTRY[doc_id]
    return {"deleted": doc_id}
