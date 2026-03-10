"""
Agent Service — Wikipedia RAG AI Agent với conversation history.

Mỗi session duy trì lịch sử hội thoại (multi-turn). Agent sử dụng LangGraph
ReAct pattern với 4 tools gọi thẳng vào các service nội bộ (không qua HTTP).
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
try:
    from langgraph.prebuilt import create_react_agent as _create_agent
except ImportError:
    from langchain.agents import create_agent as _create_agent

from src.core.llm_client import _build_llm
from src.core.config import settings
from src.services.search_service import search_service
from src.services.crawl_service import crawl_service
from src.services.index_service import index_service

logger = logging.getLogger("wiki-rag")

AGENT_SYSTEM_PROMPT = (
    "You are WikiAgent, an AI research assistant powered by a Wikipedia knowledge base. "
    "You have access to tools to search, retrieve, and crawl Wikipedia articles.\n\n"
    "TOOLS:\n"
    "- list_articles: Check which Wikipedia topics are in the knowledge base.\n"
    "- retrieve_docs: Fast hybrid search (no LLM) — use to check coverage before answering.\n"
    "- rag_answer: Full RAG pipeline — search + LLM-synthesized answer with citations.\n"
    "- crawl_topic: Crawl new Wikipedia articles when a topic is missing.\n\n"
    "STRATEGY:\n"
    "1. For direct questions, call rag_answer.\n"
    "2. If unsure about coverage, call retrieve_docs first.\n"
    "3. If no results found, call crawl_topic then retry.\n"
    "4. Always include source citations in your answer.\n"
    "Be concise, factual, and cite your sources."
)

# ---------------------------------------------------------------------------
# Internal tools (call service layer directly — faster than HTTP)
# ---------------------------------------------------------------------------

@tool
def list_articles(limit: int = 20) -> str:
    """List Wikipedia articles currently stored in the knowledge base.

    Use this to see what topics are available before deciding to crawl or answer.
    Args:
        limit: Max articles to return (default 20)
    """
    try:
        from src.core.database import SessionLocal
        from src.repository.article_repository import article_repository
        db = SessionLocal()
        try:
            items, total = article_repository.list(db, page=1, limit=limit)
        finally:
            db.close()
        if not items:
            return "Knowledge base is empty. Use crawl_topic to add articles."
        lines = [f"  [{i+1}] {a.title} — {a.url}" for i, a in enumerate(items)]
        note = f" (showing first {limit}, total may be more)" if total > limit else ""
        return f"Knowledge base: {total} article(s){note}:\n" + "\n".join(lines)
    except Exception as e:
        return f"[Error] list_articles: {e}"


@tool
def retrieve_docs(query: str, top_k: int = 5) -> str:
    """Search for relevant Wikipedia chunks using Hybrid Search (BM25 + dense vector).

    Returns raw document chunks WITHOUT LLM generation. Use to verify coverage
    before calling rag_answer, or when you only need to find specific facts.
    Args:
        query: Search query string
        top_k: Number of results to return (default 5)
    """
    try:
        results = search_service.hybrid(query, top_k=top_k)
        if not results:
            return "No relevant documents found in the knowledge base."
        lines = []
        for i, r in enumerate(results):
            snippet = r["text"][:150].replace("\n", " ")
            lines.append(
                f"[{i+1}] {r['title']} (score: {r['score']:.4f})\n"
                f"     URL: {r['url']}\n"
                f"     Snippet: {snippet}..."
            )
        return f"Found {len(results)} relevant chunks:\n\n" + "\n\n".join(lines)
    except Exception as e:
        return f"[Error] retrieve_docs: {e}"


@tool
def rag_answer(question: str) -> str:
    """Get a comprehensive answer using the full RAG pipeline.

    Performs Hybrid Search → Reranking → LLM synthesis with citations.
    Use this for questions that need a well-formed, cited answer.
    Args:
        question: The question to answer
    """
    try:
        result = search_service.answer_query(question)
        answer = result["answer"]
        sources = result.get("sources", [])
        model = result.get("model", "unknown")
        if not sources:
            return f"[RAG via {model}]\n{answer}\n(No sources found)"
        src_lines = "\n".join(
            f"  [{i+1}] {s['title']} — {s['url']}"
            for i, s in enumerate(sources[:3])
        )
        return f"[RAG via {model}]\n{answer}\n\nSources:\n{src_lines}"
    except Exception as e:
        logger.error("rag_answer tool error: %s", e, exc_info=True)
        return f"[Error] rag_answer: {e}"


@tool
def crawl_topic(keyword: str) -> str:
    """Crawl Wikipedia and add new articles about a topic to the knowledge base.

    ONLY use this when retrieve_docs returns no results for a topic.
    After crawling, wait 15 seconds then call retrieve_docs or rag_answer again.
    Args:
        keyword: Wikipedia topic to crawl (e.g. "transformer neural network")
    """
    limit: int = 3
    lang: str = "en"
    import asyncio
    from src.core.database import SessionLocal
    try:
        db = SessionLocal()
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                crawl_service.crawl_topic(db=db, keyword=keyword, limit=limit, lang=lang)
            )
            loop.close()
            # Eagerly read titles before session close
            results = result.get("results", [])
            errors = result.get("errors", [])
            saved = sum(1 for r in results if r.get("created"))
            titles = [r["article"].title for r in results if r.get("created")][:5]
            db.commit()
        finally:
            db.close()

        if saved == 0:
            return f"No new articles saved for '{keyword}' (may already exist or no Wikipedia match)."

        job = index_service.run_background()
        title_str = ", ".join(titles) + ("..." if len(titles) == 5 else "")
        return (
            f"Crawled '{keyword}': {saved} new article(s) saved.\n"
            f"Articles: {title_str}\n"
            f"Errors: {len(errors)}. "
            f"Indexing started (job: {job.id}). Wait ~15s then search again."
        )
    except Exception as e:
        logger.error("crawl_topic tool error: %s", e, exc_info=True)
        return f"[Error] crawl_topic: {e}"


TOOLS = [list_articles, retrieve_docs, rag_answer, crawl_topic]

# ---------------------------------------------------------------------------
# Session store (in-memory, thread-safe enough for demo)
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, session_id: str, model: str):
        self.session_id = session_id
        self.model = model
        self.history: list = []  # LangChain messages
        self.turn = 0


_sessions: dict[str, Session] = {}


# ---------------------------------------------------------------------------
# Agent Service
# ---------------------------------------------------------------------------

class AgentService:
    def _get_or_create_session(self, session_id: str | None, model: str) -> Session:
        sid = session_id or str(uuid.uuid4())
        if sid not in _sessions:
            _sessions[sid] = Session(sid, model)
        return _sessions[sid]

    def _build_agent(self, model_name: str):
        llm = _build_llm(
            model_name,
            settings.LLM_TEMPERATURE,
            settings.LLM_MAX_TOKENS,
        )
        try:
            # langgraph.prebuilt handles Groq native function calling better
            return _create_agent(model=llm, tools=TOOLS, prompt=AGENT_SYSTEM_PROMPT)
        except TypeError:
            # Fallback: create_agent has different signature
            return _create_agent(model=llm, tools=TOOLS, system_prompt=AGENT_SYSTEM_PROMPT)

    def _extract_text(self, content) -> str:
        """Normalize LLM response content (str or list of parts)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        return str(content) if content else ""

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        model: str | None = None,
    ) -> dict:
        """
        Process one turn of conversation.
        Returns: answer, session_id, tools_used, tool_calls, model, turn
        """
        model_name = model or settings.LLM_MODEL
        session = self._get_or_create_session(session_id, model_name)
        session.turn += 1

        agent = self._build_agent(model_name)

        # Build input: system + history + new message
        input_messages = session.history + [HumanMessage(content=message)]

        tool_calls_log: list[dict] = []
        tool_call_id_to_idx: dict[str, int] = {}  # map tool_call_id → index in tool_calls_log
        tools_used: list[str] = []
        final_answer = ""
        last_rag_result = ""
        seen_ids: set = set()

        try:
            for chunk in agent.stream(
                {"messages": input_messages},
                config={"configurable": {"thread_id": session.session_id}},
                stream_mode="values",
            ):
                last_msg = chunk["messages"][-1]
                msg_id = getattr(last_msg, "id", id(last_msg))
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
                    for tc in last_msg.tool_calls:
                        tools_used.append(tc["name"])
                        idx = len(tool_calls_log)
                        tool_calls_log.append({
                            "tool": tc["name"],
                            "args": tc["args"],
                            "result_preview": "",
                        })
                        # Store mapping by tool_call_id for result lookup
                        tc_id = tc.get("id", "")
                        if tc_id:
                            tool_call_id_to_idx[tc_id] = idx

                elif isinstance(last_msg, ToolMessage):
                    result_text = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)
                    # Try to match result to its call by tool_call_id
                    tc_id = getattr(last_msg, "tool_call_id", "")
                    if tc_id and tc_id in tool_call_id_to_idx:
                        tool_calls_log[tool_call_id_to_idx[tc_id]]["result_preview"] = result_text[:120]
                    elif tool_calls_log:
                        # fallback: fill last unfilled slot
                        for entry in reversed(tool_calls_log):
                            if not entry["result_preview"]:
                                entry["result_preview"] = result_text[:120]
                                break
                    if "[RAG" in result_text:
                        last_rag_result = result_text

                elif isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
                    content = self._extract_text(last_msg.content)
                    if content.strip():
                        final_answer = content

        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "rate" in err.lower():
                final_answer = (
                    "[Rate Limit] The LLM provider is temporarily rate-limited. "
                    "Please wait a moment and retry."
                )
            else:
                logger.error("Agent stream error: %s", exc, exc_info=True)
                # If we already got a good RAG result, use it as the answer
                if last_rag_result:
                    final_answer = last_rag_result
                else:
                    final_answer = f"[Agent Error] {err[:300]}"

        # Prefer last_rag_result if final_answer is an error or empty
        if (not final_answer or final_answer.startswith("[Agent Error]")) and last_rag_result:
            final_answer = last_rag_result
        if not final_answer:
            final_answer = "I could not generate an answer. Please try again."

        # Update history (append user + assistant turn)
        session.history.append(HumanMessage(content=message))
        session.history.append(AIMessage(content=final_answer))
        # Keep last 10 turns (20 messages)
        if len(session.history) > 20:
            session.history = session.history[-20:]

        return {
            "session_id": session.session_id,
            "message": message,
            "answer": final_answer,
            "tools_used": list(dict.fromkeys(tools_used)),  # deduplicate, preserve order
            "tool_calls": tool_calls_log,
            "model": model_name,
            "turn": session.turn,
        }

    def get_session(self, session_id: str) -> dict | None:
        s = _sessions.get(session_id)
        if not s:
            return None
        return {
            "session_id": s.session_id,
            "turn_count": s.turn,
            "history": [
                {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                for m in s.history
            ],
        }

    def list_sessions(self) -> list[str]:
        return list(_sessions.keys())

    def delete_session(self, session_id: str) -> bool:
        if session_id in _sessions:
            del _sessions[session_id]
            return True
        return False


agent_service = AgentService()
