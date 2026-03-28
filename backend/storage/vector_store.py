"""
Vector Store — CP05
LanceDB with FastEmbed embeddings.
Each document gets its own table keyed by doc_id.
"""

import os
import lancedb
from lancedb.pydantic import LanceModel, Vector
from fastembed import TextEmbedding

LANCEDB_PATH = os.environ.get("LANCEDB_PATH", "./lancedb_data")
EMBED_MODEL   = "BAAI/bge-small-en-v1.5"   # ~25 MB, fast, no API key
CHUNK_SIZE    = 512    # characters per chunk
CHUNK_OVERLAP = 80     # overlap between chunks
TOP_K         = 12     # chunks returned per query
EMBED_BATCH   = 32     # embed this many chunks at a time — limits peak memory

_embedder: TextEmbedding | None = None
_db: lancedb.DBConnection | None = None


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBED_MODEL)
    return _embedder


def get_db() -> lancedb.DBConnection:
    global _db
    if _db is None:
        os.makedirs(LANCEDB_PATH, exist_ok=True)
        _db = lancedb.connect(LANCEDB_PATH)
    return _db


# ── Schema ────────────────────────────────────────────────
class Chunk(LanceModel):
    doc_id:   str
    filename: str
    page_num: int
    chunk_id: int
    text:     str
    vector:   Vector(384)   # bge-small-en-v1.5 dim


# ── Chunking ──────────────────────────────────────────────
def _split_text(text: str, page_num: int, doc_id: str, filename: str) -> list[dict]:
    chunks = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "doc_id":   doc_id,
                "filename": filename,
                "page_num": page_num,
                "chunk_id": chunk_id,
                "text":     chunk_text,
            })
            chunk_id += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Ingest ────────────────────────────────────────────────
def ingest_document(doc_result) -> int:
    """
    Embed all pages of a DocumentResult and store in LanceDB.
    Returns total chunks stored.
    """
    embedder = get_embedder()
    db = get_db()
    table_name = f"doc_{doc_result.doc_id.replace('-', '_')}"

    raw_chunks = []
    for page in doc_result.pages:
        if page.text.strip():
            raw_chunks.extend(
                _split_text(page.text, page.page_num, doc_result.doc_id, doc_result.filename)
            )

    if not raw_chunks:
        return 0

    # Embed in batches to avoid memory spikes on large documents
    records = []
    for batch_start in range(0, len(raw_chunks), EMBED_BATCH):
        batch = raw_chunks[batch_start : batch_start + EMBED_BATCH]
        texts = [c["text"] for c in batch]
        embeddings = list(embedder.embed(texts))
        for chunk, vec in zip(batch, embeddings):
            records.append(Chunk(
                doc_id=chunk["doc_id"],
                filename=chunk["filename"],
                page_num=chunk["page_num"],
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                vector=vec.tolist(),
            ))

    table = db.create_table(table_name, data=records, mode="overwrite")
    return len(records)


# ── Retrieval ─────────────────────────────────────────────
def retrieve(query: str, doc_ids: list[str], top_k: int = TOP_K) -> list[dict]:
    """
    Embed the query and retrieve top-K chunks across selected doc tables.
    Returns list of {text, filename, page_num, doc_id, score}.
    """
    embedder = get_embedder()
    db = get_db()

    query_vec = list(embedder.embed([query]))[0].tolist()
    results = []

    for doc_id in doc_ids:
        table_name = f"doc_{doc_id.replace('-', '_')}"
        try:
            table = db.open_table(table_name)
            rows = (
                table.search(query_vec)
                     .limit(top_k)
                     .to_list()
            )
            for row in rows:
                results.append({
                    "text":     row["text"],
                    "filename": row["filename"],
                    "page_num": row["page_num"],
                    "doc_id":   row["doc_id"],
                    "score":    row.get("_distance", 0),
                })
        except Exception:
            continue   # table doesn't exist yet — skip

    # Sort globally by score (ascending distance = more similar)
    results.sort(key=lambda r: r["score"])
    return results[:top_k]


# ── Delete ────────────────────────────────────────────────
def delete_document_vectors(doc_id: str):
    """Drop the LanceDB table for a document."""
    db = get_db()
    table_name = f"doc_{doc_id.replace('-', '_')}"
    try:
        db.drop_table(table_name)
    except Exception:
        pass
