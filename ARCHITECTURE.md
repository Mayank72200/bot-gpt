# BOT GPT Architecture

## Overview
BOT GPT is a layered FastAPI application for user chat and retrieval-augmented generation (RAG):

1. API layer (`app/api/routes/*`) exposes users, conversations, and document ingestion.
2. Service layer (`app/services/*`) handles orchestration, prompt building, chunking, retrieval, and embeddings.
3. Relational persistence (SQLite via SQLAlchemy) stores users, conversations, messages, documents, and chunk metadata.
4. Vector persistence (LangChain FAISS local store) stores chunk text + vector embeddings for semantic retrieval.
5. LLM integration (`langchain-mistralai`) provides chat completion and embedding generation.

## Runtime Components
- Application entry: `app/main.py`
- Dependency wiring: `app/api/deps.py`
- DB engine/session: `app/db/session.py`
- SQLite migration helper: `app/db/sqlite_migrations.py`
- Vector manager: `app/vector_store/faiss_index.py`
- Core services:
  - `conversation_service.py`
  - `document_service.py`
  - `rag_service.py`
  - `llm_service.py`
  - `context_manager.py`

## Data Model
### SQLite tables
- `users`: identity and ownership boundary.
- `conversations`: chat mode (`OPEN` or `RAG`), summary, and lifecycle flags.
- `messages`: ordered user/assistant transcript with token estimates.
- `documents`: uploaded document metadata.
- `document_chunks`: chunk ordering metadata (`document_id`, `chunk_index`).

### Vector store
FAISS is persisted with LangChain local storage:
- `index.faiss`
- `index.pkl`

Stored vector records include:
- `page_content`: chunk text
- `metadata`: `user_id`, `document_id`, `chunk_id`, `chunk_index`
- `id`: chunk identifier

## Startup Lifecycle
On app startup (`app/main.py`):
1. Load settings and logger.
2. Apply SQLite schema creation + migration helper.
3. Initialize FAISS manager.
   - Load existing local FAISS store if present.
   - Otherwise start with an empty index and create on first insert.

## Document Ingestion Flow
Supported upload paths:
- `POST /documents` (raw text payload)
- `POST /documents/upload-file` (multipart form-data)

Supported file types in file upload:
- `.pdf` via `pypdf`
- `.docx` via `python-docx`
- `.txt`, `.md`, `.csv`, `.json` via text decoding

Ingestion steps:
1. Validate user exists.
2. Extract text (for file upload route) and validate non-empty content.
3. Create `documents` row.
4. Chunk content with `RecursiveCharacterTextSplitter`.
5. Create `document_chunks` rows (metadata only).
6. Generate embedding for each chunk through `EmbeddingService`.
7. Upsert embeddings + text + metadata into FAISS local store.
8. Commit relational transaction.

## Retrieval and Chat Flow
### OPEN mode
1. Load conversation and message history.
2. Persist new user message.
3. Keep only the last 10 messages as context (configurable via `max_history_messages`).
4. Call LLM and persist assistant response.

### RAG mode
Same as OPEN mode with retrieval step before generation:
1. Ensure user has documents.
2. Embed user query.
3. Run FAISS similarity search with `user_id` metadata filter.
4. Deduplicate and budget retrieved chunks.
5. Inject retrieved context into system prompt.
6. Keep only the last 10 messages as context (same cap as OPEN mode).
7. Generate assistant response and persist.

## Token Management
`ContextManager` controls token usage:
- **Hard message cap**: only the last `max_history_messages` messages (default **10**) are passed as conversation context in both OPEN and RAG modes, preventing token-limit and context-window overflow.
- Token estimate: `int(words * 1.3) + 1`
- Legacy budget trimmer retained for advanced use (`trim_messages_to_budget`)
- RAG chunk budget handled separately (`rag_context_max_tokens`)
- Response headroom reserved (`response_token_reserve`)

## Error Contract
Application errors inherit from `AppError` and return:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

Unhandled exceptions return `INTERNAL_SERVER_ERROR`.

## API Surface
- `POST /users`
- `GET /users`
- `POST /conversations`
- `GET /conversations`
- `GET /conversations/{id}`
- `POST /conversations/{id}/messages`
- `DELETE /conversations/{id}`
- `POST /documents`
- `POST /documents/upload-file`

Detailed API specs, data schema, and design rationale are in `TECHNICAL_SPEC.md`.

## Diagrams
### Component Diagram
```text
┌────────────────────┐
│    Streamlit UI    │
└─────────┬──────────┘
          │ HTTP
          v
┌────────────────────┐
│   FastAPI Routes   │
└─────────┬──────────┘
          │ delegates
          v
┌────────────────────┐
│   Service Layer    │
└───┬────────┬───────┘
    │        │
    │        └─────────────────────> LLM Service (LangChain + Mistral)
    │
    ├──────────────────────────────> SQLite (users, conversations, messages, docs)
    │
    └──────────────────────────────> FAISS Local Store (vectors + chunk text)
```

### File Upload + Indexing Sequence
```text
Client/UI
  |
  | POST /documents/upload-file (multipart: user_id, title?, file)
  v
Documents Route
  |
  | extract_text_from_uploaded_file(file)
  v
DocumentService
  |
  |-- validate user -------------------------> SQLite
  |-- create document + chunk metadata ------> SQLite
  |-- for each chunk: embed_text(chunk) -----> EmbeddingService
  |-- add_text_embeddings(...) --------------> FAISS Local Store
  |-- commit --------------------------------> SQLite
  |
  v
DocumentResponse (id, chunk_count)
```

### RAG Chat Sequence
```text
Client/UI
  |
  | POST /conversations/{id}/messages
  v
Conversations Route
  |
  v
ConversationService
  |
  |-- persist user message ------------------> SQLite
  |
  |-- if mode == RAG:
  |     retrieve_context(query)
  |       -> RagService
  |       -> EmbeddingService (query embedding)
  |       -> FAISS search (filter by user_id)
  |       -> return matching chunks
  |
  |-- keep last 10 messages only ------------> ContextManager.last_n_messages
  |-- build final prompt (system + history + retrieved context)
  |-- generate_chat(prompt) -----------------> LLMService
  |-- persist assistant message -------------> SQLite
  |
  v
[user_message, assistant_message]
```

## Future Improvements
- **Conversation history summarization**: Summarize older messages (beyond the last 10) so the LLM retains awareness of the full conversation without exceeding the context window.
- **Dynamic prompt customization**: Allow users to configure system prompts, tone, and behaviour per conversation to match their preferences.
- **Improved RAG context selection**: Re-rank retrieved chunks, use hybrid search (keyword + semantic), and cross-encoder scoring for higher answer quality.
- **Multi-model support**: Let users choose between different LLM providers or models per conversation.
- **Streaming responses**: Stream LLM output token-by-token for better perceived latency.
- **Feedback loop**: Collect user thumbs-up/down to fine-tune retrieval relevance and prompt quality over time.

