import io
import json
import asyncio
import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from knowledge.pdf_processor import process_pdf
from knowledge.ocr_processor import ocr_scanned_pages
from storage.vector_store import ingest_document, retrieve, delete_document_vectors
from agents.rag_agent import build_context, format_retrieval_meta
from agents.team import create_team, classify_intent

load_dotenv()

# ── Rate limiter ──────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Doc Intelligence AI", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

# ── Guards ────────────────────────────────────────────────
MAX_FILE_MB   = 20
MAX_DOCS      = 10    # total docs in registry — protects memory
MAX_MSG_CHARS = 600   # prevent token abuse on chat

# In-memory document registry {doc_id: DocumentResult}
DOC_REGISTRY: dict = {}


# ── Request models ────────────────────────────────────────
class ChatRequest(BaseModel):
    message:    str
    doc_ids:    list[str]
    session_id: str = "default"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty.")
        if len(v) > MAX_MSG_CHARS:
            raise ValueError(f"Message exceeds {MAX_MSG_CHARS} character limit.")
        return v

    @field_validator("doc_ids")
    @classmethod
    def doc_ids_not_empty(cls, v):
        if not v:
            raise ValueError("Select at least one document.")
        if len(v) > MAX_DOCS:
            raise ValueError("Too many documents selected.")
        return v


# ── Health ────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status":    "ok",
        "service":   "doc-intelligence-ai",
        "docs_loaded": len(DOC_REGISTRY),
        "docs_limit":  MAX_DOCS,
    }


# ── Upload ────────────────────────────────────────────────
@app.post("/api/upload")
@limiter.limit("3/10minute")          # 3 uploads per 10 min per IP
async def upload_pdf(request: Request, file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    raw = await file.read()

    if len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {MAX_FILE_MB} MB limit. Please compress or split the document."
        )

    if len(DOC_REGISTRY) >= MAX_DOCS:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum of {MAX_DOCS} documents reached. Delete an existing document to upload a new one."
        )

    try:
        result = process_pdf(raw, file.filename)

        if result.scanned_pages > 0:
            result.pages         = ocr_scanned_pages(raw, result.pages)
            result.text_pages    = sum(1 for p in result.pages if not p.is_scanned)
            result.scanned_pages = sum(1 for p in result.pages if p.is_scanned)

        chunk_count = ingest_document(result)

    except ValueError as e:
        # Known validation errors (e.g. page limit exceeded)
        raise HTTPException(status_code=400, detail=str(e))
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
@limiter.limit("15/10minute")         # 15 messages per 10 min per IP
async def chat(request: Request, req: ChatRequest):

    chunks       = retrieve(req.message, req.doc_ids)
    ret_meta     = format_retrieval_meta(chunks)
    context      = build_context(chunks)
    intent       = classify_intent(req.message)   # 'rag' | 'summary' | 'analyst'
    team         = create_team(context)

    AGENT_LABELS = {
        "rag":     "RAG Agent",
        "summary": "Summary Agent",
        "analyst": "Analyst Agent",
    }

    async def event_stream():
        # Event 1 — retrieval metadata + predicted agent routing
        yield f"data: {json.dumps({'type': 'retrieval_meta', 'chunks': ret_meta, 'routed_to': AGENT_LABELS[intent], 'intent': intent})}\n\n"

        try:
            loop = asyncio.get_event_loop()

            def run_team():
                return list(team.run(req.message, stream=True))

            response_chunks = await loop.run_in_executor(None, run_team)

            for chunk in response_chunks:
                content = getattr(chunk, "content", None) or ""
                if content:
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
