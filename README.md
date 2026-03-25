# Multi-Agent Document AI

A production-grade document intelligence system powered by a three-specialist AI agent team. Upload PDFs (text or scanned), ask questions in natural language, and get cited, context-grounded answers — streamed token-by-token with full retrieval transparency.

**Live Demo:** [https://Keshaavraj.github.io/multi-agent-document-ai-agno](https://Keshaavraj.github.io/multi-agent-document-ai-agno)

> The backend runs on Render free tier. First request may take 20–40 seconds to warm up — the UI shows a live warm-up indicator.

---

## What It Does

| Capability | Detail |
|---|---|
| PDF ingestion | Text extraction via pdfplumber; auto-detects scanned pages |
| OCR | Scanned pages rendered at 2× zoom → Llama 4 Scout Vision reads them |
| Multi-PDF | Upload up to 10 documents; select any combination per query |
| Vector retrieval | Local FastEmbed embeddings → LanceDB per-document tables |
| Multi-agent routing | Orchestrator classifies intent → routes to RAG / Summary / Analyst |
| SSE streaming | Token-by-token response with retrieval metadata (score, page, preview) |
| Session memory | Up to 8 conversation turns per session, 2-hour TTL |
| Abuse protection | Rate limits, 40-page cap, 8 OCR-page cap, message length guard |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  PDF Uploader → Chat Interface → SSE Parser → Retrieval Panel  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  POST /api/upload                                               │
│  ├── pdfplumber  → text extraction                              │
│  ├── scanned page detection (< 80 chars threshold)              │
│  └── PyMuPDF + Llama 4 Scout → OCR (max 8 pages)               │
│                                                                 │
│  Ingest Pipeline                                                │
│  ├── chunk (512 chars, 80 overlap)                              │
│  ├── FastEmbed BAAI/bge-small-en-v1.5 → 384-dim vectors        │
│  └── LanceDB table per document (doc_{uuid})                   │
│                                                                 │
│  POST /api/chat  (SSE)                                          │
│  ├── FastEmbed query → L2 search across selected doc tables     │
│  ├── classify_intent() → keyword pre-routing hint               │
│  ├── session_store → last 8 turns of conversation history       │
│  └── Agno Team (route mode)                                     │
│       ├── Orchestrator  ← llama-3.3-70b-versatile               │
│       ├── RAG Agent     ← llama-3.3-70b-versatile (Q&A)        │
│       ├── Summary Agent ← llama-3.3-70b-versatile (summaries)  │
│       └── Analyst Agent ← llama-3.3-70b-versatile (tables/data)│
│                                                                 │
│  SSE events: retrieval_meta → content tokens → [DONE]          │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:**
1. Upload → extract text → OCR scanned pages → chunk → embed → store in LanceDB
2. Query → embed → L2 search → top-6 chunks → inject as context → Agno Team streams answer
3. Retrieval metadata (similarity %, page number, preview) sent as first SSE event before tokens begin

---

## AI Models

### Llama 3.3 70B Versatile — `meta-llama/llama-3.3-70b-versatile`
- **Type:** Decoder-only large language model
- **Architecture:** Transformer, 70 billion parameters, grouped-query attention
- **Role:** All three specialist agents (RAG, Summary, Analyst) and the orchestrator
- **Why this model:** Best open-weight model available on Groq for instruction-following at document-Q&A tasks. Handles structured output (tables, bullet points, citations) reliably and fits within Groq's free-tier context window.
- **Inference:** Groq API (hardware-accelerated LPU — typically 200–400 tokens/second)

### Llama 4 Scout 17B — `meta-llama/llama-4-scout-17b-16e-instruct`
- **Type:** Vision-language model (multimodal)
- **Architecture:** Mixture-of-Experts (MoE) decoder with 17B active parameters across 16 experts; native image understanding via vision encoder
- **Role:** OCR agent — reads scanned PDF pages rendered as JPEG images
- **Why this model:** Groq's only production vision model at the time of build. MoE architecture gives strong vision-to-text accuracy at lower per-token cost than dense models of equivalent capability.
- **Input:** PDF pages rendered by PyMuPDF at 2× zoom → JPEG → Base64-encoded → vision API

### BAAI/bge-small-en-v1.5 — FastEmbed local embedding
- **Type:** Bi-encoder sentence embedding model
- **Architecture:** BERT-based encoder (transformer), 384-dimensional output vectors
- **Role:** Converts document chunks and user queries into dense vector representations for similarity search
- **Why this model:** ~25 MB, runs entirely locally (no API key, no latency, no cost). BAAI/bge models consistently rank at the top of the MTEB benchmark for retrieval tasks relative to their size class. Enables zero-dependency embedding on Render free tier.

---

## Retrieval Evaluation

The system exposes retrieval internals for every response so you can evaluate quality directly:

| Metric | How it's calculated | Where it appears |
|---|---|---|
| Similarity score | `max(0, 1 − L2_distance) × 100` | Retrieval panel, color-coded green/orange/red |
| Raw L2 distance | Euclidean distance between query and chunk vectors | Retrieval panel (expandable) |
| Rank | Ordered 1–6 by ascending L2 distance | Retrieval panel |
| Page citation | Stored per chunk at ingest time | Retrieval panel + agent response |
| Chunk preview | First 120 characters of each retrieved chunk | Retrieval panel |

**Why L2 distance:** LanceDB's default search uses L2 (Euclidean) distance on normalized bge vectors, which is equivalent to cosine similarity for unit-length embeddings. Similarity is converted to a 0–100 percentage for human readability.

**Qualitative validation approach:**
- Upload a PDF you know well and ask specific factual questions → verify citations match source pages
- Ask a question whose answer is not in the document → observe the agent correctly decline or caveat
- Compare RAG Agent vs Summary Agent output on the same document to verify specialist routing works
- Check retrieval scores: well-matched chunks should consistently score ≥ 60%

---

## Agent Routing

```
User query
    │
    ▼
classify_intent()  ─── keyword scan ──▶  intent hint (rag / summary / analyst)
    │
    ▼
Orchestrator Agent  (llama-3.3-70b-versatile)
    │
    ├──▶ RAG Agent      — "what does the contract say about...", specific Q&A
    ├──▶ Summary Agent  — "summarize", "key points", "executive summary"
    └──▶ Analyst Agent  — "extract table", "statistics", "compare figures"
```

The orchestrator receives the full document context, user query, and conversation history. It selects the best specialist and delegates. The UI shows which agent handled each response via an agent badge.

---

## Tech Stack

| Layer | Technology | Version | Why |
|---|---|---|---|
| Frontend framework | React | 19 | Latest stable; concurrent rendering |
| Build tool | Vite | 7 | Sub-second HMR, optimised production builds |
| Routing | React Router | 7 | File-based routing, consistent with other projects |
| Styling | CSS Modules + custom CSS | — | Zero runtime overhead, full control |
| AI agent framework | Agno | 1.4.4 | Native multi-agent Team/route mode; clean SSE support |
| LLM inference | Groq API | — | LPU hardware; fastest open-weight inference available |
| OCR model | Llama 4 Scout (Groq vision) | — | Only production vision model on Groq |
| Embedding model | FastEmbed (BAAI/bge-small-en-v1.5) | 0.4.1 | Local, no API key, top MTEB retrieval scores for size |
| Vector store | LanceDB | 0.13.0 | File-based, zero infra, per-doc tables, fast L2 search |
| PDF text extraction | pdfplumber | 0.11.4 | Accurate layout-aware text; reliable scanned detection |
| PDF rendering (OCR) | PyMuPDF | 1.24.10 | High-quality page rasterisation at arbitrary zoom |
| Backend framework | FastAPI | 0.115.0 | Async, SSE via StreamingResponse, automatic OpenAPI docs |
| Rate limiting | SlowAPI | 0.1.9 | IP-based limits without Redis; protects billing caps |
| Backend hosting | Render (free tier) | — | Docker-free Python deployment, Singapore region |
| Frontend hosting | GitHub Pages | — | Free static hosting; CI/CD via GitHub Actions |

---

## Project Structure

```
multi-agent-document-ai-agno/
├── backend/
│   ├── agents/
│   │   ├── rag_agent.py          # RAG specialist + retrieval metadata formatter
│   │   ├── summary_agent.py      # Summarisation specialist
│   │   ├── analyst_agent.py      # Data/table extraction specialist
│   │   └── team.py               # Agno Team, orchestrator, intent classifier
│   ├── knowledge/
│   │   ├── pdf_processor.py      # pdfplumber extraction, scanned page detection
│   │   └── ocr_processor.py      # PyMuPDF rendering + Llama 4 Scout OCR
│   ├── storage/
│   │   ├── vector_store.py       # FastEmbed + LanceDB ingest and retrieval
│   │   └── session_store.py      # In-memory session history, TTL eviction
│   ├── server.py                 # FastAPI app, all endpoints, SSE streaming
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx   # Product overview, particle animation
│   │   │   └── ChatPage.jsx      # Full chat interface with sidebar
│   │   ├── components/
│   │   │   └── PDFUploader.jsx   # Drag-drop multi-file uploader
│   │   └── utils/
│   │       └── session.js        # localStorage session helpers
│   ├── vite.config.js
│   └── package.json
├── .github/workflows/deploy.yml  # GitHub Actions → GitHub Pages
├── render.yaml                   # Render backend deployment config
└── CHECKPOINTS.md                # Build milestone log
```

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- A [Groq API key](https://console.groq.com) (free tier available)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your GROQ_API_KEY

uvicorn server:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. Health check: `GET /api/health`

### Frontend

```bash
cd frontend
npm install

# Create .env.local
echo "VITE_BACKEND_URL=http://localhost:8000" > .env.local

npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## Deployment

### Backend — Render

1. Push this repository to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint → connect your repo
3. Render reads `render.yaml` automatically
4. In the Render dashboard, set the `GROQ_API_KEY` environment variable manually
5. Deploy — backend URL will be `https://<service-name>.onrender.com`

> **Note:** Render free tier spins down after 15 minutes of inactivity. The frontend shows a warm-up banner and polls `/api/health` until the backend responds (up to 60 seconds).

### Frontend — GitHub Pages

1. In your GitHub repo → Settings → Secrets → Actions, add:
   - `VITE_BACKEND_URL` = your Render backend URL
2. Push to `main` — GitHub Actions builds and deploys automatically
3. Enable GitHub Pages in Settings → Pages → Source: `GitHub Actions`

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check, returns `{"status": "ok"}` |
| `/api/upload` | POST | Upload PDF; returns `doc_id`, page stats, chunk count |
| `/api/chat` | POST | SSE stream; sends `retrieval_meta`, content tokens, `[DONE]` |
| `/api/documents` | GET | List all ingested documents |
| `/api/document/{doc_id}` | DELETE | Remove document and its vector table |
| `/api/session/{session_id}` | DELETE | Clear conversation history for a session |

**Rate limits (per IP):**
- `/api/upload`: 3 requests per 10 minutes
- `/api/chat`: 15 requests per 10 minutes

**Document limits:**
- Max 10 documents stored simultaneously
- Max 40 pages per PDF
- Max 8 scanned (OCR) pages per upload

---

## License

MIT License

Copyright (c) 2026 Kesavan Rajendran

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This project is intended for educational and commercial use. Contributions are welcome.
