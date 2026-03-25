# Doc Intelligence AI — Build Checkpoints

## CP01 — Project Scaffold ✅
- [x] Folder structure: frontend/ + backend/ + .github/
- [x] React 19 + Vite 7 + React Router 7
- [x] FastAPI + Uvicorn + CORS
- [x] Health check: GET /api/health
- [x] render.yaml for Render backend deployment
- [x] GitHub Actions deploy.yml → GitHub Pages
- [x] .gitignore

## CP02 — Landing Page ✅
- [x] Product overview with feature cards (8 features)
- [x] Three-step workflow section
- [x] Stats bar (3 agents, <1s, multi-PDF, OCR)
- [x] Particle canvas animation (blue/purple)
- [x] Dark blue/purple theme

## CP03 — PDF Upload + Parsing ✅
- [x] Drag-drop multi-file upload UI with progress bar
- [x] POST /api/upload endpoint
- [x] pdfplumber text extraction per page
- [x] Scanned page detection (< 80 chars → flagged)
- [x] Returns: doc_id, total_pages, text_pages, scanned_pages, chunks

## CP04 — OCR Pipeline (Scanned PDFs) ✅
- [x] PyMuPDF renders scanned pages at 2× zoom → JPEG
- [x] Base64 encode → Llama 4 Scout (Groq vision API)
- [x] Max 8 OCR pages per upload (billing cap)
- [x] Mixed PDFs handled (text + scanned on same doc)
- [x] UI shows pulsing "Running OCR…" state

## CP05 — Embed + Vector Store ✅
- [x] FastEmbed BAAI/bge-small-en-v1.5 (local, no API key, ~25 MB)
- [x] LanceDB per-doc tables (doc_{uuid})
- [x] 512-char chunks with 80-char overlap
- [x] retrieve() searches across selected doc tables
- [x] Similarity = (1 − L2_distance) × 100
- [x] GET /api/documents, DELETE /api/document/{doc_id}

## CP06 — Single RAG Agent + SSE Streaming ✅
- [x] Agno Agent with Groq llama-3.3-70b-versatile
- [x] Context injected into system prompt
- [x] SSE streaming: retrieval_meta → content tokens → [DONE]
- [x] retrieval_meta includes: rank, filename, page, similarity %, L2 distance, preview

## CP07 — Multi-Agent Team ✅
- [x] Agno Team (route mode)
- [x] Orchestrator Agent — routes to RAG / Summary / Analyst
- [x] RAG Agent — retrieval Q&A with page citations
- [x] Summary Agent — executive summaries and key takeaways
- [x] Analyst Agent — tables, statistics, structured data extraction
- [x] classify_intent() — keyword-based pre-routing for UI display
- [x] SSE metadata includes: routed_to, intent

## CP08 — Session Memory ✅
- [x] Per-session conversation history (session_id UUID)
- [x] Max 8 turns, TTL 2 hours, auto-eviction
- [x] History passed to Agno Team.run(messages=history)
- [x] DELETE /api/session/{id} — reset history
- [x] localStorage: session_id, selected_docs, sidebar_open

## CP09 — Chat Interface ✅
- [x] Sidebar: metrics, active agents, session memory bar, doc list
- [x] SSE streaming with markdown rendering (tables, code, lists)
- [x] Collapsible retrieval panel per message (scores, pages, previews)
- [x] Agent badge + response time on every assistant message
- [x] Quick prompts on welcome screen
- [x] Multi-doc selector with checkbox per document
- [x] Inline PDF uploader in sidebar

## CP10 — Deployment ✅
- [x] render.yaml: Python 3.11, free tier, Singapore region, health check
- [x] GitHub Actions: Node 20, Vite build, VITE_BACKEND_URL secret, GitHub Pages
- [x] Backend warm-up banner (Render cold start indicator)
- [x] CHECKPOINTS.md completed
- [x] README with full setup instructions
