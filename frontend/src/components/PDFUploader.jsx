import { useRef, useState } from 'react'
import axios from 'axios'
import './PDFUploader.css'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const MAX_SIZE_MB = 20
const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg']

export default function PDFUploader({ onUploaded, onStatusChange }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [queue, setQueue]       = useState([])   // {name, status, progress, result, error}

  const isOcring = queue.some(e => e.status === 'processing')

  const addFiles = files => {
    const valid = Array.from(files).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      if (!ALLOWED_EXTS.includes(ext)) return false
      if (f.size > MAX_SIZE_MB * 1024 * 1024) return false
      return true
    })
    if (!valid.length) return

    const entries = valid.map(f => ({
      id: crypto.randomUUID(),
      name: f.name,
      status: 'pending',   // pending | uploading | processing | done | error
      progress: 0,
      result: null,
      error: null,
      file: f,
    }))
    setQueue(prev => [...prev, ...entries])
    entries.forEach(e => uploadOne(e))
  }

  const uploadOne = async entry => {
    setQueue(prev => prev.map(e =>
      e.id === entry.id ? { ...e, status: 'uploading', progress: 0 } : e
    ))
    onStatusChange?.({ filename: entry.name, status: 'uploading' })

    const form = new FormData()
    form.append('file', entry.file)

    try {
      const res = await axios.post(`${BACKEND}/api/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: evt => {
          const pct = Math.round((evt.loaded / evt.total) * 100)
          const nextStatus = pct >= 100 ? 'processing' : 'uploading'
          setQueue(prev => prev.map(e =>
            e.id === entry.id ? { ...e, status: nextStatus, progress: pct } : e
          ))
          if (pct >= 100) {
            onStatusChange?.({ filename: entry.name, status: 'processing' })
          }
        },
      })

      const r = res.data
      setQueue(prev => prev.map(e =>
        e.id === entry.id
          ? { ...e, status: 'done', progress: 100, result: r }
          : e
      ))
      onStatusChange?.({
        filename: entry.name,
        status: 'done',
        info: `${r.total_pages} pages · ${r.chunks} chunks indexed.`,
      })
      onUploaded?.(r)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed'
      setQueue(prev => prev.map(e =>
        e.id === entry.id ? { ...e, status: 'error', error: msg } : e
      ))
      onStatusChange?.({ filename: entry.name, status: 'error', info: msg })
    }
  }

  const remove = id => setQueue(prev => prev.filter(e => e.id !== id))

  const onDrop = e => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  return (
    <div className="uploader">
      {/* Drop zone */}
      <div
        className={`uploader__zone ${dragging ? 'uploader__zone--drag' : ''}`}
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg"
          multiple
          hidden
          onChange={e => addFiles(e.target.files)}
        />
        <span className="uploader__zone-icon">📄</span>
        <p className="uploader__zone-text">
          Drop files here or <span className="uploader__link">browse</span>
        </p>
        <p className="uploader__zone-hint">
          PDF · DOCX · TXT · PNG · JPG · Max {MAX_SIZE_MB} MB each
        </p>
      </div>

      {/* OCR banner */}
      {isOcring && (
        <div className="uploader__ocr-banner">
          <span className="uploader__ocr-banner-spinner">⟳</span>
          <span>Running OCR on scanned pages — please wait, this can take up to 30 seconds…</span>
        </div>
      )}

      {/* Queue */}
      {queue.length > 0 && (
        <ul className="uploader__queue">
          {queue.map(e => (
            <li key={e.id} className={`upload-item upload-item--${e.status}`}>
              <div className="upload-item__header">
                <span className="upload-item__icon">
                  {e.status === 'done' && '✅'}
                  {e.status === 'error' && '❌'}
                  {e.status === 'processing' && '🔍'}
                  {(e.status === 'uploading' || e.status === 'pending') && '⏳'}
                </span>
                <span className="upload-item__name">{e.name}</span>
                <button className="upload-item__remove" onClick={() => remove(e.id)}>✕</button>
              </div>

              {e.status === 'uploading' && (
                <div className="upload-item__bar">
                  <div className="upload-item__fill" style={{ width: `${e.progress}%` }} />
                </div>
              )}
              {e.status === 'processing' && (
                <p className="upload-item__ocr">Running OCR on scanned pages…</p>
              )}

              {e.status === 'done' && e.result && (
                <p className="upload-item__meta">
                  {e.result.total_pages} pages ·{' '}
                  {e.result.text_pages} text ·{' '}
                  {e.result.scanned_pages} scanned ·{' '}
                  {e.result.chunks} chunks indexed
                </p>
              )}

              {e.status === 'error' && (
                <p className="upload-item__error">{e.error}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
