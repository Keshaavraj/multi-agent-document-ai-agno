import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import axios from 'axios'
import PDFUploader from '../components/PDFUploader'
import { getSession, saveSelectedDocs, saveSidebarState, clearSessionMemory } from '../utils/session'
import './ChatPage.css'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const AGENT_COLORS = {
  'RAG Agent':     '#2f81f7',
  'Summary Agent': '#a371f7',
  'Analyst Agent': '#f0883e',
}

const QUICK_PROMPTS = [
  '📄 Summarise this document',
  '🔍 What are the key findings?',
  '📊 Extract all tables and statistics',
  '📌 List the main conclusions',
  '❓ What problem does this document address?',
]

export default function ChatPage() {
  const navigate = useNavigate()
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)
  const abortRef  = useRef(null)

  // Backend warm-up (Render free tier cold start)
  const [backendStatus, setBackendStatus] = useState('checking') // checking | ready | cold

  // Session
  const [sessionId,    setSessionId]    = useState('')
  const [sessionTurns, setSessionTurns] = useState(0)

  // Documents
  const [docs,         setDocs]         = useState([])
  const [selectedDocs, setSelectedDocs] = useState([])

  // UI
  const [sidebarOpen,  setSidebarOpen]  = useState(true)
  const [showUploader, setShowUploader] = useState(false)

  // Document processing status — shown as banner in main chat area
  // null | { filename, status: 'uploading'|'processing'|'done'|'error', info }
  const [docStatus, setDocStatus] = useState(null)

  // Chat
  const [messages, setMessages] = useState([])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)

  // Metrics
  const [metrics, setMetrics] = useState({
    lastResponse: 0,
    avgResponse:  0,
    totalTokens:  0,
    totalMsgs:    0,
    responseTimes: [],
  })

  const isProcessing  = docStatus && (docStatus.status === 'uploading' || docStatus.status === 'processing')
  const noDocCountRef = useRef(0)

  const getNoDocReply = (msg) => {
    noDocCountRef.current += 1
    const n = noDocCountRef.current
    const lower = msg.toLowerCase()

    if (n === 1) {
      return "Hi! I'm **Document Intelligence AI** — I can analyze, summarize, extract data, and answer questions about your documents.\n\nUpload a PDF, Word doc, image, or text file using the **Upload** button in the sidebar to get started."
    }
    if (lower.match(/total|sum|calculat|invoice|bill|amount|price|cost|tax/)) {
      return `I can calculate that for you — just upload the invoice or document containing those figures and ask me the same question.`
    }
    if (lower.match(/summar|overview|brief|tldr|key point/)) {
      return `I'll generate a summary as soon as you upload a document. Drop a PDF or Word file in the sidebar.`
    }
    if (lower.match(/what|who|when|where|how|why|which|tell me|explain|describe/)) {
      return `Good question — I can find that answer once you attach a document. Upload one from the sidebar and ask again.`
    }
    if (lower.match(/image|photo|chart|graph|diagram|picture/)) {
      return `I can analyze images and visuals too — upload an image file (PNG, JPG) or a PDF containing diagrams and I'll describe what's in them.`
    }
    if (n >= 3) {
      return `Please upload a document from the sidebar — I'm ready to help the moment you do.`
    }
    return `I need a document to work from. Upload one using the sidebar (PDF, Word, TXT, or image) and I'll get right to it.`
  }

  // ── Init ──────────────────────────────────────────────
  useEffect(() => {
    const s = getSession()
    setSessionId(s.session_id)
    setSelectedDocs(s.selected_docs || [])
    const isMobile = window.innerWidth <= 680
    setSidebarOpen(isMobile ? false : (s.sidebar_open ?? true))
    checkBackend()
    fetchDocs()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-clear 'done' status after 3 seconds
  useEffect(() => {
    if (docStatus?.status === 'done') {
      const t = setTimeout(() => setDocStatus(null), 3000)
      return () => clearTimeout(t)
    }
  }, [docStatus])

  // ── Backend health check (Render cold start) ──────────
  const checkBackend = async () => {
    setBackendStatus('checking')
    for (let i = 0; i < 12; i++) {
      try {
        await axios.get(`${BACKEND}/api/health`, { timeout: 5000 })
        setBackendStatus('ready')
        return
      } catch {
        setBackendStatus('cold')
        await new Promise(r => setTimeout(r, 5000))
      }
    }
    setBackendStatus('cold')
  }

  // ── Document management ───────────────────────────────
  const fetchDocs = async () => {
    try {
      const res = await axios.get(`${BACKEND}/api/documents`)
      setDocs(res.data)
      setBackendStatus('ready')
      // Clear any stale selected IDs that no longer exist on the backend
      const validIds = new Set(res.data.map(d => d.doc_id))
      setSelectedDocs(prev => {
        const next = prev.filter(id => validIds.has(id))
        if (next.length !== prev.length) saveSelectedDocs(next)
        return next
      })
    } catch { /* backend not yet connected */ }
  }

  const toggleDoc = (doc_id) => {
    setSelectedDocs(prev => {
      const next = prev.includes(doc_id)
        ? prev.filter(id => id !== doc_id)
        : [...prev, doc_id]
      saveSelectedDocs(next)
      return next
    })
  }

  const deleteDoc = async (doc_id) => {
    try {
      await axios.delete(`${BACKEND}/api/document/${doc_id}`)
      setDocs(prev => prev.filter(d => d.doc_id !== doc_id))
      setSelectedDocs(prev => {
        const next = prev.filter(id => id !== doc_id)
        saveSelectedDocs(next)
        return next
      })
    } catch (e) {
      console.error('Delete failed', e)
    }
  }

  const onUploaded = (result) => {
    setDocs(prev => {
      if (prev.find(d => d.doc_id === result.doc_id)) return prev
      return [...prev, result]
    })
    setSelectedDocs(prev => {
      if (prev.includes(result.doc_id)) return prev
      const next = [...prev, result.doc_id]
      saveSelectedDocs(next)
      return next
    })
    setShowUploader(false)

    // Determine sample prompts by file type
    const ext  = result.filename?.split('.').pop()?.toLowerCase() || ''
    const isImage = ['png', 'jpg', 'jpeg'].includes(ext)
    const isSheet = ['csv', 'xlsx'].includes(ext)
    const prompts = isImage
      ? ['Describe what you see in this image', 'Are there any numbers or data in this image?', 'What text is visible?']
      : isSheet
      ? ['Summarise the data', 'What are the key figures?', 'Calculate the totals']
      : ['Summarise this document', 'What are the key points?', 'Extract all figures and numbers']

    const promptList = prompts.map(p => `• *${p}*`).join('\n')

    setMessages(prev => [...prev, {
      id:           crypto.randomUUID(),
      role:         'assistant',
      content:      `**${result.filename}** is ready — I've fully understood its content and built a knowledge index across ${result.total_pages} page${result.total_pages !== 1 ? 's' : ''} (${result.chunks} knowledge chunks).\n\nYou can ask me anything about it. Here are a few ideas to get started:\n\n${promptList}\n\nOr type your own question below.`,
      retrieval:    null,
      agent:        null,
      responseTime: null,
      loading:      false,
    }])
  }

  // Called by PDFUploader on every status change
  const onDocStatusChange = ({ filename, status, info }) => {
    setDocStatus({ filename, status, info })
  }

  // ── Sidebar toggle ────────────────────────────────────
  const toggleSidebar = () => {
    setSidebarOpen(prev => {
      saveSidebarState(!prev)
      return !prev
    })
  }

  // ── New chat ──────────────────────────────────────────
  const newChat = async () => {
    if (abortRef.current) abortRef.current.abort()
    try { await axios.delete(`${BACKEND}/api/session/${sessionId}`) } catch {}
    const newId = clearSessionMemory()
    setSessionId(newId)
    setMessages([])
    setSessionTurns(0)
    setMetrics({ lastResponse: 0, avgResponse: 0, totalTokens: 0, totalMsgs: 0, responseTimes: [] })
  }

  // ── Send message ──────────────────────────────────────
  const send = useCallback(async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    if (selectedDocs.length === 0) {
      setInput('')
      setMessages(prev => [
        ...prev,
        { role: 'user', content: msg },
        {
          id:           crypto.randomUUID(),
          role:         'assistant',
          content:      getNoDocReply(msg),
          retrieval:    null,
          agent:        null,
          responseTime: null,
          loading:      false,
        },
      ])
      return
    }

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setInput('')
    setLoading(true)
    const startTime = Date.now()

    setMessages(prev => [...prev, { role: 'user', content: msg }])

    const assistantId = crypto.randomUUID()
    setMessages(prev => [...prev, {
      id:           assistantId,
      role:         'assistant',
      content:      '',
      retrieval:    null,
      agent:        null,
      responseTime: null,
      loading:      true,
    }])

    try {
      const res = await fetch(`${BACKEND}/api/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: msg, doc_ids: selectedDocs, session_id: sessionId }),
        signal:  controller.signal,
      })

      if (!res.ok) {
        const err = await res.json()
        const detail = err.detail
        const msg = Array.isArray(detail)
          ? detail.map(e => e.msg?.replace(/^Value error,\s*/i, '') || JSON.stringify(e)).join('; ')
          : (detail || 'Request failed')
        throw new Error(msg)
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') break

          try {
            const event = JSON.parse(raw)

            if (event.type === 'retrieval_meta') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, retrieval: event.chunks, agent: event.routed_to, session: event.session }
                  : m
              ))
              if (event.session) setSessionTurns(event.session.turns)
            }

            if (event.type === 'consolidating') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, consolidating: true }
                  : m
              ))
            }

            if (event.type === 'content') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.content, loading: false, consolidating: false }
                  : m
              ))
            }

            if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: `Error: ${event.message}`, loading: false }
                  : m
              ))
            }
          } catch { /* malformed event — skip */ }
        }
      }

      const elapsed = parseFloat(((Date.now() - startTime) / 1000).toFixed(2))
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, responseTime: elapsed, loading: false } : m
      ))

      setMetrics(prev => {
        const times = [...prev.responseTimes, elapsed]
        const avg   = parseFloat((times.reduce((a, b) => a + b, 0) / times.length).toFixed(2))
        const fullContent = messages.find(m => m.id === assistantId)?.content || ''
        const tokens = Math.round(fullContent.split(' ').length * 1.3)
        return {
          lastResponse:  elapsed,
          avgResponse:   avg,
          totalTokens:   prev.totalTokens + tokens,
          totalMsgs:     prev.totalMsgs + 1,
          responseTimes: times,
        }
      })

    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: e.message || 'Something went wrong. Please try again.', loading: false }
            : m
        ))
      }
    } finally {
      setLoading(false)
    }
  }, [input, loading, selectedDocs, sessionId, messages])

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  // ── Render ────────────────────────────────────────────
  return (
    <div className="chat-layout">

      {/* ── Left Sidebar: metrics + agents + session + doc list ── */}
      <aside className={`chat-sidebar ${sidebarOpen ? 'chat-sidebar--open' : 'chat-sidebar--closed'}`}>

        <div className="sidebar-header">
          <button className="sidebar-brand" onClick={() => navigate('/')}>⚙️ Doc AI</button>
          <div className="sidebar-header-actions">
            <button className="icon-btn" title="New Chat" onClick={newChat}>🔄</button>
            <button className="icon-btn" title="Close sidebar" onClick={toggleSidebar}>✕</button>
          </div>
        </div>

        {/* Performance metrics */}
        <div className="sidebar-section">
          <h3 className="sidebar-section-title">📊 Performance</h3>
          <div className="metrics-grid">
            <div className="metric"><span className="metric-label">Last Response</span><span className="metric-value">{metrics.lastResponse}s</span></div>
            <div className="metric"><span className="metric-label">Avg Response</span><span className="metric-value">{metrics.avgResponse}s</span></div>
            <div className="metric"><span className="metric-label">Total Tokens</span><span className="metric-value">{metrics.totalTokens}</span></div>
            <div className="metric"><span className="metric-label">Messages</span><span className="metric-value">{metrics.totalMsgs}</span></div>
          </div>
        </div>

        {/* Active agents */}
        <div className="sidebar-section">
          <h3 className="sidebar-section-title">🤖 Active Agents</h3>
          <div className="agents-list">
            {Object.entries(AGENT_COLORS).map(([name, color]) => (
              <div key={name} className="agent-item">
                <span className="agent-dot" style={{ background: color }} />
                <div>
                  <div className="agent-name">{name}</div>
                  <div className="agent-role">
                    {name === 'RAG Agent'     && 'Retrieval & Q&A'}
                    {name === 'Summary Agent' && 'Document Overview'}
                    {name === 'Analyst Agent' && 'Data Extraction'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Session memory */}
        <div className="sidebar-section">
          <h3 className="sidebar-section-title">🧠 Session Memory</h3>
          <div className="session-bar-wrap">
            <div className="session-bar">
              <div className="session-bar-fill" style={{ width: `${(sessionTurns / 8) * 100}%` }} />
            </div>
            <span className="session-bar-label">{sessionTurns} / 8 turns</span>
          </div>
          <button className="btn-new-chat" onClick={newChat}>New Chat</button>
        </div>

        {/* Document list — select which docs to query */}
        <div className="sidebar-section sidebar-section--docs">
          <h3 className="sidebar-section-title">📄 My Documents</h3>
          {docs.length === 0 ? (
            <p className="sidebar-empty">No documents yet. Use the chat to upload one.</p>
          ) : (
            <ul className="doc-list">
              {docs.map(d => (
                <li key={d.doc_id} className={`doc-item ${selectedDocs.includes(d.doc_id) ? 'doc-item--selected' : ''}`}>
                  <label className="doc-item-label">
                    <input
                      type="checkbox"
                      checked={selectedDocs.includes(d.doc_id)}
                      onChange={() => toggleDoc(d.doc_id)}
                    />
                    <div className="doc-item-info">
                      <span className="doc-item-name">{d.filename}</span>
                      <span className="doc-item-meta">{d.total_pages}p · {d.text_pages} text · {d.scanned_pages} OCR</span>
                    </div>
                  </label>
                  <button className="doc-item-delete" onClick={() => deleteDoc(d.doc_id)} title="Remove document">🗑</button>
                </li>
              ))}
            </ul>
          )}
        </div>

      </aside>

      {/* Dark backdrop — tapping closes sidebar on mobile */}
      {sidebarOpen && <div className="sidebar-backdrop" onClick={toggleSidebar} />}

      {/* Sidebar open button (when closed) */}
      {!sidebarOpen && (
        <button className="sidebar-open-btn" onClick={toggleSidebar}>☰</button>
      )}

      {/* ── Main chat area ── */}
      <main className="chat-main">

        {/* Top bar */}
        <div className="chat-topbar">
          {!sidebarOpen && (
            <button className="icon-btn" onClick={toggleSidebar}>☰</button>
          )}
          <div className="chat-topbar-title">
            <span className="chat-topbar-name">Doc Intelligence AI</span>
            <span className="chat-topbar-sub">Multi-agent document analysis · Agno + Groq</span>
          </div>
          <div className="chat-topbar-status">
            <span className="status-dot" />
            Agents Active
          </div>
        </div>

        {/* Backend warm-up banner */}
        {backendStatus !== 'ready' && (
          <div className={`warmup-banner warmup-banner--${backendStatus}`}>
            {backendStatus === 'checking' && '⏳ Connecting to backend…'}
            {backendStatus === 'cold'     && '🔄 Backend is warming up (Render free tier — usually takes 20–40s)…'}
          </div>
        )}

        {/* Document processing banner — shown in main chat area */}
        {docStatus && (
          <div className={`doc-status-banner doc-status-banner--${docStatus.status}`}>
            {docStatus.status === 'uploading' && (
              <>⬆️ Uploading <strong>{docStatus.filename}</strong>… please wait.</>
            )}
            {docStatus.status === 'processing' && (
              <>🔍 Processing <strong>{docStatus.filename}</strong> — OCR running on scanned pages. This can take up to 30 seconds. <strong>Please wait before asking questions.</strong></>
            )}
            {docStatus.status === 'done' && (
              <>✅ <strong>{docStatus.filename}</strong> is ready! {docStatus.info} You can now ask questions.</>
            )}
            {docStatus.status === 'error' && (
              <>❌ Failed to process <strong>{docStatus.filename}</strong>: {docStatus.info}</>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="chat-messages">

          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="chat-welcome-icon">⚙️</div>
              <h2>Doc Intelligence AI</h2>
              <p>Upload a document and ask anything — precise answers, summaries, and data extraction via multi-agent AI.</p>

              {/* Inline uploader — shown in welcome when no docs yet OR when triggered */}
              {(docs.length === 0 || showUploader) && (
                <div className="chat-upload-zone">
                  <PDFUploader onUploaded={onUploaded} onStatusChange={onDocStatusChange} />
                  <p className="chat-upload-limits">
                    PDF · DOCX · TXT · PNG · JPG &nbsp;·&nbsp; Max 20 MB · 40 pages · 10 docs · 3 uploads / 10 min
                  </p>
                </div>
              )}

              {docs.length > 0 && selectedDocs.length === 0 && !showUploader && (
                <p className="chat-hint">☑️ Select a document from the sidebar to start chatting.</p>
              )}
              {selectedDocs.length > 0 && !showUploader && (
                <div className="quick-prompts">
                  <p className="quick-prompts-label">Try asking:</p>
                  {QUICK_PROMPTS.map((p, i) => (
                    <button key={i} className="quick-prompt-btn" onClick={() => send(p)}>{p}</button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message message--${msg.role}`}>

              {msg.role === 'user' && (
                <div className="message-bubble message-bubble--user">
                  {msg.content}
                </div>
              )}

              {msg.role === 'assistant' && (
                <div className="message-bubble message-bubble--assistant">

                  {msg.agent && (
                    <div className="message-meta-row">
                      <span
                        className="agent-badge"
                        style={{ borderColor: AGENT_COLORS[msg.agent], color: AGENT_COLORS[msg.agent] }}
                      >
                        {msg.agent}
                      </span>
                      {msg.responseTime && (
                        <span className="response-time">⚡ {msg.responseTime}s</span>
                      )}
                    </div>
                  )}

                  {msg.retrieval && msg.retrieval.length > 0 && (
                    <details className="retrieval-panel">
                      <summary className="retrieval-panel-summary">
                        🔍 {msg.retrieval.length} chunks retrieved — click to inspect
                      </summary>
                      <div className="retrieval-chunks">
                        {msg.retrieval.map((c, j) => (
                          <div key={j} className="retrieval-chunk">
                            <div className="retrieval-chunk-header">
                              <span className="chunk-rank">#{c.rank}</span>
                              <span className="chunk-file">{c.filename}</span>
                              <span className="chunk-page">Page {c.page_num}</span>
                              <span
                                className="chunk-score"
                                style={{ color: c.similarity > 75 ? '#3fb950' : c.similarity > 50 ? '#f0883e' : '#f85149' }}
                              >
                                {c.similarity}% match
                              </span>
                              <span className="chunk-distance">L2: {c.distance}</span>
                            </div>
                            <p className="chunk-preview">{c.preview}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}

                  {msg.loading && !msg.content && (
                    <div className="typing-indicator">
                      <span /><span /><span />
                    </div>
                  )}
                  {msg.consolidating && msg.content && (
                    <div className="consolidating-indicator">
                      ✦ Consolidating findings…
                    </div>
                  )}
                  {msg.content && (
                    <div className="message-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Inline uploader panel — shown above input bar when 📎 clicked mid-chat */}
        {showUploader && messages.length > 0 && (
          <div className="chat-upload-panel">
            <div className="chat-upload-panel-header">
              <span>📤 Upload a document</span>
              <button className="icon-btn" onClick={() => setShowUploader(false)}>✕</button>
            </div>
            <PDFUploader onUploaded={onUploaded} onStatusChange={onDocStatusChange} />
            <p className="chat-upload-limits">
              PDF · DOCX · TXT · PNG · JPG &nbsp;·&nbsp; Max 20 MB · 40 pages · 10 docs · 3 uploads / 10 min
            </p>
          </div>
        )}

        {/* Input bar */}
        <div className="chat-input-bar">
          <button
            className="input-icon-btn"
            title="Upload a document"
            onClick={() => setShowUploader(v => !v)}
          >
            📎
          </button>
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={
              isProcessing
                ? '⏳ Document is processing — please wait…'
                : selectedDocs.length === 0
                  ? 'Select a document from the sidebar first…'
                  : 'Ask anything about your documents…'
            }
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            maxLength={600}
            disabled={loading || isProcessing}
          />
          <button
            className={`send-btn ${loading ? 'send-btn--loading' : ''}`}
            onClick={() => send()}
            disabled={loading || !input.trim() || isProcessing}
          >
            {loading ? '⏳' : '➤'}
          </button>
        </div>

      </main>
    </div>
  )
}
