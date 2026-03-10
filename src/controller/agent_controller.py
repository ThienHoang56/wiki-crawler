from __future__ import annotations
from fastapi import HTTPException
from src.services.agent_service import agent_service
from src.schemas.agent_schema import (
    AgentChatRequest, AgentChatResponse, ToolCallLog,
    SessionInfo, ChatMessage, SessionListResponse,
)


class AgentController:
    def chat(self, req: AgentChatRequest) -> AgentChatResponse:
        try:
            result = agent_service.chat(
                message=req.message,
                session_id=req.session_id,
                model=req.model,
            )
            return AgentChatResponse(
                session_id=result["session_id"],
                message=result["message"],
                answer=result["answer"],
                tools_used=result["tools_used"],
                tool_calls=[ToolCallLog(**tc) for tc in result["tool_calls"]],
                model=result["model"],
                turn=result["turn"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def get_session(self, session_id: str) -> SessionInfo:
        data = agent_service.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        return SessionInfo(
            session_id=data["session_id"],
            turn_count=data["turn_count"],
            history=[ChatMessage(**m) for m in data["history"]],
        )

    def list_sessions(self) -> SessionListResponse:
        sessions = agent_service.list_sessions()
        return SessionListResponse(sessions=sessions, total=len(sessions))

    def delete_session(self, session_id: str) -> dict:
        ok = agent_service.delete_session(session_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        return {"deleted": session_id}


agent_controller = AgentController()
