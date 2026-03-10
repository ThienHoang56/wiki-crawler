from fastapi import APIRouter
from src.controller.agent_controller import agent_controller
from src.schemas.agent_schema import (
    AgentChatRequest, AgentChatResponse,
    SessionInfo, SessionListResponse,
)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with WikiAgent",
    description="""
Send a message to the Wikipedia RAG AI Agent.

The agent uses a **ReAct loop** (Reason → Act → Observe) to decide which tools to call:

| Tool | When used |
|------|-----------|
| `list_articles` | To check what topics are in the knowledge base |
| `retrieve_docs` | To search for relevant chunks without LLM generation |
| `rag_answer` | To get a full LLM-synthesized answer with citations |
| `crawl_topic` | To crawl new Wikipedia articles when topic is missing |

**Multi-turn support**: Pass the same `session_id` across requests to maintain conversation history.

**Model override**: Set `model` to switch providers on-the-fly:
- `llama-3.1-8b-instant` (Groq — fast, free tier)
- `llama-3.3-70b-versatile` (Groq — smarter)
- `gemini-2.5-flash` (Google Gemini)
""",
)
def chat(req: AgentChatRequest) -> AgentChatResponse:
    return agent_controller.chat(req)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List active agent sessions",
)
def list_sessions() -> SessionListResponse:
    return agent_controller.list_sessions()


@router.get(
    "/sessions/{session_id}",
    response_model=SessionInfo,
    summary="Get conversation history for a session",
)
def get_session(session_id: str) -> SessionInfo:
    return agent_controller.get_session(session_id)


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a session and its history",
)
def delete_session(session_id: str) -> dict:
    return agent_controller.delete_session(session_id)
