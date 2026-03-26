"""
RAG Agent — CP06
Single Agno agent that retrieves context from LanceDB
and generates grounded answers with page citations.
Returns retrieval metadata as the first SSE event so the
UI can display inner workings (scores, pages, filenames).
"""

from agno.agent import Agent
from agno.models.groq import Groq as GroqModel

RAG_MODEL = "llama-3.3-70b-versatile"

RAG_INSTRUCTIONS = """
You are a precise document intelligence assistant.

ABSOLUTE RULES:
- Answer ONLY from the provided document context — never fabricate or assume information.
- Do NOT use general knowledge, training data, or outside context under any circumstances.
- Cite every fact with [Page X] or [Filename, Page X] when multiple docs are active.
- If the answer is not in the document context, say clearly:
  "This information is not present in the provided documents."
  Do NOT attempt to answer from general knowledge as a fallback.
- Format responses using bullet points, tables, or numbered lists where helpful.
- Keep answers concise but complete — do not pad with filler.
"""


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a readable context block for the agent."""
    if not chunks:
        return "No relevant content found in the selected documents."

    unique_files = list(dict.fromkeys(c["filename"] for c in chunks))
    header = (
        f"NOTE: Content retrieved from {len(unique_files)} document(s): "
        + ", ".join(f'"{f}"' for f in unique_files)
        + ". ALWAYS prefix every fact with [filename, Page X] so the user knows which document it came from.\n\n"
        if len(unique_files) > 1 else ""
    )

    lines = []
    for c in chunks:
        lines.append(f"[{c['filename']}, Page {c['page_num']}]\n{c['text']}")
    return header + "\n\n---\n\n".join(lines)


def format_retrieval_meta(chunks: list[dict]) -> list[dict]:
    """
    Format chunk metadata for the retrieval_meta SSE event.
    Converts raw LanceDB distance scores to a 0-100 similarity percentage.
    LanceDB returns L2 distance — lower = more similar.
    We map distance → similarity: sim = max(0, 1 - distance) * 100
    """
    meta = []
    for i, c in enumerate(chunks):
        distance = c.get("score", 0)
        similarity = round(max(0.0, 1.0 - distance) * 100, 1)
        meta.append({
            "rank":       i + 1,
            "filename":   c["filename"],
            "page_num":   c["page_num"],
            "doc_id":     c["doc_id"],
            "similarity": similarity,          # 0–100 %
            "distance":   round(distance, 4),  # raw L2 distance
            "preview":    c["text"][:120] + ("…" if len(c["text"]) > 120 else ""),
        })
    return meta


def create_rag_agent(context: str) -> Agent:
    """Build an Agno RAG agent with retrieved context injected into the system prompt."""
    return Agent(
        name="RAG Agent",
        model=GroqModel(id=RAG_MODEL),
        instructions=RAG_INSTRUCTIONS,
        system_message=(
            "DOCUMENT CONTEXT — answer using ONLY this material:\n\n"
            + context
        ),
        markdown=True,
        stream=True,
    )
