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
  const bottomRef   = useRef(null)
  const inputRef    = useRef(null)
  const abortRef    = useRef(null)
  const fileRef     = useRef(null)

  // Session
  const [sessionId,     setSessionId]     = useState('')
  const [sessionTurns,  setSessionTurns]  = useState(0)

  // Documents
  const [docs,          setDocs]          = useState([])
  const [selectedDocs,  setSelectedDocs]  = useState([])

  // UI
  const [sidebarOpen,   setSidebarOpen]   = useState(true)
  const [showUploader,  setShowUploader]  = useState(false)

  // Chat
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState('')
  const [loading,       setLoading]       = useState(false)

  // Metrics
  const [metrics, setMetrics] = useState({
    lastResponse: 0,
    avgResponse:  0,
    totalTokens:  0,
    totalMsgs:    0,
    responseTimes: [],
  })

  // ── Init ──────────────────────────────────────────────
  useEffect(() => {
    const s = getSession()
    setSessionId(s.session_id)
    setSelectedDocs(s.selected_docs || [])
    setSidebarOpen(s.sidebar_open ?? true)
    fetchDocs()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Document management ───────────────────────────────
  const fetchDocs = async () => {
    try {
      const res = await axios.get(`${BACKEND}/api/documents`)
      setDocs(res.data)
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
    // Auto-select newly uploaded doc
    setSelectedDocs(prev => {
      if (prev.includes(result.doc_id)) return prev
      const next = [...prev, result.doc_id]
      saveSelectedDocs(next)
      return next
    })
    setShowUploader(false)
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
      alert('Please select at least one document from the sidebar.')
      return
    }

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setInput('')
    setLoading(true)
    const startTime = Date.now()

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: msg }])

    // Add placeholder assistant message
    const assistantId = crypto.randomUUID()
    setMessages(prev => [...prev, {
      id:          assistantId,
      role:        'assistant',
      content:     '',
      retrieval:   null,
      agent:       null,
      responseTime: null,
      loading:     true,
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
        throw new Error(err.detail || 'Request failed')
      }

      const reader = res.body.getReader()
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

            if (event.type === 'content') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.content, loading: false }
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

      // Finalize metrics
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
            ? { ...m, content: `Failed to connect to the backend. Is it running?\n\n${e.message}`, loading: false }
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

      {/* ── Sidebar ── */}
      <aside className={`chat-sidebar ${sidebarOpen ? 'chat-sidebar--open' : 'chat-sidebar--closed'}`}>

        {/* Header */}
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

        {/* Documents */}
        <div className="sidebar-section sidebar-section--docs">
          <div className="sidebar-section-header">
            <h3 className="sidebar-section-title">📄 Documents</h3>
            <button className="btn-upload-small" onClick={() => setShowUploader(v => !v)}>+ Upload</button>
          </div>

          {showUploader && (
            <div className="uploader-inline">
              <PDFUploader onUploaded={onUploaded} />
            </div>
          )}

          {docs.length === 0 && !showUploader && (
            <p className="sidebar-empty">No documents yet. Upload a PDF to start.</p>
          )}

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
        </div>
      </aside>

      {/* ── Sidebar toggle (when closed) ── */}
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

        {/* Messages */}
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="chat-welcome-icon">⚙️</div>
              <h2>Doc Intelligence AI</h2>
              <p>Upload a PDF and ask anything — precise answers, summaries, and data extraction via multi-agent AI.</p>
              {docs.length === 0 && (
                <button className="btn-upload-cta" onClick={() => { setSidebarOpen(true); setShowUploader(true) }}>
                  📄 Upload your first document
                </button>
              )}
              {docs.length > 0 && selectedDocs.length === 0 && (
                <p className="chat-hint">Select a document from the sidebar to start chatting.</p>
              )}
              {selectedDocs.length > 0 && (
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

              {/* User message */}
              {msg.role === 'user' && (
                <div className="message-bubble message-bubble--user">
                  {msg.content}
                </div>
              )}

              {/* Assistant message */}
              {msg.role === 'assistant' && (
                <div className="message-bubble message-bubble--assistant">

                  {/* Agent + response time badge */}
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

                  {/* Retrieval panel — inner workings */}
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

                  {/* Response content */}
                  {msg.loading && !msg.content && (
                    <div className="typing-indicator">
                      <span /><span /><span />
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

        {/* Input bar */}
        <div className="chat-input-bar">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            multiple
            hidden
            onChange={() => {
              setSidebarOpen(true)
              setShowUploader(true)
            }}
          />
          <button
            className="input-icon-btn"
            title="Upload PDF"
            onClick={() => { setSidebarOpen(true); setShowUploader(true) }}
          >
            📎
          </button>
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={
              selectedDocs.length === 0
                ? 'Select a document from the sidebar first…'
                : 'Ask anything about your documents…'
            }
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            maxLength={600}
            disabled={loading}
          />
          <button
            className={`send-btn ${loading ? 'send-btn--loading' : ''}`}
            onClick={() => send()}
            disabled={loading || !input.trim()}
          >
            {loading ? '⏳' : '➤'}
          </button>
        </div>
      </main>
    </div>
  )
}
