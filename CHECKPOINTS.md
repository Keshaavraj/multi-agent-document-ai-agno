# Doc Intelligence AI — Build Checkpoints

## CP01 — Project Scaffold ✅
- [x] Folder structure: frontend/ + backend/ + .github/
- [x] React 19 + Vite 7 + React Router 7
- [x] FastAPI + Uvicorn + CORS
- [x] Health check: GET /api/health
- [x] render.yaml for Render backend deployment
- [x] GitHub Actions deploy.yml → GitHub Pages
- [x] .gitignore

## CP02 — Landing Page
- [ ] Product overview with feature cards
- [ ] Upload CTA button
- [ ] Stats bar (3 agents, multi-PDF, scanned support, live)
- [ ] Particle / animated background
- [ ] Dark blue/purple theme

## CP03 — PDF Upload + Parsing
- [ ] Drag-drop multi-file upload UI
- [ ] POST /api/upload endpoint
- [ ] pdfplumber text extraction per page
- [ ] Scanned page detection (empty text → flag for OCR)
- [ ] Upload progress feedback in UI

## CP04 — OCR Pipeline (Scanned PDFs)
- [ ] Convert scanned pages to base64 via PyMuPDF
- [ ] Send to Llama 4 Scout (Groq vision API)
- [ ] Merge OCR text back into page pipeline
- [ ] Handles mixed PDFs (some text, some scanned)

## CP05 — Embed + Vector Store
- [ ] FastEmbed chunking + embedding (BAAI/bge-small-en-v1.5)
- [ ] LanceDB per-doc collections (doc_id as table name)
- [ ] GET /api/documents — list all docs
- [ ] DELETE /api/document/{doc_id} — remove doc + embeddings

## CP06 — Single RAG Agent + SSE Streaming
- [ ] Agno Agent with Groq llama-3.3-70b-versatile
- [ ] LanceDB retrieval (top-5 chunks)
- [ ] POST /api/chat — SSE stream response
- [ ] Page number citations in responses

## CP07 — Multi-Agent Team
- [ ] Agno Team (route mode)
- [ ] Orchestrator Agent — intent routing
- [ ] RAG Agent — retrieval Q&A
- [ ] Summary Agent — full doc overview
- [ ] Analyst Agent — tables, numbers, key data extraction

## CP08 — Session Memory
- [ ] Agno session context across turns
- [ ] localStorage: selected doc IDs, settings
- [ ] Conversation history per session

## CP09 — Chat Interface
- [ ] Sidebar: doc list, active agents, performance metrics
- [ ] SSE streaming chat with markdown rendering
- [ ] Multi-doc selector
- [ ] Quick prompts
- [ ] Upload modal in chat

## CP10 — Deployment
- [ ] render.yaml verified + backend live on Render
- [ ] VITE_BACKEND_URL secret in GitHub repo
- [ ] Frontend live on GitHub Pages
- [ ] README with live demo link + screenshots
