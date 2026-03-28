"""
RAG Evaluation — real-time Faithfulness + Answer Relevancy per query.

Faithfulness   : Groq LLM judge — checks if every claim in the answer
                 is supported by the retrieved context. (0.0 – 1.0)

Answer Relevancy: Cosine similarity between the question embedding and
                  the answer embedding via FastEmbed. (0.0 – 1.0)

Both metrics mirror the RAGAS definitions but run fully in-process
using the same Groq key and FastEmbed model already used by the app.
"""

from __future__ import annotations
import httpx
import numpy as np
from fastembed import TextEmbedding

# ── Shared embedding model (loaded once, reused per process) ──────────────────
_embedder: TextEmbedding | None = None

def _get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _embedder


def _cosine(a: list[float], b: list[float]) -> float:
    u, v = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = (np.linalg.norm(u) * np.linalg.norm(v)) + 1e-9
    return float(np.dot(u, v) / denom)


# ── Answer Relevancy ──────────────────────────────────────────────────────────

def answer_relevancy(question: str, answer: str) -> float:
    """
    Cosine similarity between the question and answer embeddings.
    High score = answer is on-topic. Low score = answer drifted off-topic.
    """
    try:
        embedder = _get_embedder()
        q_emb, a_emb = list(embedder.embed([question, answer]))
        score = _cosine(list(q_emb), list(a_emb))
        return round(max(0.0, min(1.0, score)), 3)
    except Exception:
        return 0.0


# ── Faithfulness ─────────────────────────────────────────────────────────────

_FAITHFULNESS_PROMPT = """\
You are a strict RAG evaluation judge.

Your task: rate how FAITHFUL the AI answer is to the provided source context.

RULES:
- 1.0  → every claim in the answer is directly supported by the context
- 0.7-0.9 → most claims are supported; trivial phrasing additions only
- 0.4-0.6 → roughly half the claims are supported by the context
- 0.0-0.3 → most claims are NOT in the context or contradict it

Source context (truncated to 2000 chars):
{context}

AI answer to evaluate (truncated to 1000 chars):
{answer}

Respond with ONLY a single decimal number between 0.0 and 1.0. No explanation, no text."""


def faithfulness(answer: str, context: str, groq_api_key: str) -> float:
    """
    Ask Groq Llama to judge if the answer is grounded in the context.
    Returns a float 0.0–1.0.
    """
    if not groq_api_key or not answer.strip() or not context.strip():
        return 0.0
    try:
        prompt = _FAITHFULNESS_PROMPT.format(
            context=context[:2000],
            answer=answer[:1000],
        )
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10,
                "temperature": 0.0,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        score = float(raw.split()[0].rstrip("."))
        return round(max(0.0, min(1.0, score)), 2)
    except Exception:
        return 0.0


# ── Combined evaluator ────────────────────────────────────────────────────────

def evaluate(question: str, answer: str, context: str, groq_api_key: str) -> dict:
    """
    Run both metrics and return:
      {
        "faithfulness":      float | None,   # 0.0 – 1.0
        "answer_relevancy":  float | None,   # 0.0 – 1.0
      }
    """
    faith = faithfulness(answer, context, groq_api_key)
    relevancy = answer_relevancy(question, answer)
    return {
        "faithfulness":     faith     if faith     > 0 else None,
        "answer_relevancy": relevancy if relevancy > 0 else None,
    }
