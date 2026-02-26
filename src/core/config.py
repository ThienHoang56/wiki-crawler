import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Project Settings
    PROJECT_NAME = "Wikipedia RAG API"
    VERSION = "0.1.0"

    # PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/wiki_db")

    # Vector DB Config (Elasticsearch)
    ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
    ES_USER = os.getenv("ES_USER", "")
    ES_PASSWORD = os.getenv("ES_PASSWORD", "")
    INDEX_NAME = os.getenv("INDEX_NAME", "wiki_chunks")

    # LLM Config
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Embedding Config
    # QUAN TRỌNG: EMBEDDING_DIMS phải khớp với model đang dùng.
    # all-MiniLM-L6-v2 → 384 | all-mpnet-base-v2 → 768 | text-embedding-3-small → 1536
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIMS  = int(os.getenv("EMBEDDING_DIMS", "384"))
    CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP", "50"))

    # Search / RAG Params
    # Pool size trước khi RRF — càng lớn recall càng cao nhưng chậm hơn
    SEARCH_CANDIDATE_POOL = int(os.getenv("SEARCH_CANDIDATE_POOL", "20"))
    # Hằng số RRF (60 là chuẩn theo paper gốc, tăng → ưu tiên hơn các kết quả cuối)
    RRF_K             = int(os.getenv("RRF_K", "60"))
    # Số chunks truyền vào LLM khi answer_query
    RAG_TOP_K_CONTEXT = int(os.getenv("RAG_TOP_K_CONTEXT", "3"))
    # Số chunks hybrid retrieve trước khi rerank
    RAG_HYBRID_POOL   = int(os.getenv("RAG_HYBRID_POOL", "10"))

    # Crawler Config
    CRAWLER_USER_AGENT = os.getenv(
        "CRAWLER_USER_AGENT",
        "wiki-rag-bot/1.0 (https://github.com/your-repo; your@email.com)"
    )
    CRAWLER_RATE_LIMIT_SECONDS = float(os.getenv("CRAWLER_RATE_LIMIT_SECONDS", "1.0"))
    CRAWLER_CONCURRENCY        = int(os.getenv("CRAWLER_CONCURRENCY", "3"))
    CRAWLER_TIMEOUT_SECONDS    = float(os.getenv("CRAWLER_TIMEOUT_SECONDS", "15.0"))
    CRAWLER_RETRY_COUNT        = int(os.getenv("CRAWLER_RETRY_COUNT", "3"))
    CRAWLER_RETRY_BACKOFF      = float(os.getenv("CRAWLER_RETRY_BACKOFF", "2.0"))
    # Ngôn ngữ Wikipedia mặc định (en, vi, ja, zh, fr, de, ...)
    CRAWLER_WIKI_LANG          = os.getenv("CRAWLER_WIKI_LANG", "en")

    # Redis Cache Config (Optional)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

settings = Settings()
