/**
 * Session utilities — CP08
 * Persists session_id, selected doc IDs, and UI preferences in localStorage.
 * Generates a new session_id on first visit.
 */

const KEY = 'doc_ai_session'

const defaults = {
  session_id:       null,   // UUID — generated on first load
  selected_docs:    [],     // doc_ids the user has selected
  sidebar_open:     true,   // left sidebar visibility
  right_panel_open: true,   // right documents panel visibility
}

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...defaults, ...JSON.parse(raw) } : { ...defaults }
  } catch {
    return { ...defaults }
  }
}

function save(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data))
  } catch {
    // localStorage full or blocked — fail silently
  }
}

export function getSession() {
  const data = load()
  if (!data.session_id) {
    data.session_id = crypto.randomUUID()
    save(data)
  }
  return data
}

export function saveSelectedDocs(doc_ids) {
  const data = load()
  data.selected_docs = doc_ids
  save(data)
}

export function saveSidebarState(open) {
  const data = load()
  data.sidebar_open = open
  save(data)
}

export function saveRightPanelState(open) {
  const data = load()
  data.right_panel_open = open
  save(data)
}

export function clearSessionMemory() {
  const data = load()
  data.session_id = crypto.randomUUID()   // new session = new ID
  save(data)
  return data.session_id
}
