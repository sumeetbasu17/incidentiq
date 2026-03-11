"""
IncidentIQ - Runbook RAG Tool
Manages a vector store of uploaded runbooks, past incident reports,
and internal documentation. Provides semantic search for incident resolution.
"""

import os
import json
from typing import Optional
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
)
from config import Config


def get_embeddings():
    """Initialize OpenAI embeddings via OpenRouter."""
    return OpenAIEmbeddings(
        model=Config.EMBEDDING_MODEL,
        openai_api_key=Config.OPENAI_API_KEY,
        openai_api_base=Config.EMBEDDING_BASE_URL,
    )


def get_vectorstore():
    """Get or create the ChromaDB vector store."""
    embeddings = get_embeddings()
    persist_dir = Config.CHROMA_PERSIST_DIR

    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        return Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings,
            collection_name="runbooks",
        )
    else:
        os.makedirs(persist_dir, exist_ok=True)
        return Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings,
            collection_name="runbooks",
        )


def ingest_document(file_path: str, doc_type: str = "runbook", original_name: str = None) -> dict:
    """
    Ingest a document into the vector store.
    Supports: .txt, .md, .pdf
    Deduplicates: if a file with the same name already exists, removes old chunks first.
    """
    ext = os.path.splitext(file_path)[1].lower()
    file_name = original_name or os.path.basename(file_path)

    try:
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, encoding="utf-8")

        documents = loader.load()

        # Add metadata with the REAL filename (not temp path)
        for doc in documents:
            doc.metadata["doc_type"] = doc_type
            doc.metadata["source_file"] = file_name

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.RAG_CHUNK_SIZE,
            chunk_overlap=Config.RAG_CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        )
        chunks = splitter.split_documents(documents)

        vectorstore = get_vectorstore()

        # DEDUPLICATION: remove existing chunks from same file before adding
        try:
            collection = vectorstore._collection
            existing = collection.get(where={"source_file": file_name})
            if existing and existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception:
            pass  # Collection might be empty or not support where clause yet

        # Add new chunks
        vectorstore.add_documents(chunks)

        return {
            "status": "success",
            "file": file_name,
            "chunks_created": len(chunks),
            "doc_type": doc_type,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def search_runbooks(query: str) -> str:
    """
    Search internal runbooks, incident reports, and documentation for information
    relevant to the current incident.
    
    Use this to find: standard operating procedures, past incident resolutions,
    service-specific troubleshooting guides, and known issues documentation.
    
    Args:
        query: A descriptive search query about the issue.
               Example: "PaymentService database connection pool exhaustion troubleshooting"
    """
    try:
        vectorstore = get_vectorstore()

        # Check if store has any documents
        collection = vectorstore._collection
        if collection.count() == 0:
            return json.dumps({
                "status": "empty",
                "message": "No runbooks have been uploaded yet. Upload runbooks via the sidebar to enable internal knowledge search.",
                "query": query,
            })

        # Semantic search — always return top results, let the agent judge relevance
        results = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=Config.RAG_TOP_K,
        )

        if not results:
            return json.dumps({
                "status": "no_matches",
                "message": f"No relevant runbook sections found for: {query}",
                "query": query,
            })

        matches = []
        for doc, score in results:
            # Include all results — don't filter by threshold
            # Let the LLM agent decide what's relevant
            matches.append({
                "content": doc.page_content[:800],
                "source_file": doc.metadata.get("source_file", "unknown"),
                "doc_type": doc.metadata.get("doc_type", "unknown"),
                "relevance_score": round(float(score), 3),
            })

        output = {
            "status": "success",
            "query": query,
            "total_matches": len(matches),
            "matches": matches,
        }

        return json.dumps(output, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Runbook search error: {str(e)}",
            "query": query,
        })


def get_ingested_docs() -> list:
    """List all documents currently in the vector store."""
    try:
        vectorstore = get_vectorstore()
        collection = vectorstore._collection
        if collection.count() == 0:
            return []
        # Get unique source files from metadata
        all_data = collection.get(include=["metadatas"])
        sources = set()
        for meta in all_data.get("metadatas", []):
            if meta and "source_file" in meta:
                sources.add(meta["source_file"])
        return list(sources)
    except Exception:
        return []


def delete_document(file_name: str) -> dict:
    """Delete a specific document (all its chunks) from the vector store."""
    try:
        vectorstore = get_vectorstore()
        collection = vectorstore._collection
        existing = collection.get(where={"source_file": file_name})
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
            return {"status": "success", "file": file_name, "chunks_deleted": len(existing["ids"])}
        return {"status": "not_found", "file": file_name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def clear_all_documents() -> dict:
    """Delete ALL documents from the runbook vector store."""
    try:
        vectorstore = get_vectorstore()
        collection = vectorstore._collection
        count = collection.count()
        if count > 0:
            all_data = collection.get()
            if all_data and all_data.get("ids"):
                collection.delete(ids=all_data["ids"])
        return {"status": "success", "chunks_deleted": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}
