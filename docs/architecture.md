# System Architecture Document

## Project Name: The Lenny Growth Assistant
**Document Version:** 1.0.0  
**Stack:** React (Vite) + FastAPI + PostgreSQL + Ollama / Anthropic Claude  
**Status:** Completed & Production Verified  

---

## 1. High-Level Architectural Overview

The Lenny Growth Assistant is built as a decoupled, service-oriented web application designed for high-signal retrieval, reliable autonomous skills, and secure visual artifact rendering.

```mermaid
graph TB
    subgraph Client ["Client Layer (Browser)"]
        UI["React 18 SPA (Vite)"]
        Chat["ChatArea & Message Stream"]
        Studio["ArtifactPanel (Sandboxed Iframe)"]
        UI --> Chat
        UI --> Studio
    end

    subgraph Gateway ["Nginx / Reverse Proxy (Docker :5173 / :80)"]
        NGX["Nginx Web Server"]
    end

    subgraph Backend ["Application Layer (FastAPI :8000)"]
        API["FastAPI REST Router (/api)"]
        HealthAPI["Health & Diagnostic Endpoints (/health)"]
        Agent["RAGAgent Orchestrator"]
        EssaySkill["Ship30For30Skill (~1,250 words)"]
        ArtifactSkill["ArtifactGenerationSkill"]
        Sanitizer["HTML Sanitizer Engine"]
        Retriever["RetrievalService (NumPy Cosine)"]
        
        API --> Agent
        Agent --> Retriever
        Agent --> EssaySkill
        Agent --> ArtifactSkill
        ArtifactSkill --> Sanitizer
    end

    subgraph Inference ["LLM Inference Providers"]
        OllamaProv["OllamaLLMProvider (llama3.2:3b)"]
        ClaudeProv["AnthropicLLMProvider / ClaudeAgentProvider"]
        MockProv["MockLLMProvider (Offline Tests)"]
    end

    subgraph Storage ["Persistence Layer (PostgreSQL :5432 / :5433)"]
        DB[(PostgreSQL 15 Database: lenny_growth_db)]
        T_Conv[conversations]
        T_Msg[messages]
        T_Art[artifacts]
        T_Doc[knowledge_documents]
        T_Chunk[knowledge_chunks]
        
        DB --- T_Conv
        DB --- T_Msg
        DB --- T_Art
        DB --- T_Doc
        DB --- T_Chunk
    end

    UI -->|HTTP / CORS| API
    NGX -->|Static Assets| UI
    Agent --> OllamaProv
    Agent --> ClaudeProv
    Agent --> MockProv
    Retriever -->|Vector Query| T_Chunk
    API -->|SQLAlchemy ORM| DB
```

---

## 2. Component Responsibilities

### 2.1. Frontend (`frontend/src/`)
- **Framework**: React 18, Vite 5.
- **Components**:
  - `Header.jsx`: Branding, dynamic server status (`Online`), active LLM provider pill (`ollama`, `anthropic`), model name (`llama3.2:3b`).
  - `Sidebar.jsx`: Conversation list, "+ New Chat", conversation deletion with cascade effect.
  - `ChatArea.jsx`: Welcome hero with 4 prompt cards, message feed, citation accordion with clickable YouTube deep links, auto-expanding textarea input.
  - `ArtifactPanel.jsx`: Slide-out studio panel with multi-artifact switcher, `Page Preview` vs `Raw Code` tabs, sandboxed `<iframe>`, copy-to-clipboard, and `.md` / `.html` export.
- **Service Layer (`services/api.js`)**: Clean Axios/Fetch API wrapper handling error recovery, retries, and data transformations.

### 2.2. Backend API (`backend/app/api/`)
- **Framework**: FastAPI (Python 3.10+ / 3.11).
- **Routers**:
  - `conversations.py`: CRUD operations for conversations and message dispatching.
  - `artifacts.py`: CRUD endpoints for artifacts linked to conversations.
  - `health.py`: Liveness (`/health`), DB readiness (`/health/db`), and LLM diagnostics (`/health/llm`).

### 2.3. Agent & Autonomous Skills (`backend/app/agents/` & `backend/app/skills/`)
- **`RAGAgent` (`rag_agent.py`)**: Central agent orchestrator. Ingests user input and chat history, queries `RetrievalService`, constructs untrusted context prompts with anti-injection guards, selects the configured LLM provider, extracts structured source citations, and routes deliverable prompts to specialized skills.
- **`Ship30For30Skill` (`skills/ship_30_for_30.py`)**: Intent-activated skill for ~1,250-word atomic growth essays. Performs topic extraction, injects retrieved podcast wisdom, enforces structural headings, executes single-pass controlled continuation if draft is under 700 words, and reports actual whitespace-delimited word counts.
- **`ArtifactGenerationSkill` (`skills/artifact_generation.py`)**: Synthesizes standalone Markdown guides or HTML/CSS landing pages/widgets, sanitizes them, and records them in PostgreSQL.

### 2.4. Knowledge Base & Vector Retrieval (`backend/app/knowledge_base/`)
- **`loader.py`**: Multi-format loader (`.md`, `.txt`, `.json`, `.pdf`) with canonical path validation preventing path traversal attacks.
- **`normalizer.py`**: Whitespace standardization and speaker turn normalization (`Speaker (HH:MM:SS):`).
- **`chunker.py`**: Configurable sliding window chunker (1,000 characters, 200 overlap).
- **`metadata.py`**: YAML frontmatter parsing (`title`, `guest`, `youtube_url`, `publication_date`) and SHA-256 content hashing.
- **`embeddings.py`**: Embeddings engine supporting `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dims, local cache), lightweight `hash`, local `ollama`, and cloud `openai`.
- **`vector_store.py`**: Storage and retrieval in PostgreSQL with JSONB vector arrays and NumPy cosine similarity.
- **`retrieval.py`**: `RetrievalService` providing clean query search, top-k ranking, guest/episode filtering, and keyword boosting.
- **`ingest.py`**: Repeatable, idempotent CLI ingestion pipeline with progress reporting and duplicate skipping.

---

## 3. Request & Response Execution Flows

### 3.1. Conversational Query & RAG Retrieval Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant API as FastAPI (/api/conversations/{id}/messages)
    participant DB as PostgreSQL (lenny_growth_db)
    participant Agent as RAGAgent
    participant RAG as RetrievalService
    participant LLM as Active LLM Provider (Ollama / Claude)

    User->>API: POST /api/conversations/{id}/messages {"content": "..."}
    Note over API,DB: Reliability: Commit user message first
    API->>DB: INSERT INTO messages (role="user", content="...")
    
    API->>Agent: process_query(conversation_id, prompt, history)
    Agent->>RAG: retrieve_context(query, top_k=5)
    RAG->>DB: SELECT chunk_index, content, metadata_json, embedding FROM knowledge_chunks
    DB-->>RAG: Return candidate chunks
    RAG->>RAG: Compute cosine similarity + keyword boost
    RAG-->>Agent: Return top-k matching passages
    
    Agent->>Agent: Construct system prompt (<retrieved_context>)
    Agent->>LLM: generate_chat_response(messages, system_prompt)
    
    alt Inference Successful
        LLM-->>Agent: Generated text response
        Agent->>Agent: Map retrieved chunks to SourceCitation objects
        Agent-->>API: Response payload (content, citations, metadata)
        API->>DB: INSERT INTO messages (role="assistant", metadata_json={citations: [...]})
        API-->>User: HTTP 201 Created (Message + Citations)
    else Inference Failed / Timeout
        LLM-->>Agent: ConnectionError / Timeout
        Agent-->>API: Fallback error payload
        API->>DB: INSERT INTO messages (role="assistant", status="error")
        API-->>User: HTTP 201 Created (Error banner with Retry button)
    end
```

### 3.2. Ship 30 for 30 Essay Generation Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant API as FastAPI
    participant Skill as Ship30For30Skill
    participant RAG as RetrievalService
    participant LLM as Active LLM
    participant DB as PostgreSQL

    User->>API: "Write a Ship 30 for 30 essay on customer retention"
    API->>Skill: activate(prompt)
    Skill->>Skill: Extract topic: "customer retention"
    Skill->>RAG: retrieve_context("customer retention", top_k=5)
    RAG-->>Skill: Return podcast excerpts (e.g. Elena Verna, Lauryn Isford)
    
    Skill->>LLM: Generate initial draft (~1,250 words target)
    LLM-->>Skill: Return draft
    Skill->>Skill: Calculate whitespace-delimited word count
    
    opt Draft is < 700 words
        Skill->>LLM: Single-pass controlled continuation prompt
        LLM-->>Skill: Expansion section
        Skill->>Skill: Stitch expansion before conclusion
    end
    
    Skill->>Skill: Append transparent word count notice
    Skill->>DB: INSERT INTO artifacts (type="markdown", title="...", content="...")
    Skill-->>API: Return essay text + artifact reference
    API-->>User: Render essay in chat + open ArtifactPanel automatically
```

---

## 4. API Specification

| Endpoint | Method | Request Body | Response Status | Purpose |
|---|---|---|---|---|
| `/` | `GET` | None | `200 OK` | Root metadata probe and Swagger link |
| `/health` | `GET` | None | `200 OK` | Core service readiness probe |
| `/health/db` | `GET` | None | `200 OK` / `503` | Database connectivity probe (`SELECT 1`) |
| `/health/llm` | `GET` | None | `200 OK` | Diagnostic probe for Ollama / Anthropic status |
| `/api/conversations` | `POST` | `{"title": "..."}` | `201 Created` | Create a new conversation |
| `/api/conversations` | `GET` | None | `200 OK` | List conversations (sorted by `updated_at` desc) |
| `/api/conversations/{id}` | `GET` | None | `200 OK` | Fetch conversation details & full message history |
| `/api/conversations/{id}` | `DELETE` | None | `200 OK` | Delete conversation and cascade delete all messages/artifacts |
| `/api/conversations/{id}/messages` | `POST` | `{"content": "..."}` | `201 Created` | Send message, invoke RAG/Agent, persist assistant reply |
| `/api/conversations/{id}/artifacts`| `POST` | `{"title": "...", "type": "...", "content": "..."}` | `201 Created` | Create and link artifact to conversation |
| `/api/conversations/{id}/artifacts`| `GET` | None | `200 OK` | List all artifacts for a conversation |
| `/api/artifacts/{id}` | `GET` | None | `200 OK` | Retrieve single artifact by ID |
| `/api/artifacts/{id}` | `PUT` | `{"title": "...", "content": "..."}` | `200 OK` | Update artifact content/metadata |
| `/api/artifacts/{id}` | `DELETE` | None | `200 OK` | Delete single artifact by ID |

---

## 5. Database Schema & Relational Models

The database uses PostgreSQL 15 (`lenny_growth_db`). All tables are managed via SQLAlchemy 2.0 ORM models in `backend/app/models/`.

```mermaid
erDiagram
    conversations ||--o{ messages : "has (CASCADE)"
    conversations ||--o{ artifacts : "has (CASCADE)"
    knowledge_documents ||--o{ knowledge_chunks : "contains (CASCADE)"

    conversations {
        string id PK "UUID-4 (36 chars)"
        string title "Max 255 chars"
        timestamp created_at "UTC timezone"
        timestamp updated_at "UTC timezone"
    }

    messages {
        string id PK "UUID-4 (36 chars)"
        string conversation_id FK "References conversations.id"
        string role "user | assistant"
        text content "Max 50,000 chars"
        jsonb metadata_json "citations, provider, model, status"
        timestamp created_at "UTC timezone"
    }

    artifacts {
        string id PK "UUID-4 (36 chars)"
        string conversation_id FK "References conversations.id"
        string title "Max 255 chars"
        string type "markdown | html"
        text content "Max 500,000 chars (sanitized)"
        jsonb metadata_json "version, word_count, topic"
        timestamp created_at "UTC timezone"
        timestamp updated_at "UTC timezone"
    }

    knowledge_documents {
        uuid id PK "UUID"
        string title "Max 255 chars"
        string source_type "podcast | newsletter | document"
        string author "Guest speaker"
        string episode_title "Podcast episode name"
        string publication_date "YYYY-MM-DD"
        text source_url "Official recording URL"
        text file_path "Relative path"
        string file_hash UK "SHA-256 hash"
        integer chunk_count "Total segments"
        timestamp created_at "UTC timezone"
    }

    knowledge_chunks {
        uuid id PK "UUID"
        uuid document_id FK "References knowledge_documents.id"
        integer chunk_index "0-indexed sequence"
        text content "Chunk body (~1,000 chars)"
        jsonb embedding "384-dim vector array"
        integer token_count "Estimated tokens"
        jsonb metadata_json "Guest, timestamp, deep-link URL"
        timestamp created_at "UTC timezone"
    }
```

---

## 6. LLM Provider Architecture & Selection Mechanics

All model implementations adhere to the abstract interface `BaseLLMProvider` (`backend/app/agents/base.py`):

```python
class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: pass

    @property
    @abstractmethod
    def model_name(self) -> str: pass

    @abstractmethod
    def generate_chat_response(self, messages, system_prompt=None, temperature=0.7) -> str: pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]: pass
```

### Supported Providers

1. **`OllamaLLMProvider`** (`app/agents/providers/ollama_provider.py`):
   - Targets local daemon: `http://localhost:11434` (or `http://host.docker.internal:11434` in Docker).
   - Default model: `llama3.2:3b`.
   - Timeout: 60.0s.
   - Bounded retries for transient connection hiccups.
2. **`AnthropicLLMProvider`** (`app/agents/providers/anthropic_provider.py`):
   - Targets cloud Claude API via official `anthropic` SDK.
   - Model: `claude-3-5-sonnet-20241022`.
   - Requires `ANTHROPIC_API_KEY`.
   - Handles 401 auth errors, 429 rate limits, and network dropouts.
3. **`ClaudeAgentProvider`** (`app/agents/providers/claude_agent_provider.py`):
   - Cloud agent framework integration satisfying assignment SDK requirements.
4. **`MockLLMProvider`** (`app/agents/providers/mock_provider.py`):
   - Deterministic, zero-network mock provider used for the 98 hermetic automated tests.

---

## 7. Docker Orchestration & Networking

The system defines 3 containerized services in [`docker-compose.yml`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/docker-compose.yml):

```mermaid
graph LR
    subgraph Host ["Host Machine (Windows / macOS / Linux)"]
        Browser["User Browser (:5173)"]
        HostOllama["Host Ollama (:11434)"]
    end

    subgraph ComposeNet ["Docker Bridge Network (lenny_growth_network)"]
        FrontendC["lenny_frontend (Nginx :5173)"]
        BackendC["lenny_backend (FastAPI :8000)"]
        PostgresC["lenny_postgres (Postgres 15 :5432)"]
    end

    Browser -->|Port 5173| FrontendC
    Browser -->|Port 8000| BackendC
    FrontendC -->|Reverse Proxy /api| BackendC
    BackendC -->|lenny_postgres:5432| PostgresC
    BackendC -->|host.docker.internal:11434| HostOllama
    PostgresC -->|Named Volume| Vol[(lenny_postgres_data)]
```

### Networking & Security Hardening
- **Port Mapping**: Container PostgreSQL 5432 maps to host **5433** (`POSTGRES_HOST_PORT`) to eliminate collisions with any local PostgreSQL instance already running on port 5432.
- **Host Gateway**: Backend container uses `host.docker.internal:11434` with Compose `extra_hosts: ["host.docker.internal:host-gateway"]`, providing seamless access to host Ollama across Windows, Mac, and Linux.
- **Non-Root Execution**: Backend Dockerfile creates and executes as an unprivileged user (`appuser`, UID 1000).
- **Readiness Probes**: Backend container employs `wait_for_db()` polling with exponential backoff to eliminate startup race conditions with PostgreSQL.
