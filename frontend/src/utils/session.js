/**
 * Session utilities
 * session_id + selected_docs → sessionStorage (clears when tab closes)
 * UI preferences (sidebar_open) → localStorage (persists across sessions)
 */

const SID_KEY      = 'doc_ai_sid'        // sessionStorage
const SELECTED_KEY = 'doc_ai_selected'   // sessionStorage
const PREFS_KEY    = 'doc_ai_prefs'      // localStorage

const defaultPrefs = {
  sidebar_open: true,
}

function loadPrefs() {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    return raw ? { ...defaultPrefs, ...JSON.parse(raw) } : { ...defaultPrefs }
  } catch {
    return { ...defaultPrefs }
  }
}

function savePrefs(prefs) {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)) } catch {}
}

export function getSession() {
  let session_id = sessionStorage.getItem(SID_KEY)
  if (!session_id) {
    session_id = crypto.randomUUID()
    sessionStorage.setItem(SID_KEY, session_id)
  }
  let selected_docs = []
  try {
    const raw = sessionStorage.getItem(SELECTED_KEY)
    selected_docs = raw ? JSON.parse(raw) : []
  } catch {}
  return { session_id, selected_docs, ...loadPrefs() }
}

export function saveSelectedDocs(doc_ids) {
  try { sessionStorage.setItem(SELECTED_KEY, JSON.stringify(doc_ids)) } catch {}
}

export function saveSidebarState(open) {
  const prefs = loadPrefs()
  prefs.sidebar_open = open
  savePrefs(prefs)
}

export function clearSessionMemory() {
  const new_id = crypto.randomUUID()
  sessionStorage.setItem(SID_KEY, new_id)
  sessionStorage.removeItem(SELECTED_KEY)
  return new_id
}
