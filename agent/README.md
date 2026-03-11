# WikiAgent — AI Agent backed by Wikipedia RAG

An AI Agent built with **LangGraph ReAct** that reasons over a set of tools connected to the Wikipedia RAG system. The agent can search the knowledge base, retrieve documents, crawl new Wikipedia topics, and generate cited answers.

---

## Completed Features

- **ReAct Loop**: Agent uses Thought → Action → Observation → Answer cycle (LangGraph `create_agent`)
- **Multi-tool reasoning**: Agent decides which tools to call based on the question
- **4 Tools** wrapping the Wikipedia RAG API:
  - `list_articles` — list all crawled Wikipedia articles in the knowledge base
  - `retrieve_docs` — hybrid search (BM25 + dense vector) without LLM generation
  - `rag_answer` — full RAG pipeline: search + LLM-synthesized answer with citations
  - `crawl_topic` — crawl new Wikipedia articles and index them on demand
- **Multi-provider LLM support**: works with Gemini, OpenAI, Anthropic, or Ollama (local)
- **Streaming output**: shows each step (tool calls and observations) in real time
- **Rate limit handling**: automatic retry with exponential backoff on 429 errors
- **CLI interface**: one-shot (`--question`) or interactive multi-turn mode

---

## Architecture

```
User (CLI)
    │
    ▼
WikiAgent (LangGraph ReAct)
    │  Thought → select tool
    ├──► list_articles   → GET  /api/v1/articles/
    ├──► retrieve_docs   → POST /api/v1/search/hybrid
    ├──► rag_answer      → POST /api/v1/search/ask
    └──► crawl_topic     → POST /api/v1/crawl/topic
                                │
                         FastAPI Server (:8001)
                         ├── PostgreSQL  (raw articles)
                         └── Elasticsearch  (vector index)
```

The agent calls the running RAG API over HTTP — fully decoupled, no direct database access.

---

## Prerequisites

| Requirement | How to satisfy |
|-------------|----------------|
| RAG API running at port 8001 | `poetry run uvicorn src.api.main:app --reload --port 8001` |
| Docker services (PostgreSQL + Elasticsearch) | `docker compose up -d` |
| Gemini API key OR Ollama | Set `GEMINI_API_KEY` in `.env` OR run Ollama locally |

---

## How to Run

All commands must be run from the **project root** (same directory as `pyproject.toml`):

```bash
# Step 1: Start infrastructure (if not already running)
docker compose up -d

# Step 2: Start the RAG API server (keep this running in a separate terminal)
poetry run uvicorn src.api.main:app --reload --port 8001

# Step 3 (in a new terminal): Run the agent
```

### Interactive mode (multi-turn conversation)
```bash
poetry run python agent/wiki_agent.py
```

### One-shot question
```bash
poetry run python agent/wiki_agent.py --question "What is machine learning?"
```

### Specify LLM model
```bash
# Use Gemini 2.5 Flash (recommended — more quota than lite)
poetry run python agent/wiki_agent.py --model gemini-2.5-flash --question "Explain transformers"

# Use a local Ollama model (requires Ollama running)
poetry run python agent/wiki_agent.py --model qwen2.5:1.5b --question "What is deep learning?"
```

### Full help
```bash
poetry run python agent/wiki_agent.py --help
```

---

## Demo Session

Below is an actual demo of the agent answering a multi-step question:

```
╔══════════════════════════════════════════╗
║         WikiAgent — RAG AI Assistant      ║
╚══════════════════════════════════════════╝

LLM: gemini-2.5-flash
Tools: rag_answer, retrieve_docs, crawl_topic, list_articles
API:  http://localhost:8001/api/v1

Question: What is deep learning? List me all topics in the knowledge base first.
────────────────────────────────────────────────────────────

[TOOL CALL]
  list_articles()

[OBSERVATION]
  Knowledge base contains 20 article(s):
    [1] Đạo hàm của các hàm lượng giác — vi.wikipedia.org/...
    [2] Vi phân — vi.wikipedia.org/...
    ...
    [18] Machine learning — en.wikipedia.org/wiki/Machine_learning
    [19] Natural language processing — en.wikipedia.org/...
    [20] Deep learning — en.wikipedia.org/wiki/Deep_learning

[TOOL CALL]
  rag_answer(question='What is deep learning?')

[OBSERVATION]
  [RAG Answer via gemini-2.5-flash]
  Deep learning refers to systems with a substantial credit assignment path (CAP)
  depth. The word "deep" refers to the number of layers through which data is
  transformed...

────────────────────────────────────────────────────────────

[FINAL ANSWER]
  The knowledge base contains 20 articles on topics including:
  - Mathematics (Vietnamese): Calculus derivatives, integrals, differentials
  - AI & ML: Artificial intelligence, Machine learning, Deep learning,
    Neural networks, Transformers, LLMs, NLP, CNNs, Reasoning models

  Deep learning = systems with deep credit assignment paths. The word "deep"
  refers to the number of layers. For feedforward nets: CAP depth = hidden
  layers + 1.

────────────────────────────────────────────────────────────
Tools used: list_articles, rag_answer
```

---

## Screenshots

See `screenshots/` folder:

| File | Description |
|------|-------------|
| `01_agent_simple_query.png` | Agent answering "What is machine learning?" — single tool call |
| `02_agent_multi_tool.png` | Agent listing knowledge base topics then answering about deep learning — multi-tool call |

---

## Configuration

The agent reads from the project root `.env` file. Key variables:

```env
# LLM for the agent reasoning (default: auto-detect from model name)
LLM_MODEL=gemini-flash-lite-latest

# API Keys
GEMINI_API_KEY=your_key_here

# Ollama (for local models, no API key needed)
OLLAMA_BASE_URL=http://localhost:11434

# RAG API base URL (default: http://localhost:8001/api/v1)
RAG_API_BASE_URL=http://localhost:8001/api/v1

# Override the model used inside RAG tool calls
TOOL_LLM_MODEL=gemini-2.5-flash
```

**Recommended model:** `gemini-2.5-flash` (more quota than `gemini-flash-lite-latest` on free tier).

---

## Known Limitations

1. **Gemini free tier rate limits**: The `gemini-flash-lite-latest` model has a limit of ~20 requests/day. Use `--model gemini-2.5-flash` for more quota, or set up Ollama for unlimited local inference.
2. **Sequential tool calls**: The current implementation does not run tools in parallel. Complex multi-step queries may be slow.
3. **No persistent memory**: Each agent session starts fresh. Conversation history is not saved between runs.
4. **Ollama not pre-started**: If using Ollama models, you must start Ollama manually before running the agent (`ollama serve` then `ollama pull qwen2.5:1.5b`).
5. **Index lag**: After `crawl_topic` crawls new articles, there is a ~10s delay before they appear in search results (background indexing job).
