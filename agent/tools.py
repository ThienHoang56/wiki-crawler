"""
Wikipedia RAG Agent — Tool definitions.

Each tool wraps a FastAPI endpoint so the agent can call them over HTTP.
The server must be running at BASE_URL (default: http://localhost:8001).
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from langchain_core.tools import tool

BASE_URL = os.getenv("RAG_API_BASE_URL", "http://localhost:8001/api/v1")
# Model to use inside rag_answer tool call (overrides the API server's LLM_MODEL)
# Priority: TOOL_LLM_MODEL env > Groq > Gemini > None (use server default)
def _resolve_tool_model() -> str | None:
    if os.getenv("TOOL_LLM_MODEL"):
        return os.getenv("TOOL_LLM_MODEL")
    if os.getenv("GROQ_API_KEY"):
        return "llama-3.1-8b-instant"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini-2.5-flash"
    return None

_TOOL_LLM_MODEL = _resolve_tool_model()
_TIMEOUT = 60.0  # seconds — crawl + index can be slow


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _post(path: str, payload: dict) -> dict:
    resp = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, params: dict | None = None) -> dict | list:
    resp = httpx.get(f"{BASE_URL}{path}", params=params or {}, timeout=_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def rag_answer(question: str) -> str:
    """Ask a question and get a comprehensive answer using the full RAG pipeline.

    This tool embeds the question, searches indexed Wikipedia chunks via Hybrid
    Search (BM25 + dense vector), then passes the top results to an LLM to
    produce a cited, factual answer.

    Use this when you need a detailed, LLM-generated answer backed by
    Wikipedia sources.

    Args:
        question: The question to answer, e.g. "What is deep learning?"
    """
    try:
        payload: dict = {"query": question, "top_k": 5}
        if _TOOL_LLM_MODEL:
            payload["model"] = _TOOL_LLM_MODEL
        data = _post("/search/ask", payload)
        answer = data.get("answer", "No answer returned.")
        sources = data.get("sources", [])
        model = data.get("model", "unknown")

        if not sources:
            return f"[RAG Answer via {model}]\n{answer}\n(No sources found)"

        source_lines = "\n".join(
            f"  [{i+1}] {s['title']} — {s['url']} (chunk {s['chunk_index']})"
            for i, s in enumerate(sources[:3])
        )
        return (
            f"[RAG Answer via {model}]\n"
            f"{answer}\n\n"
            f"Sources:\n{source_lines}"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return "[Error] LLM rate limit hit. Wait a few seconds and try again."
        return f"[Error] API returned {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return f"[Error] rag_answer failed: {e}"


@tool
def retrieve_docs(query: str, top_k: int = 5) -> str:
    """Retrieve the most relevant Wikipedia document chunks for a query.

    Uses Hybrid Search (BM25 + dense vector with RRF fusion) to find related
    chunks from the indexed knowledge base WITHOUT calling an LLM.

    Use this to check whether information about a topic exists in the knowledge
    base before deciding whether to crawl or answer directly.

    Args:
        query: Search query, e.g. "gradient descent optimization"
        top_k: Number of top chunks to return (default 5)
    """
    try:
        data = _post("/search/hybrid", {"query": query, "top_k": top_k})
        results = data.get("results", [])
        if not results:
            return "No relevant documents found in the knowledge base for this query."

        lines = []
        for i, r in enumerate(results):
            snippet = r["text"][:150].replace("\n", " ")
            lines.append(
                f"[{i+1}] Title: {r['title']} | Score: {r['score']:.4f}\n"
                f"     URL: {r['url']}\n"
                f"     Snippet: {snippet}..."
            )
        return f"Found {len(results)} relevant chunks:\n\n" + "\n\n".join(lines)
    except Exception as e:
        return f"[Error] retrieve_docs failed: {e}"


@tool
def crawl_topic(topic: str, max_pages: int = 3, lang: str = "en") -> str:
    """Crawl Wikipedia and add new articles about a topic to the knowledge base.

    This tool fetches Wikipedia articles matching the topic keyword, stores them
    in PostgreSQL, chunks and embeds them, then indexes into Elasticsearch so
    they become searchable immediately.

    Use this when retrieve_docs returns no relevant results — crawl the topic
    first, then search again.

    Args:
        topic: Wikipedia topic keyword to crawl, e.g. "transformer neural network"
        max_pages: Number of articles to crawl (default 3, max recommended 10)
        lang: Wikipedia language code (default "en"; also "vi", "ja", "fr", ...)
    """
    try:
        # Step 1: Crawl → store in PostgreSQL
        crawl_data = _post("/crawl/topic", {
            "keyword": topic,
            "limit": max_pages,
            "lang": lang,
        })
        saved = crawl_data.get("pages_saved", 0)
        found = crawl_data.get("pages_found", 0)
        articles = crawl_data.get("articles", [])
        titles = [a.get("title", "") for a in articles]

        if saved == 0:
            return f"Crawl complete: no new articles found for '{topic}' (all may already exist or no matches)."

        # Step 2: Trigger background indexing
        idx_data = _post("/index/run", {})
        job_id = idx_data.get("job_id", "")

        title_list = ", ".join(titles[:5]) + ("..." if len(titles) > 5 else "")
        return (
            f"Crawled '{topic}': {saved} new article(s) saved (found {found}).\n"
            f"Articles: {title_list}\n"
            f"Indexing started (job_id: {job_id}). "
            f"Wait ~10s then search again."
        )
    except Exception as e:
        return f"[Error] crawl_topic failed: {e}"


@tool
def list_articles(limit: int = 20) -> str:
    """List Wikipedia articles currently stored in the knowledge base.

    Returns the titles and URLs of articles that have been crawled and are
    available for search. Use this to understand what topics are already
    covered before deciding to crawl more.

    Args:
        limit: Maximum number of articles to list (default 20)
    """
    try:
        data = _get("/articles", {"limit": limit, "offset": 0})
        # Response can be a list or a dict with 'items'
        items = data if isinstance(data, list) else data.get("items", [])
        if not items:
            return "Knowledge base is empty. Use crawl_topic to add articles."

        lines = [f"  [{i+1}] {a.get('title', 'Unknown')} — {a.get('url', '')}" for i, a in enumerate(items)]
        total_hint = f" (showing first {limit})" if len(items) >= limit else ""
        return f"Knowledge base contains {len(items)} article(s){total_hint}:\n" + "\n".join(lines)
    except Exception as e:
        return f"[Error] list_articles failed: {e}"
