"""
Session Store — CP08
In-memory conversation history per session_id.
Each session keeps the last MAX_TURNS message pairs so the agent
has context from previous turns without blowing up the context window.
Sessions expire after TTL_SECONDS of inactivity.
"""

import time
from dataclasses import dataclass, field

MAX_TURNS   = 8        # message pairs kept per session (8 user + 8 assistant = 16 msgs)
TTL_SECONDS = 7200     # 2 hours — after this the session is cleared


@dataclass
class Session:
    session_id: str
    messages:   list[dict] = field(default_factory=list)   # {role, content}
    last_active: float     = field(default_factory=time.time)


_store: dict[str, Session] = {}


def _evict_expired():
    """Remove sessions that have been inactive beyond TTL."""
    now = time.time()
    expired = [sid for sid, s in _store.items() if now - s.last_active > TTL_SECONDS]
    for sid in expired:
        del _store[sid]


def get_history(session_id: str) -> list[dict]:
    """Return the conversation history for a session (empty list if new)."""
    _evict_expired()
    session = _store.get(session_id)
    if not session:
        return []
    return session.messages.copy()


def append_turn(session_id: str, user_msg: str, assistant_msg: str):
    """
    Add a user + assistant message pair to the session.
    Trims to MAX_TURNS pairs when the limit is exceeded.
    """
    _evict_expired()

    if session_id not in _store:
        _store[session_id] = Session(session_id=session_id)

    session = _store[session_id]
    session.messages.append({"role": "user",      "content": user_msg})
    session.messages.append({"role": "assistant",  "content": assistant_msg})

    # Keep only the last MAX_TURNS pairs (2 messages per pair)
    max_messages = MAX_TURNS * 2
    if len(session.messages) > max_messages:
        session.messages = session.messages[-max_messages:]

    session.last_active = time.time()


def clear_session(session_id: str):
    """Explicitly clear a session (e.g. user clicks 'New Chat')."""
    _store.pop(session_id, None)


def session_stats(session_id: str) -> dict:
    """Return metadata about the session for display in the UI sidebar."""
    session = _store.get(session_id)
    if not session:
        return {"turns": 0, "messages": 0}
    pairs = len(session.messages) // 2
    return {
        "turns":    pairs,
        "messages": len(session.messages),
        "max_turns": MAX_TURNS,
    }
