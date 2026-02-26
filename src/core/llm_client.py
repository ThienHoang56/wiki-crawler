from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.config import settings

class LLMClient:
    _llm: ChatOpenAI = None

    @property
    def llm(self) -> ChatOpenAI:
        """Lazy init: chỉ khởi tạo kết nối LLM khi lần đầu được gọi."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.0,
            )
        return self._llm

    def generate_response(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]
        return self.llm.invoke(messages).content

llm_client = LLMClient()
