from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = Field(..., description="Vai trò: 'user' hoặc 'assistant'")
    content: str = Field(..., description="Nội dung tin nhắn")


class AgentChatRequest(BaseModel):
    message: str = Field(..., description="Câu hỏi hoặc yêu cầu gửi đến agent")
    session_id: Optional[str] = Field(
        default=None,
        description="ID phiên trò chuyện để duy trì lịch sử. Để trống = tạo session mới.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Override LLM model (e.g. 'llama-3.1-8b-instant', 'gemini-2.5-flash')",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is deep learning and how does it differ from machine learning?",
                "session_id": "my-session-1",
                "model": None,
            }
        }


class ToolCallLog(BaseModel):
    tool: str = Field(..., description="Tên tool được gọi")
    args: dict = Field(default_factory=dict, description="Tham số truyền vào tool")
    result_preview: str = Field(..., description="100 ký tự đầu của kết quả tool")


class AgentChatResponse(BaseModel):
    session_id: str = Field(..., description="ID phiên (dùng lại cho các tin nhắn tiếp theo)")
    message: str = Field(..., description="Câu hỏi của người dùng")
    answer: str = Field(..., description="Câu trả lời cuối cùng từ agent")
    tools_used: list[str] = Field(default_factory=list, description="Danh sách tools đã gọi")
    tool_calls: list[ToolCallLog] = Field(default_factory=list, description="Chi tiết từng tool call")
    model: str = Field(..., description="Model LLM đã sử dụng")
    turn: int = Field(..., description="Số lượt hội thoại trong session")


class SessionInfo(BaseModel):
    session_id: str
    turn_count: int
    history: list[ChatMessage]


class SessionListResponse(BaseModel):
    sessions: list[str]
    total: int
