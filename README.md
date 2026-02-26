# BOT GPT Backend

Production-oriented conversational backend with FastAPI, SQLite, FAISS, LangChain-powered Mistral integration, and clean architecture boundaries.

Detailed architecture guide: see `ARCHITECTURE.md`.

## Features

- Open chat mode and grounded RAG mode.
- Persistent users, conversations, messages, documents, and chunk metadata in SQLite.
- Vector search with FAISS (`index.faiss`) + JSON metadata (`chunk_id -> document_id`).
- Async LangChain (`langchain-mistralai`) chat + embedding integration with retries and timeout handling.
- Token-aware context management: last 10 messages passed as context (configurable) to avoid context-window limits.
- Structured error responses and JSON logging.
- Dockerized runtime and GitHub Actions CI.

## Architecture

```
bot-gpt/
├── app/
│   ├── main.py
│   ├── core/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── schemas/
│   ├── db/
│   └── vector_store/
├── tests/
├── Dockerfile
├── requirements.txt
└── .github/workflows/ci.yml
```

## Local Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

App runs at `http://127.0.0.1:8000`.

## Environment Variables

Prefix all variables with `BOTGPT_`:

- `BOTGPT_DATABASE_URL` (default `sqlite:///./bot_gpt.db`)
- `BOTGPT_MISTRAL_API_KEY`
- `BOTGPT_MISTRAL_BASE_URL`
- `BOTGPT_MISTRAL_CHAT_MODEL`
- `BOTGPT_MISTRAL_EMBEDDING_MODEL`

If `BOTGPT_MISTRAL_API_KEY` is missing, chat can still run in mock mode, but embedding-backed indexing/retrieval features require the key.

## Streamlit UI

```bash
streamlit run streamlit_app.py
```

The UI includes:

- user creation and listing
- conversation creation/list/deletion
- chat with message history per conversation
- document upload and chunk indexing flow
- direct file upload for RAG (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`)

Make sure the FastAPI backend is running (default: `http://127.0.0.1:8000`), create/select a user from the sidebar, then use that `user_id` for conversation and document flows.

## API Endpoints

- `POST /users`
- `GET /users?page=1&page_size=20`
- `POST /conversations`
- `GET /conversations?user_id=<uuid>&page=1&page_size=20`
- `GET /conversations/{id}`
- `POST /conversations/{id}/messages`
- `DELETE /conversations/{id}`
- `POST /documents`
- `POST /documents/upload-file` (multipart form-data: `user_id`, optional `title`, `file`)

## Error Contract

```json
{
  "error": {
    "code": "RAG_INDEX_MISSING",
    "message": "Vector index not initialized."
  }
}
```

## Tests

```bash
pytest -q
```

Coverage includes:

- conversation creation
- message ordering
- context token trimming
- FAISS retrieval logic

## Docker

```bash
docker build -t bot-gpt .
docker run -p 8000:8000 bot-gpt
```

## Scalability Notes

- SQLite is suitable for MVP; migrate to Postgres for production transactions and concurrency.
- Local FAISS is suitable for early scale; switch to managed vector DB (Pinecone/Weaviate) for distributed operations.
- Move LLM/embedding calls to async workers for queue-based throughput and resilience.
- Add background chunk processing to avoid blocking upload requests.
- Introduce read replicas and horizontal scaling behind a load balancer as traffic grows.
- **Conversation history summarization**: Summarize older messages so the LLM retains full context without exceeding token limits.
- **Dynamic prompt customization**: Let users configure system prompts, tone, and behaviour per conversation.
- **Improved RAG retrieval**: Hybrid search (keyword + semantic), cross-encoder re-ranking, and multi-hop retrieval.
- **Streaming responses**: Stream LLM output token-by-token for better UX.
- **Multi-model support**: Allow users to choose between different LLM providers or models.
