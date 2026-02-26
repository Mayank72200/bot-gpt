# BOT GPT Technical Specification

This document combines API specifications, data schema, and design rationale.

## 1) API Specifications

Base behavior:
- Content type: `application/json` unless explicitly multipart.
- Error format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

### Users

#### POST /users
Create user or return existing user for email.

Request body:
```json
{
  "email": "user@example.com",
  "user_id": "optional-uuid"
}
```

Response 200:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "created_at": "2026-02-26T12:00:00"
}
```

#### GET /users?page=1&page_size=20
List users with pagination.

Response 200:
```json
[
  {
    "id": "uuid",
    "email": "user@example.com",
    "created_at": "2026-02-26T12:00:00"
  }
]
```

### Conversations

#### POST /conversations
Create conversation for a user.

Request body:
```json
{
  "user_id": "uuid",
  "mode": "OPEN"
}
```

Notes:
- `mode` supports `OPEN` and `RAG`.

Response 200:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "mode": "OPEN",
  "summary": null,
  "is_active": true,
  "created_at": "2026-02-26T12:00:00",
  "updated_at": "2026-02-26T12:00:00"
}
```

#### GET /conversations?user_id=<uuid>&page=1&page_size=20
List active conversations for a user.

Response 200:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "mode": "RAG",
    "summary": null,
    "is_active": true,
    "created_at": "2026-02-26T12:00:00",
    "updated_at": "2026-02-26T12:00:00"
  }
]
```

#### GET /conversations/{id}
Get conversation and ordered messages.

Response 200:
```json
{
  "conversation": {
    "id": "uuid",
    "user_id": "uuid",
    "mode": "OPEN",
    "summary": null,
    "is_active": true,
    "created_at": "2026-02-26T12:00:00",
    "updated_at": "2026-02-26T12:00:00"
  },
  "messages": [
    {
      "id": 1,
      "conversation_id": "uuid",
      "role": "user",
      "content": "Hello",
      "token_count": 2,
      "sequence_number": 1,
      "created_at": "2026-02-26T12:00:05"
    }
  ]
}
```

#### POST /conversations/{id}/messages
Append a user message and generate assistant response.

Request body:
```json
{
  "content": "User question"
}
```

Response 200:
```json
[
  {
    "id": 10,
    "conversation_id": "uuid",
    "role": "user",
    "content": "User question",
    "token_count": 4,
    "sequence_number": 7,
    "created_at": "2026-02-26T12:10:00"
  },
  {
    "id": 11,
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "Assistant answer",
    "token_count": 24,
    "sequence_number": 8,
    "created_at": "2026-02-26T12:10:01"
  }
]
```

#### DELETE /conversations/{id}
Soft-delete conversation (`is_active=false`).

Response 200:
```json
{
  "status": "deleted"
}
```

### Documents

#### POST /documents
Upload raw text for indexing.

Request body:
```json
{
  "user_id": "uuid",
  "title": "Policy Document",
  "text": "Full document content..."
}
```

Response 200:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Policy Document",
  "created_at": "2026-02-26T12:20:00",
  "chunk_count": 18
}
```

#### POST /documents/upload-file
Upload file for extraction + indexing.

Content type:
- `multipart/form-data`

Fields:
- `user_id` (required)
- `title` (optional; defaults to filename stem)
- `file` (required)

Supported extensions:
- `.pdf`
- `.docx`
- `.txt`
- `.md`
- `.csv`
- `.json`

Response 200:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "filename-or-custom-title",
  "created_at": "2026-02-26T12:22:00",
  "chunk_count": 10
}
```

## 2) Data Schema

## SQLite Entities

### users
- `id` (string UUID, PK)
- `email` (string, unique)
- `created_at` (datetime)

### conversations
- `id` (string UUID, PK)
- `user_id` (FK -> users.id)
- `mode` (`OPEN` | `RAG`)
- `summary` (nullable string)
- `is_active` (boolean)
- `created_at` (datetime)
- `updated_at` (datetime)

### messages
- `id` (int, PK autoincrement)
- `conversation_id` (FK -> conversations.id)
- `role` (`user` | `assistant` | `system`)
- `content` (text)
- `token_count` (int)
- `sequence_number` (int)
- `created_at` (datetime)

### documents
- `id` (string UUID, PK)
- `user_id` (FK -> users.id)
- `title` (string)
- `created_at` (datetime)

### document_chunks
- `id` (int, PK autoincrement)
- `document_id` (FK -> documents.id)
- `chunk_index` (int)

Notes:
- Chunk text is not stored in SQLite.
- SQLite stores chunk metadata and relational ownership.

## FAISS Local Store Schema

Persistence files:
- `data/index.faiss`
- `data/index.pkl`

Per-vector payload:
- `id`: chunk id
- `page_content`: chunk text
- `metadata.user_id`
- `metadata.document_id`
- `metadata.chunk_id`
- `metadata.chunk_index`

## 3) Design Rationale

### Why split relational and vector storage
- SQLite handles transactional entities well (users, conversations, lifecycle state).
- FAISS handles fast semantic nearest-neighbor retrieval for chunk text.
- Separation keeps relational schema simple and retrieval performant.

### Why metadata-only chunk rows in SQL
- SQL stores deterministic ownership and ordering.
- Vector store stores payload needed for retrieval context.
- This prevents duplicating large chunk text blobs across two stores.

### Why file extraction in service layer
- Route remains transport-focused.
- DocumentService centralizes extraction, validation, chunking, embedding, and indexing.
- Same ingestion pipeline is reused for raw text and uploaded files.

### Why two ingestion endpoints
- `POST /documents` is simple for integrations and tests.
- `POST /documents/upload-file` is user-friendly for UI uploads.
- Both converge to one indexing flow in service code.

### Why token budget controls
- Hard cap of last 10 messages prevents context-window overflow in both OPEN and RAG modes.
- RAG chunk budget is separate and bounded.
- Older conversation history is preserved in the database and can be summarized in future iterations.
- Configurable via `BOTGPT_MAX_HISTORY_MESSAGES` environment variable.

### Why RAG retrieval is user-scoped
- Metadata filter uses `user_id` so one user never retrieves another user’s chunks.
- This is the minimum isolation boundary before introducing full auth layers.

### Why local FAISS now
- Good fit for MVP/local deployments with low operational overhead.
- Can be replaced by managed vector infrastructure as scale increases.
