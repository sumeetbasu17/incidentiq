"""
IncidentIQ - Incident Memory Tool
Stores resolved incidents and finds similar past incidents.
Uses SQLite for structured data + ChromaDB for semantic matching.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import chromadb
from config import Config


DB_PATH = Config.INCIDENT_DB_PATH
MEMORY_CHROMA_DIR = os.path.join(os.path.dirname(DB_PATH), "incident_memory_chroma")


def _init_db():
    """Initialize SQLite database for incident records."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            error_type TEXT,
            error_message TEXT,
            severity TEXT,
            language TEXT,
            services TEXT,
            root_cause TEXT,
            resolution TEXT,
            raw_log TEXT,
            full_rca TEXT
        )
    """)
    conn.commit()
    conn.close()


def _get_memory_store():
    """Get ChromaDB store for incident embeddings using cosine similarity.
    
    Why cosine? The default L2 (Euclidean) distance in high-dimensional
    embedding space (1536-dim) produces large distances even for similar
    texts, leading to low relevance scores.  Cosine similarity compares
    the *direction* of vectors regardless of magnitude, which is the
    standard metric for text-embedding similarity search.
    """
    os.makedirs(MEMORY_CHROMA_DIR, exist_ok=True)
    embeddings = OpenAIEmbeddings(
        model=Config.EMBEDDING_MODEL,
        openai_api_key=Config.OPENAI_API_KEY,
        openai_api_base=Config.EMBEDDING_BASE_URL,
    )

    # Use cosine distance — much better relevance scores for text embeddings.
    # If an old L2 collection already exists, delete and recreate it so the
    # distance metric actually changes (ChromaDB can't alter an existing
    # collection's metric).
    client = chromadb.PersistentClient(path=MEMORY_CHROMA_DIR)
    COLLECTION_NAME = "incident_memory"

    try:
        existing = client.get_collection(COLLECTION_NAME)
        meta = existing.metadata or {}
        if meta.get("hnsw:space") != "cosine":
            # Old collection uses L2 — migrate data
            old_data = existing.get(include=["documents", "metadatas", "embeddings"])
            client.delete_collection(COLLECTION_NAME)
            new_col = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            if old_data and old_data.get("ids"):
                new_col.add(
                    ids=old_data["ids"],
                    documents=old_data.get("documents"),
                    metadatas=old_data.get("metadatas"),
                    embeddings=old_data.get("embeddings"),
                )
    except Exception:
        # Collection doesn't exist yet — will be created below
        client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return Chroma(
        persist_directory=MEMORY_CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


def store_incident(
    error_type: str,
    error_message: str,
    severity: str,
    language: str,
    services: list,
    root_cause: str,
    resolution: str,
    raw_log: str,
    full_rca: str,
) -> dict:
    """Store a resolved incident for future reference."""
    # Hash only on content (not timestamp) so same incident isn't duplicated
    incident_id = hashlib.md5(
        f"{error_type}{error_message[:200]}".encode()
    ).hexdigest()[:12]

    timestamp = datetime.now().isoformat()

    # Check if already exists — update timestamp but don't duplicate
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT id FROM incidents WHERE id = ?", (incident_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE incidents SET timestamp = ?, full_rca = ? WHERE id = ?",
            (timestamp, full_rca, incident_id),
        )
        conn.commit()
        conn.close()
        return {"status": "updated", "incident_id": incident_id}

    conn.execute(
        """INSERT OR REPLACE INTO incidents 
           (id, timestamp, error_type, error_message, severity, language, 
            services, root_cause, resolution, raw_log, full_rca)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            incident_id, timestamp, error_type, error_message, severity,
            language, json.dumps(services), root_cause, resolution,
            raw_log[:2000], full_rca,
        ),
    )
    conn.commit()
    conn.close()

    # Store embedding for semantic search
    # Include raw log snippet alongside structured fields — this makes
    # semantic search work for both structured queries ("NullPointerException")
    # and natural language queries ("I'm getting null pointer in my service")
    try:
        store = _get_memory_store()
        # Combine structured info + raw log for a richer embedding
        raw_snippet = raw_log[:500] if raw_log else ""
        doc_text = (
            f"Error: {error_type} - {error_message}\n"
            f"Root Cause: {root_cause}\n"
            f"Resolution: {resolution}\n"
            f"Log: {raw_snippet}"
        )
        from langchain_core.documents import Document
        doc = Document(
            page_content=doc_text,
            metadata={
                "incident_id": incident_id,
                "error_type": error_type,
                "severity": severity,
                "timestamp": timestamp,
            },
        )
        store.add_documents([doc])
    except Exception as e:
        print(f"Warning: Could not store incident embedding: {e}")

    return {"status": "stored", "incident_id": incident_id}


@tool
def find_similar_incidents(query: str) -> str:
    """
    Search past incident history for similar issues that were previously resolved.
    
    Use this to find: past occurrences of similar errors, proven resolutions,
    and patterns of recurring issues. This helps provide faster resolution
    by leveraging organizational incident memory.
    
    Args:
        query: Description of the current incident or error message.
               Example: "database connection pool exhaustion in PaymentService"
    """
    try:
        _init_db()
        store = _get_memory_store()
        collection = store._collection

        if collection.count() == 0:
            return json.dumps({
                "status": "empty",
                "message": "No past incidents stored yet. Incidents are saved after each analysis for future reference.",
                "query": query,
            })

        # ── Semantic search (cosine similarity) ──
        # Fetch more candidates than we need so we can analyze the
        # score distribution and find natural gaps.
        results = store.similarity_search_with_relevance_scores(query, k=10)

        if not results:
            return json.dumps({
                "status": "no_matches",
                "message": "No similar past incidents found.",
                "query": query,
            })

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Log ALL raw scores for debugging
        for doc, score in results:
            etype = doc.metadata.get("error_type", "?")
            print(f"[IncidentIQ] score={score:.4f} error_type={etype} | query={query[:50]}... | doc={doc.page_content[:60]}...")

        scores = [s for _, s in results]
        top_score = scores[0]

        # ── Score-gap thresholding ──
        # Instead of hardcoded keyword families, we use the score
        # distribution itself to decide what's a real match:
        #
        # 1. Absolute floor: top score must clear 0.60 — with cosine
        #    on the same embedding model, truly related incidents
        #    (same error type) consistently score above this.
        #    Cross-type matches (OOM vs NullPointer) sit at 0.45-0.60.
        #
        # 2. Gap detection: find the largest score drop between
        #    consecutive results. Results above the gap are "real
        #    matches"; results below are noise. This adapts to any
        #    error type without hardcoding.
        #
        # 3. Relative cutoff: even without a clear gap, only keep
        #    results within 80% of the top score.
        ABSOLUTE_MIN = 0.60

        if top_score < ABSOLUTE_MIN:
            return json.dumps({
                "status": "no_matches",
                "message": "No similar past incidents found.",
                "query": query,
            })

        # Find the largest gap in scores to separate signal from noise
        gap_cutoff = ABSOLUTE_MIN
        if len(scores) >= 2:
            max_gap = 0
            max_gap_idx = 0
            for i in range(len(scores) - 1):
                gap = scores[i] - scores[i + 1]
                if gap > max_gap:
                    max_gap = gap
                    max_gap_idx = i
            # Only use the gap if it's meaningful (> 0.08 = 8% jump)
            # and the gap isn't at the very bottom of the list
            if max_gap > 0.08 and scores[max_gap_idx] >= ABSOLUTE_MIN:
                gap_cutoff = scores[max_gap_idx + 1] + 0.001  # just above the lower group

        # Final cutoff: the stricter of gap-based and relative
        relative_cutoff = top_score * 0.80
        final_cutoff = max(gap_cutoff, relative_cutoff, ABSOLUTE_MIN)

        conn = sqlite3.connect(DB_PATH)
        similar = []
        seen_ids = set()

        for doc, score in results:
            if score < final_cutoff:
                continue
            incident_id = doc.metadata.get("incident_id", "")
            if not incident_id or incident_id in seen_ids:
                continue
            row = conn.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
            if row:
                seen_ids.add(incident_id)
                similar.append({
                    "incident_id": row[0],
                    "timestamp": row[1],
                    "error_type": row[2],
                    "error_message": row[3][:200],
                    "severity": row[4],
                    "language": row[5],
                    "root_cause": row[7],
                    "resolution": row[8],
                    "full_rca_summary": row[10][:600] if row[10] else "",
                    "similarity_score": round(score, 3),
                })
        conn.close()

        if not similar:
            return json.dumps({
                "status": "no_matches",
                "message": "No similar past incidents found.",
                "query": query,
            })

        return json.dumps({
            "status": "success",
            "query": query,
            "similar_incidents": similar,
            "count": len(similar),
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Incident memory search error: {str(e)}",
        })


def get_incident_history(limit: int = 20) -> list:
    """Get recent incident history for display."""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, timestamp, error_type, severity, services, root_cause FROM incidents ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    incidents = []
    for row in rows:
        incidents.append({
            "id": row[0],
            "timestamp": row[1],
            "error_type": row[2],
            "severity": row[3],
            "services": row[4],
            "root_cause": row[5],
        })
    return incidents


def clear_incident_memory() -> dict:
    """Delete ALL incidents from SQLite and ChromaDB incident memory."""
    try:
        _init_db()
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        conn.execute("DELETE FROM incidents")
        conn.commit()
        conn.close()

        # Clear ChromaDB incident embeddings
        try:
            store = _get_memory_store()
            collection = store._collection
            if collection.count() > 0:
                all_data = collection.get()
                if all_data and all_data.get("ids"):
                    collection.delete(ids=all_data["ids"])
        except Exception:
            pass

        return {"status": "success", "incidents_deleted": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}
