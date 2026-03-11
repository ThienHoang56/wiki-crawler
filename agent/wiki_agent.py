"""
Wikipedia RAG Agent — CLI entry point.

Uses LangGraph ReAct agent to reason over a set of tools that interact
with the running Wikipedia RAG API (http://localhost:8001).

Usage:
    # Interactive mode (multi-turn conversation)
    python agent/wiki_agent.py

    # One-shot question
    python agent/wiki_agent.py --question "What is the difference between AI and machine learning?"

    # Custom LLM model
    python agent/wiki_agent.py --model gemini-flash-lite-latest
    python agent/wiki_agent.py --model qwen2.5:1.5b   # Ollama local model

Prerequisites:
    - RAG API server running: poetry run uvicorn src.api.main:app --reload --port 8001
    - Docker services up:     docker compose up -d
    - .env configured with GEMINI_API_KEY or Ollama running
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

# Allow running from project root: python agent/wiki_agent.py
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.agents import create_agent

from agent.tools import rag_answer, retrieve_docs, crawl_topic, list_articles

TOOLS = [rag_answer, retrieve_docs, crawl_topic, list_articles]

AGENT_SYSTEM_PROMPT = textwrap.dedent("""\
    You are WikiAgent, an intelligent research assistant powered by a Wikipedia RAG system.

    You have access to a knowledge base of Wikipedia articles and can search, retrieve, 
    and crawl new articles to answer questions accurately.

    Available tools:
    - list_articles: Check which topics are already in the knowledge base.
    - retrieve_docs: Search for relevant chunks without generating an answer (fast).
    - rag_answer: Get a full LLM-generated answer from the knowledge base (comprehensive).
    - crawl_topic: Add new Wikipedia articles to the knowledge base when needed.

    Strategy:
    1. For simple lookups, call rag_answer directly.
    2. For multi-part questions, call retrieve_docs first to verify coverage, then rag_answer.
    3. If retrieve_docs returns no results, call crawl_topic first, then rag_answer.
    4. Always cite your sources.

    Be concise, factual, and helpful.
""")


# ---------------------------------------------------------------------------
# Build LLM — reuse config from project .env
# ---------------------------------------------------------------------------

def build_llm(model: str | None = None):
    """Build an LLM instance using the same provider logic as the RAG system.

    Provider priority (when model not specified):
    1. CLI --model flag
    2. AGENT_LLM_MODEL env var
    3. Groq (if GROQ_API_KEY set) — recommended, free
    4. Gemini (if GEMINI_API_KEY set and model is not Ollama)
    5. LLM_MODEL from .env
    """
    from src.core.llm_client import _build_llm
    from src.core.config import settings

    if not model:
        agent_model_env = os.getenv("AGENT_LLM_MODEL", "")
        if agent_model_env:
            model = agent_model_env
        elif settings.GROQ_API_KEY:
            # llama-3.1-8b-instant: 14,400 RPD free limit — sustainable for demo
            model = "llama-3.1-8b-instant"
        elif settings.GEMINI_API_KEY:
            model = "gemini-2.5-flash"
        else:
            model = settings.LLM_MODEL

    t = settings.LLM_TEMPERATURE
    n = settings.LLM_MAX_TOKENS
    return _build_llm(model, t, n), model


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def print_banner():
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║         WikiAgent — RAG AI Assistant      ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════╝{RESET}")
    print(f"{YELLOW}Type your question and press Enter. Type 'exit' to quit.{RESET}\n")


def print_step(label: str, content: str, color: str = CYAN):
    print(f"\n{color}{BOLD}[{label}]{RESET}")
    for line in content.strip().split("\n"):
        print(f"  {line}")


def stream_agent_response(agent, question: str, thread_id: str = "main"):
    """Run agent, stream steps, return final answer text."""
    config = {"configurable": {"thread_id": thread_id}}
    messages = [HumanMessage(content=question)]

    print(f"\n{BOLD}Question:{RESET} {question}")
    print(f"{YELLOW}{'─' * 60}{RESET}")

    final_answer = ""
    tool_calls_made = []
    last_rag_answer = ""  # fallback if LLM skips synthesis
    seen_msg_ids: set = set()

    import time as _time
    for attempt in range(3):
        try:
            for chunk in agent.stream({"messages": messages}, config=config, stream_mode="values"):
                last_msg = chunk["messages"][-1]
                msg_id = getattr(last_msg, "id", id(last_msg))
                if msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(msg_id)

                # Tool call by AI
                if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
                    for tc in last_msg.tool_calls:
                        tool_name = tc["name"]
                        args_str = ", ".join(f"{k}={repr(v)}" for k, v in tc["args"].items())
                        print_step("TOOL CALL", f"{tool_name}({args_str})", YELLOW)
                        tool_calls_made.append(tool_name)

                # Tool result (observation)
                elif isinstance(last_msg, ToolMessage):
                    snippet = last_msg.content[:300]
                    if len(last_msg.content) > 300:
                        snippet += "..."
                    print_step("OBSERVATION", snippet, CYAN)
                    # Save rag_answer result as fallback in case LLM passes through
                    if "[RAG Answer" in last_msg.content:
                        last_rag_answer = last_msg.content

                # Final AI answer (no pending tool calls)
                elif isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
                    raw = last_msg.content
                    # Gemini 2.5 may return a list of content parts
                    if isinstance(raw, list):
                        text_parts = [
                            p["text"] for p in raw
                            if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
                        ]
                        content = "\n".join(text_parts)
                    else:
                        content = str(raw) if raw else ""
                    if content.strip():
                        final_answer = content
            break  # success

        except Exception as exc:
            err = str(exc)
            is_rate_limit = "429" in err or "RESOURCE_EXHAUSTED" in err or "rate" in err.lower()
            if is_rate_limit and attempt < 2:
                wait_secs = 35
                print(f"\n{YELLOW}[Rate limit hit, waiting {wait_secs}s before retry {attempt+2}/3...]{RESET}")
                _time.sleep(wait_secs)
                seen_msg_ids.clear()
                continue
            # Non-rate-limit error or exhausted retries
            print(f"\n{YELLOW}[LLM Error: {err[:200]}]{RESET}")
            # If we already got a tool observation, use it as fallback answer
            if last_rag_answer:
                final_answer = last_rag_answer
            break

    # If LLM passed through without synthesizing, use the last tool result
    if not final_answer and last_rag_answer:
        final_answer = last_rag_answer

    print(f"\n{YELLOW}{'─' * 60}{RESET}")
    print_step("FINAL ANSWER", final_answer, GREEN)
    print(f"{YELLOW}{'─' * 60}{RESET}")

    if tool_calls_made:
        print(f"\n{CYAN}Tools used:{RESET} {', '.join(tool_calls_made)}")

    return final_answer


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WikiAgent — AI Agent backed by Wikipedia RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python agent/wiki_agent.py
              python agent/wiki_agent.py --question "What is reinforcement learning?"
              python agent/wiki_agent.py --question "Compare CNN and RNN" --model gemini-flash-lite-latest
        """)
    )
    parser.add_argument("--question", "-q", type=str, help="One-shot question (skip interactive mode)")
    parser.add_argument("--model", "-m", type=str, help="LLM model override (e.g. gemini-flash-lite-latest)")
    args = parser.parse_args()

    # Build LLM
    try:
        llm, model_name = build_llm(args.model)
    except Exception as e:
        print(f"{YELLOW}[Error] Could not initialize LLM: {e}{RESET}")
        print("Make sure GEMINI_API_KEY is set in .env, or Ollama is running.")
        sys.exit(1)

    # Build agent using LangChain's create_agent (LangGraph-backed)
    agent = create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=AGENT_SYSTEM_PROMPT,
    )

    print_banner()
    print(f"{CYAN}LLM:{RESET} {model_name}")
    print(f"{CYAN}Tools:{RESET} {', '.join(t.name for t in TOOLS)}")
    print(f"{CYAN}API:{RESET} {os.getenv('RAG_API_BASE_URL', 'http://localhost:8001/api/v1')}\n")

    # One-shot mode
    if args.question:
        stream_agent_response(agent, args.question)
        return

    # Interactive mode
    session_id = 0
    while True:
        try:
            question = input(f"\n{BOLD}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Goodbye!{RESET}")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print(f"{YELLOW}Goodbye!{RESET}")
            break

        session_id += 1
        try:
            stream_agent_response(agent, question, thread_id=f"session-{session_id}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}(interrupted){RESET}")
        except Exception as e:
            print(f"\n{YELLOW}[Error] {e}{RESET}")


if __name__ == "__main__":
    main()
