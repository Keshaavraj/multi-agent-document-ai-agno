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

from knowledge.document_processor import process_document, ALLOWED_EXTENSIONS
from knowledge.ocr_processor import ocr_scanned_pages
from storage.vector_store import ingest_document, retrieve, delete_document_vectors
from storage.session_store import get_history, append_turn, clear_session, session_stats
from storage.job_store import create_job, get_job, complete_job, fail_job
from agents.rag_agent import build_context, format_retrieval_meta, create_rag_agent
from agents.summary_agent import create_summary_agent
from agents.analyst_agent import create_analyst_agent
from agents.consolidator_agent import create_consolidator_agent
from agents.team import classify_intent

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
        "https://keshaavraj.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Guards ────────────────────────────────────────────────
MAX_FILE_MB   = 20
MAX_DOCS      = 10
MAX_MSG_CHARS = 600

DOC_REGISTRY: dict = {}

AGENT_LABELS = {
    "rag":     "RAG Agent",
    "summary": "Summary Agent",
    "analyst": "Analyst Agent",
}


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
        "status":      "ok",
        "service":     "doc-intelligence-ai",
        "docs_loaded": len(DOC_REGISTRY),
        "docs_limit":  MAX_DOCS,
    }


# ── Background processor ──────────────────────────────────
async def _process_upload(job_id: str, raw: bytes, filename: str):
    """
    Runs entirely in a thread-pool executor so heavy work (pdfplumber,
    OCR, fastembed) never blocks the event loop or hits Render's HTTP timeout.
    """
    loop = asyncio.get_event_loop()

    def _run():
        import gc

        result = process_document(raw, filename)

        if result.scanned_pages > 0:
            result.pages         = ocr_scanned_pages(raw, result.pages)
            result.text_pages    = sum(1 for p in result.pages if not p.is_scanned)
            result.scanned_pages = sum(1 for p in result.pages if p.is_scanned)

        gc.collect()
        chunk_count = ingest_document(result)
        return result, chunk_count

    try:
        result, chunk_count = await loop.run_in_executor(None, _run)
        DOC_REGISTRY[result.doc_id] = result
        complete_job(job_id, {
            "doc_id":        result.doc_id,
            "filename":      result.filename,
            "total_pages":   result.total_pages,
            "text_pages":    result.text_pages,
            "scanned_pages": result.scanned_pages,
            "chunks":        chunk_count,
        })
    except ValueError as e:
        fail_job(job_id, str(e))
    except Exception as e:
        fail_job(job_id, f"Processing failed: {e}")


# ── Upload ────────────────────────────────────────────────
@app.post("/api/upload")
@limiter.limit("3/10minute")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """
    Accepts the file, validates it quickly, then kicks off async processing.
    Returns a job_id immediately — client polls /api/upload/status/{job_id}.
    """
    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: PDF, DOCX, TXT, PNG, JPG"
        )

    raw = await file.read()

    if len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {MAX_FILE_MB} MB. Please compress or split the document."
        )

    if len(DOC_REGISTRY) >= MAX_DOCS:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum of {MAX_DOCS} documents reached. Delete one to upload a new file."
        )

    job_id = create_job(file.filename)
    asyncio.create_task(_process_upload(job_id, raw, file.filename))

    return {"job_id": job_id, "filename": file.filename, "status": "processing"}


# ── Upload status ─────────────────────────────────────────
@app.get("/api/upload/status/{job_id}")
async def upload_status(job_id: str):
    """Poll this endpoint to check async upload progress."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id":   job.job_id,
        "filename": job.filename,
        "status":   job.status,   # processing | done | failed
        "result":   job.result,
        "error":    job.error,
    }


# ── Chat (SSE) ────────────────────────────────────────────
@app.post("/api/chat")
@limiter.limit("15/10minute")
async def chat(request: Request, req: ChatRequest):

    # Load conversation history for this session
    history   = get_history(req.session_id)

    # Build a richer retrieval query for short follow-up questions
    retrieval_query = req.message
    if history and len(req.message.split()) < 12:
        recent_user_msgs = [m["content"] for m in history[-4:] if m["role"] == "user"]
        if recent_user_msgs:
            retrieval_query = " ".join(recent_user_msgs[-2:]) + " " + req.message

    # If user references a specific doc by name, search only that doc first
    # then fall back to all selected docs if nothing found
    msg_lower      = req.message.lower()
    doc_names      = {d.doc_id: d.filename for d in DOC_REGISTRY.values() if d.doc_id in req.doc_ids}
    focused_doc_id = next(
        (did for did, fname in doc_names.items() if fname.lower().split('.')[0] in msg_lower),
        None,
    )

    # Retrieve chunks + build context
    if focused_doc_id:
        chunks = retrieve(retrieval_query, [focused_doc_id])
        if not chunks:                         # nothing in focused doc — widen search
            chunks = retrieve(retrieval_query, req.doc_ids)
    else:
        chunks = retrieve(retrieval_query, req.doc_ids)
    ret_meta  = format_retrieval_meta(chunks)
    context   = build_context(chunks)
    intent    = classify_intent(req.message)

    # Route directly to the right agent — avoids fragile LLM tool-call routing
    if intent == "summary":
        agent = create_summary_agent(context)
    elif intent == "analyst":
        agent = create_analyst_agent(context)
    else:
        agent = create_rag_agent(context)

    async def event_stream():
        # Event 1 — retrieval metadata + routing decision + session info
        stats = session_stats(req.session_id)
        yield f"data: {json.dumps({'type': 'retrieval_meta', 'chunks': ret_meta, 'routed_to': AGENT_LABELS[intent], 'intent': intent, 'session': stats})}\n\n"

        final_response = []

        try:
            loop = asyncio.get_event_loop()

            # ── Step 1: run specialist agent silently, collect draft ──
            def _extract(chunk) -> str:
                """Safely extract text from an agno streaming chunk."""
                content = getattr(chunk, "content", None)
                if isinstance(content, str):
                    return content
                # Some agno events carry content as a nested message object
                msg = getattr(chunk, "message", None)
                if msg:
                    c = getattr(msg, "content", None)
                    if isinstance(c, str):
                        return c
                return ""

            def run_specialist():
                return list(agent.run(
                    req.message,
                    messages=history,
                    stream=True,
                ))

            specialist_chunks = await loop.run_in_executor(None, run_specialist)
            draft = "".join(_extract(c) for c in specialist_chunks).strip()

            # Fallback: retry without streaming if draft is empty
            if not draft:
                def run_specialist_sync():
                    resp = agent.run(req.message, messages=history, stream=False)
                    content = getattr(resp, "content", None)
                    return content if isinstance(content, str) else ""

                draft = await loop.run_in_executor(None, run_specialist_sync)
                draft = (draft or "").strip()

            # If still empty, build a clear "not found" message from context
            if not draft:
                if not chunks:
                    draft = "I could not find relevant content in the selected documents for your query. Please make sure the correct document is selected, or try rephrasing your question."
                else:
                    draft = "I found some content in your documents but was unable to generate a response. Please try rephrasing your question."

            # ── Step 2: signal consolidation starting ─────────────────
            yield f"data: {json.dumps({'type': 'consolidating'})}\n\n"

            # ── Step 3: run consolidator and stream its output ────────
            consolidator = create_consolidator_agent(req.message, draft)

            def run_consolidator():
                return list(consolidator.run(
                    "Produce the final answer now.",
                    stream=True,
                ))

            consolidated_chunks = await loop.run_in_executor(None, run_consolidator)

            for chunk in consolidated_chunks:
                content = getattr(chunk, "content", None) or ""
                if content:
                    final_response.append(content)
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

            # Fall back to draft if consolidator returned nothing
            if not final_response:
                final_response.append(draft)
                yield f"data: {json.dumps({'type': 'content', 'content': draft})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if final_response:
                append_turn(
                    req.session_id,
                    req.message,
                    "".join(final_response),
                )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Session ───────────────────────────────────────────────
@app.delete("/api/session/{session_id}")
async def reset_session(session_id: str):
    """Clear conversation history for a session (New Chat button)."""
    clear_session(session_id)
    return {"cleared": session_id}


@app.get("/api/session/{session_id}")
async def get_session_info(session_id: str):
    return session_stats(session_id)


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
