"""
Multi-provider LLM Client.

Tự động chọn provider dựa theo model name hoặc LLM_PROVIDER trong config:
  openai    → gpt-4o, gpt-4o-mini, gpt-4-turbo, o1-mini, o3-mini, ...
  gemini    → gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash, ...
  anthropic → claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus, ...
  groq      → llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768, gemma2-9b-it
              Free tier: 14,400 req/day, 30 RPM. Key: https://console.groq.com
  ollama    → llama3.2, mistral, qwen2.5, phi4, deepseek-r1, ... (local, no API key)
"""
from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from src.core.config import settings


_GROQ_MODELS = {
    "llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant",
    "llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it",
    "llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview",
    "llama-guard-3-8b", "llama3-groq-70b-8192-tool-use-preview",
}


def _detect_provider(model: str) -> str:
    """Tự detect provider từ tên model nếu LLM_PROVIDER không được set."""
    m = model.lower()
    if any(m.startswith(p) for p in ("gpt-", "o1-", "o3-", "o4-", "chatgpt")):
        return "openai"
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("claude"):
        return "anthropic"
    # Groq models: nếu GROQ_API_KEY có sẵn và model khớp → dùng Groq
    if m in _GROQ_MODELS or m.startswith(("llama3-", "llama-3", "mixtral-", "gemma2-")):
        if settings.GROQ_API_KEY:
            return "groq"
    # Còn lại coi là Ollama (local models)
    return "ollama"


def _build_llm(model: str, temperature: float, max_tokens: int) -> BaseChatModel:
    provider = settings.LLM_PROVIDER or _detect_provider(model)

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY chưa được set trong .env")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY chưa được set trong .env")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Chạy: pip install langchain-google-genai")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY chưa được set trong .env")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("Chạy: pip install langchain-anthropic")
        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY chưa được set trong .env. "
                "Lấy key miễn phí tại https://console.groq.com"
            )
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError("Chạy: poetry add langchain-groq")
        return ChatGroq(
            model=model,
            api_key=settings.GROQ_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError("Chạy: pip install langchain-ollama")
        return ChatOllama(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
            num_predict=max_tokens,
        )

    raise ValueError(
        f"Provider không hỗ trợ: '{provider}'. "
        "Chọn: openai | gemini | anthropic | groq | ollama"
    )


class LLMClient:
    """
    Lazy-init multi-provider LLM client.
    Cache instance theo (model, temperature, max_tokens) để tránh init lại mỗi request.
    """
    _cache: dict[tuple, BaseChatModel] = {}

    def _get_llm(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        m = model or settings.LLM_MODEL
        t = temperature if temperature is not None else settings.LLM_TEMPERATURE
        n = max_tokens or settings.LLM_MAX_TOKENS
        key = (m, t, n)
        if key not in self._cache:
            self._cache[key] = _build_llm(m, t, n)
        return self._cache[key]

    def generate_response(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Gọi LLM và trả về dict gồm answer + metadata.
        Tự retry khi gặp rate limit (429), raise LLMRateLimitError để caller xử lý.
        """
        import time

        llm = self._get_llm(model, temperature, max_tokens)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]
        provider = settings.LLM_PROVIDER or _detect_provider(model or settings.LLM_MODEL)
        used_model = model or settings.LLM_MODEL

        last_exc = None
        for attempt in range(3):
            try:
                response = llm.invoke(messages)

                usage = {}
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    u = response.usage_metadata
                    usage = {
                        "input_tokens":  getattr(u, "input_tokens", None),
                        "output_tokens": getattr(u, "output_tokens", None),
                    }

                return {
                    "answer":   response.content,
                    "model":    used_model,
                    "provider": provider,
                    "usage":    usage,
                }

            except Exception as exc:
                err_str = str(exc)
                # Rate limit → retry với backoff
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate" in err_str.lower():
                    last_exc = exc
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    if attempt < 2:
                        time.sleep(wait)
                        continue
                    # Hết retry → raise rõ ràng để trả 429 thay vì 500
                    raise LLMRateLimitError(
                        f"Gemini rate limit exceeded. Retry sau vài giây. ({err_str[:120]})"
                    ) from exc
                raise  # Lỗi khác → raise thẳng


class LLMRateLimitError(Exception):
    """Raise khi LLM provider trả 429 sau tất cả retries."""
    pass

    @property
    def available_providers(self) -> list[str]:
        providers = []
        if settings.OPENAI_API_KEY:    providers.append("openai")
        if settings.GEMINI_API_KEY:    providers.append("gemini")
        if settings.ANTHROPIC_API_KEY: providers.append("anthropic")
        providers.append("ollama")  # always available nếu Ollama đang chạy
        return providers


llm_client = LLMClient()
