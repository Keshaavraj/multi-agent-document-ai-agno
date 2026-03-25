import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import './LandingPage.css'

const FEATURES = [
  {
    icon: '🤖',
    title: 'Multi-Agent Orchestration',
    desc: 'Agno Team routes every query to the right specialist — RAG, Summary, or Analyst agent — automatically.',
  },
  {
    icon: '📄',
    title: 'Multi-PDF Support',
    desc: 'Upload multiple documents at once. Query one, several, or all — the agent retrieves across every selected file.',
  },
  {
    icon: '🔍',
    title: 'Semantic Retrieval',
    desc: 'FastEmbed converts your query into a dense vector. LanceDB returns the most relevant chunks in milliseconds.',
  },
  {
    icon: '🖼️',
    title: 'Scanned PDF OCR',
    desc: 'Llama 4 Scout Vision reads image-only pages and extracts text, feeding it into the same retrieval pipeline.',
  },
  {
    icon: '⚡',
    title: 'Real-time Streaming',
    desc: 'Server-Sent Events deliver token-by-token responses. No waiting for the full answer to generate.',
  },
  {
    icon: '🧠',
    title: 'Session Memory',
    desc: 'Agno maintains conversation context across turns — ask follow-up questions without repeating yourself.',
  },
  {
    icon: '📊',
    title: 'Analyst Agent',
    desc: 'Extracts tables, key statistics, definitions, and structured data from dense technical documents.',
  },
  {
    icon: '📝',
    title: 'Summary Agent',
    desc: 'Produces a structured executive summary of any uploaded document with key takeaways and sections.',
  },
]

const STEPS = [
  {
    num: '01',
    title: 'Upload Your PDFs',
    desc: 'Drag and drop one or more documents — text-based or scanned. Processing starts immediately.',
  },
  {
    num: '02',
    title: 'Agents Analyse',
    desc: 'The Orchestrator reads your query and delegates to the RAG, Summary, or Analyst agent.',
  },
  {
    num: '03',
    title: 'Get Precise Answers',
    desc: 'Receive streamed responses with page citations, structured tables, and follow-up context.',
  },
]

const STATS = [
  { value: '3', label: 'AI Agents' },
  { value: '<1s', label: 'Response' },
  { value: 'Multi', label: 'PDF' },
  { value: 'OCR', label: 'Scanned' },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId
    let particles = []

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    for (let i = 0; i < 55; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.5 + 0.3,
        dx: (Math.random() - 0.5) * 0.4,
        dy: (Math.random() - 0.5) * 0.4,
        alpha: Math.random() * 0.5 + 0.1,
        color: Math.random() > 0.5 ? '47,129,247' : '163,113,247',
      })
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => {
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${p.color},${p.alpha})`
        ctx.fill()
        p.x += p.dx
        p.y += p.dy
        if (p.x < 0 || p.x > canvas.width) p.dx *= -1
        if (p.y < 0 || p.y > canvas.height) p.dy *= -1
      })
      animId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <div className="landing">
      <canvas ref={canvasRef} className="landing__canvas" />

      {/* Nav */}
      <nav className="landing__nav">
        <div className="landing__nav-brand">
          <span className="brand-icon">⚙️</span>
          <span>Doc Intelligence AI</span>
        </div>
        <button className="btn btn--outline" onClick={() => navigate('/chat')}>
          Launch Assistant →
        </button>
      </nav>

      {/* Hero */}
      <section className="landing__hero">
        <div className="landing__badge">
          <span className="badge-dot" />
          Powered by Agno · Groq · LanceDB
        </div>
        <h1 className="landing__headline">
          Ask Anything About<br />
          <span className="landing__headline--accent">Your Documents</span>
        </h1>
        <p className="landing__sub">
          Upload PDFs — text or scanned — and get instant answers, summaries,
          and structured data extractions via a multi-agent AI pipeline.
        </p>
        <div className="landing__cta-row">
          <button className="btn btn--primary" onClick={() => navigate('/chat')}>
            📄 Upload & Analyse
          </button>
          <button className="btn btn--ghost" onClick={() => navigate('/chat')}>
            💬 Ask a Question
          </button>
        </div>

        <div className="landing__stats">
          {STATS.map(s => (
            <div key={s.label} className="stat">
              <span className="stat__value">{s.value}</span>
              <span className="stat__label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="landing__steps">
        <h2 className="section-title">How It Works</h2>
        <p className="section-sub">Three steps from upload to insight</p>
        <div className="steps-grid">
          {STEPS.map((s, i) => (
            <div key={i} className="step-card">
              <span className="step-card__num">{s.num}</span>
              <h3 className="step-card__title">{s.title}</h3>
              <p className="step-card__desc">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="landing__features">
        <h2 className="section-title">Intelligent Features</h2>
        <p className="section-sub">Everything you need to unlock document intelligence</p>
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div key={i} className="feature-card">
              <span className="feature-card__icon">{f.icon}</span>
              <h3 className="feature-card__title">{f.title}</h3>
              <p className="feature-card__desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Banner */}
      <section className="landing__banner">
        <h2>Ready to interrogate your documents?</h2>
        <p>Upload a PDF and start asking questions in seconds.</p>
        <button className="btn btn--primary btn--lg" onClick={() => navigate('/chat')}>
          Launch AI Assistant →
        </button>
      </section>

      <footer className="landing__footer">
        <p>Built with Agno · Groq · LanceDB · FastEmbed · React 19</p>
      </footer>
    </div>
  )
}
