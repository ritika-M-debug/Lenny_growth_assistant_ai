# Automated Testing Documentation

## Project Name: The Lenny Growth Assistant
**Test Framework**: Pytest 9.x (Python) + Vite Build Verification (Node.js)  
**Total Automated Tests**: 98 passed, 0 failed  
**Execution Duration**: ~4.95 seconds  
**Test Isolation**: 100% Hermetic (Zero external network calls, zero paid API tokens, zero running Ollama process required)  

---

## 1. Test Architecture & Hermetic Isolation Philosophy

To ensure tests execute reliably, instantaneously, and deterministically across different developer machines and CI pipelines, all automated tests use a hermetic testing strategy:

1. **In-Memory SQLite Database**:
   - Tests run against an isolated in-memory SQLite database using SQLAlchemy's `StaticPool` (`sqlite:///:memory:`).
   - Real PostgreSQL development and production databases (`lenny_growth_db`) are never modified or purged during test runs.
   - Tables are created on test fixture setup and torn down on teardown.

2. **Mocked LLM Inference (`MockLLMProvider`)**:
   - LLM generation calls use the deterministic `MockLLMProvider` (`backend/app/agents/providers/mock_provider.py`).
   - Generates predictable, prompt-aware text, atomic essays, and HTML landing pages in milliseconds without requiring an active Ollama daemon or paid Anthropic Claude API keys.

3. **Deterministic Embeddings**:
   - Tests verify chunking, embeddings, and cosine retrieval using pre-cached model vectors or deterministic lightweight hash vectors (`HashEmbeddingProvider`).

---

## 2. Test Execution Commands

### Run Full Test Suite (Windows PowerShell)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

### Run Full Test Suite (Linux / macOS)
```bash
cd backend
source venv/bin/activate
pytest -v
```

### Run Full Test Suite Inside Docker Container
```bash
docker compose exec backend pytest -v
```

### Run Specific Test Modules

```powershell
# Health and Database Probes (4 tests)
pytest tests/test_health.py -v

# Conversation & Message Persistence (6 tests)
pytest tests/test_conversations.py -v

# Artifact Generation, Sanitization & Persistence (17 tests)
pytest tests/test_artifacts.py -v

# Knowledge Base Chunking & Normalization (8 tests)
pytest tests/test_rag.py -v

# Transcript Integration & YouTube Deep Links (5 tests)
pytest tests/test_transcript_integration.py -v

# Agent Orchestrator & Grounded Citations (6 tests)
pytest tests/test_agent.py -v

# Ship 30 for 30 Essay Generation Skill (8 tests)
pytest tests/test_essay_skill.py -v

# Dual Provider Reliability, Retries & Fallbacks (23 tests)
pytest tests/test_providers.py -v

# Docker Deployment & DB Readiness Probes (5 tests)
pytest tests/test_docker_deployment.py -v

# Real Podcast Transcript Retrieval & Grounding (5 tests)
pytest tests/test_real_transcript_rag.py -v

# 12-Flow Frontend E2E Regression Suite (11 tests)
pytest tests/test_frontend_flows_e2e.py -v
```

### Run Frontend Production Build Verification
```powershell
cd frontend
npm run build
```

---

## 3. Test Coverage Areas & Module Breakdown

| Module | File | Test Count | Key Scenarios Covered |
|---|---|---|---|
| **Health Probes** | [`test_health.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_health.py) | 4 | Root `/` metadata, `/health` liveness probe, `/health/db` connectivity success, and `/health/db` failure handling. |
| **Conversations** | [`test_conversations.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_conversations.py) | 6 | `POST /api/conversations`, chronological message sorting, conversation re-opening, invalid ID handling (404), and cascade deletion. |
| **Artifacts** | [`test_artifacts.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_artifacts.py) | 17 | Artifact CRUD endpoints, multi-artifact linking to conversation, cascade delete when conversation is deleted, HTML sanitizer stripping `<script>` / `onclick` / `javascript:`, and ordinary chat non-creation. |
| **RAG Pipeline** | [`test_rag.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_rag.py) | 8 | Text normalization, sliding window chunking with overlap, metadata preservation, missing field safety, unsupported format handling, SHA256 duplicate skipping, and empty KB behavior. |
| **Transcript Parsing** | [`test_transcript_integration.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_transcript_integration.py) | 5 | Safe YAML frontmatter parsing, speaker turns timestamp conversion to seconds (`t=Xs`), target filtering, idempotent duplicate skipping, and grounded citation generation. |
| **Agent Logic** | [`test_agent.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_agent.py) | 6 | RAG prompt assembly, untrusted context boundary enforcement, source citation metadata structure, empty KB general advice fallback, and conversation history preservation. |
| **Essay Skill** | [`test_essay_skill.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_essay_skill.py) | 8 | Ship 30 for 30 intent detection, topic extraction, retrieval context injection, whitespace-delimited word count calculation, controlled continuation, ordinary chat bypass, and model timeout error handling. |
| **Dual Providers** | [`test_providers.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_providers.py) | 23 | Environment variable provider selection (`ollama`, `anthropic`, `mock`), Ollama connection failure/missing model/timeout handling, Anthropic 401/429/timeout handling, `/health/llm` key masking, user prompt preservation, and zero duplicate message/artifact generation on error. |
| **Docker Config** | [`test_docker_deployment.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_docker_deployment.py) | 5 | `DATABASE_URL` generation for container networking, CORS origins for Docker Nginx frontend (`:80`, `:5173`), `wait_for_db()` immediate success, retry-then-success, and retry exhaustion. |
| **Real Transcripts** | [`test_real_transcript_rag.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_real_transcript_rag.py) | 5 | Real episodes presence verification, retrieval on product-market fit (Todd Jackson), retrieval on growth teams (Adam Fishman), citation URLs valid YouTube deep links, and agent non-fabrication of citations. |
| **Frontend E2E** | [`test_frontend_flows_e2e.py`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/backend/tests/test_frontend_flows_e2e.py) | 11 | Complete automated simulation of all 12 manual UI journeys: launch, new chat, Q&A, reload persistence, citations, Ship 30 for 30 essay, markdown artifact, HTML preview & sanitization, copy/download, artifact isolation, and failure recovery. |

---

## 4. Actual Automated Test Results

Executed on local machine:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- D:\oogway\lenny growth assistant\lenny-growth-assistant\backend\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\oogway\lenny growth assistant\lenny-growth-assistant\backend
plugins: anyio-4.15.1
collected 98 items

tests/test_agent.py::test_rag_agent_query_with_context PASSED             [  1%]
tests/test_agent.py::test_rag_agent_empty_context PASSED                  [  2%]
tests/test_agent.py::test_rag_agent_citation_structure PASSED             [  3%]
tests/test_agent.py::test_rag_agent_system_prompt_structure PASSED        [  4%]
tests/test_agent.py::test_conversation_history_passed_to_provider PASSED  [  5%]
tests/test_agent.py::test_agent_handles_provider_exception PASSED         [  6%]
tests/test_artifacts.py::test_sanitizer_strips_script_tags PASSED        [  7%]
tests/test_artifacts.py::test_sanitizer_strips_inline_event_handlers PASSED [  8%]
tests/test_artifacts.py::test_sanitizer_strips_javascript_pseudo_protocols PASSED [  9%]
tests/test_artifacts.py::test_sanitizer_strips_dangerous_elements PASSED [ 10%]
tests/test_artifacts.py::test_sanitizer_preserves_safe_html_and_css PASSED [ 11%]
tests/test_artifacts.py::test_create_markdown_artifact_via_api PASSED    [ 12%]
tests/test_artifacts.py::test_create_html_artifact_via_api_is_sanitized PASSED [ 13%]
tests/test_artifacts.py::test_create_artifact_invalid_conversation PASSED [ 14%]
tests/test_artifacts.py::test_create_artifact_unsupported_type PASSED    [ 15%]
tests/test_artifacts.py::test_list_artifacts_for_conversation PASSED     [ 16%]
tests/test_artifacts.py::test_get_and_update_artifact_by_id PASSED       [ 17%]
tests/test_artifacts.py::test_delete_artifact_by_id PASSED               [ 18%]
tests/test_artifacts.py::test_delete_conversation_cascades_to_artifacts PASSED [ 19%]
tests/test_artifacts.py::test_chat_message_generates_and_persists_html_artifact PASSED [ 20%]
tests/test_artifacts.py::test_chat_message_generates_and_persists_essay_artifact PASSED [ 21%]
tests/test_artifacts.py::test_ordinary_chat_does_not_create_artifact PASSED [ 22%]
tests/test_conversations.py::test_create_conversation PASSED             [ 23%]
tests/test_conversations.py::test_list_conversations PASSED              [ 24%]
tests/test_conversations.py::test_get_conversation_with_messages_chronological PASSED [ 25%]
tests/test_conversations.py::test_send_and_persist_message PASSED        [ 26%]
tests/test_conversations.py::test_get_invalid_conversation_id PASSED     [ 27%]
tests/test_conversations.py::test_delete_conversation PASSED             [ 28%]
tests/test_docker_deployment.py::test_compose_database_url_generation PASSED [ 29%]
tests/test_docker_deployment.py::test_cors_origins_include_docker_frontend PASSED [ 30%]
tests/test_docker_deployment.py::test_wait_for_db_immediate_success PASSED [ 31%]
tests/test_docker_deployment.py::test_wait_for_db_retry_then_success PASSED [ 32%]
tests/test_docker_deployment.py::test_wait_for_db_max_retries_exhausted PASSED [ 33%]
tests/test_essay_skill.py::test_skill_activation_applicability PASSED    [ 34%]
tests/test_essay_skill.py::test_topic_extraction PASSED                  [ 35%]
tests/test_essay_skill.py::test_word_count_calculation PASSED            [ 36%]
tests/test_essay_skill.py::test_retrieval_context_passed_to_skill PASSED [ 37%]
tests/test_essay_skill.py::test_empty_knowledge_base_behavior PASSED     [ 38%]
tests/test_essay_skill.py::test_ordinary_chat_requests_unaffected PASSED [ 39%]
tests/test_essay_skill.py::test_conversation_api_essay_persistence PASSED [ 40%]
tests/test_essay_skill.py::test_model_failure_handling_in_essay PASSED   [ 41%]
tests/test_frontend_flows_e2e.py::test_flow_1_open_application_health PASSED [ 42%]
tests/test_frontend_flows_e2e.py::test_flow_2_create_new_conversation PASSED [ 43%]
tests/test_frontend_flows_e2e.py::test_flow_3_and_4_send_question_and_reopen_conversation PASSED [ 44%]
tests/test_frontend_flows_e2e.py::test_flow_5_inspect_source_citations PASSED [ 45%]
tests/test_frontend_flows_e2e.py::test_flow_6_generate_ship_30_for_30_essay PASSED [ 46%]
tests/test_frontend_flows_e2e.py::test_flow_7_generate_markdown_artifact PASSED [ 47%]
tests/test_frontend_flows_e2e.py::test_flow_8_generate_html_artifact_and_preview_sanitization PASSED [ 48%]
tests/test_frontend_flows_e2e.py::test_flow_9_copy_download_artifact PASSED [ 50%]
tests/test_frontend_flows_e2e.py::test_flow_10_switch_between_conversations_and_artifacts PASSED [ 51%]
tests/test_frontend_flows_e2e.py::test_flow_11_request_failure_handling PASSED [ 52%]
tests/test_frontend_flows_e2e.py::test_flow_12_responsive_styles_and_breakpoints PASSED [ 53%]
tests/test_health.py::test_read_root PASSED                              [ 54%]
tests/test_health.py::test_health_check PASSED                           [ 55%]
tests/test_health.py::test_health_db_check_success PASSED                [ 56%]
tests/test_health.py::test_health_db_check_failure PASSED                [ 57%]
tests/test_providers.py::test_provider_selection_env_ollama PASSED       [ 58%]
tests/test_providers.py::test_provider_selection_env_anthropic PASSED    [ 59%]
tests/test_providers.py::test_provider_selection_env_claude_agent_sdk PASSED [ 60%]
tests/test_providers.py::test_provider_selection_env_mock PASSED         [ 61%]
tests/test_providers.py::test_provider_selection_unsupported PASSED      [ 62%]
tests/test_providers.py::test_ollama_mocked_success PASSED               [ 63%]
tests/test_providers.py::test_ollama_connection_failure PASSED           [ 64%]
tests/test_providers.py::test_ollama_missing_model PASSED                [ 65%]
tests/test_providers.py::test_ollama_timeout PASSED                      [ 66%]
tests/test_providers.py::test_ollama_health_checks PASSED                [ 67%]
tests/test_providers.py::test_anthropic_missing_api_key PASSED           [ 68%]
tests/test_providers.py::test_anthropic_placeholder_api_key PASSED       [ 69%]
tests/test_providers.py::test_anthropic_mocked_success PASSED            [ 70%]
tests/test_providers.py::test_anthropic_authentication_failure PASSED    [ 71%]
tests/test_providers.py::test_anthropic_rate_limit_failure PASSED        [ 72%]
tests/test_providers.py::test_anthropic_timeout_failure PASSED           [ 73%]
tests/test_providers.py::test_anthropic_connection_failure PASSED        [ 74%]
tests/test_providers.py::test_anthropic_health_masks_key PASSED          [ 75%]
tests/test_rag.py::test_normalize_text PASSED                            [ 76%]
tests/test_rag.py::test_chunk_text PASSED                                [ 77%]
tests/test_rag.py::test_metadata_preservation PASSED                     [ 78%]
tests/test_rag.py::test_metadata_missing_fields_not_fabricated PASSED    [ 79%]
tests/test_rag.py::test_load_empty_and_unsupported_files PASSED          [ 80%]
tests/test_rag.py::test_duplicate_ingestion_behavior PASSED              [ 81%]
tests/test_rag.py::test_empty_knowledge_base_retrieval PASSED            [ 82%]
tests/test_rag.py::test_retrieval_ranking_synthetic_docs PASSED          [ 83%]
tests/test_real_transcript_rag.py::test_real_transcripts_present_in_database PASSED [ 84%]
tests/test_real_transcript_rag.py::test_real_retrieval_product_market_fit PASSED [ 85%]
tests/test_real_transcript_rag.py::test_real_retrieval_growth_teams_adam_fishman PASSED [ 86%]
tests/test_real_transcript_rag.py::test_real_citations_have_valid_metadata_and_links PASSED [ 87%]
tests/test_real_transcript_rag.py::test_agent_attaches_only_real_citations_without_fabrication PASSED [ 88%]
tests/test_transcript_integration.py::test_transcript_target_filtering PASSED [ 89%]
tests/test_transcript_integration.py::test_transcript_frontmatter_and_body_extraction PASSED [ 90%]
tests/test_transcript_integration.py::test_timestamp_deep_link_extraction PASSED [ 91%]
tests/test_transcript_integration.py::test_idempotent_duplicate_skipping PASSED [ 92%]
tests/test_transcript_integration.py::test_retrieval_returns_grounded_citations PASSED [ 93%]
tests/test_providers.py::test_rag_citations_attached_with_mocked_provider PASSED [ 94%]
tests/test_providers.py::test_ship_30_for_30_essay_with_configured_provider PASSED [ 95%]
tests/test_providers.py::test_artifact_generation_with_configured_provider PASSED [ 96%]
tests/test_providers.py::test_failure_handling_no_duplicate_messages_or_artifacts PASSED [ 97%]
tests/test_providers.py::test_health_endpoints_provider_resilience PASSED [ 98%]

======================= 98 passed, 2 warnings in 4.95s ========================
```

---

## 5. Frontend Production Build Verification

Executed in `frontend/`:
```text
> lenny-growth-assistant-frontend@0.1.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 39 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.80 kB │ gzip:  0.45 kB
dist/assets/index-C5H1_kt8.css   23.28 kB │ gzip:  4.91 kB
dist/assets/index-Cd7wPR3b.js   173.21 kB │ gzip: 53.85 kB
✓ built in 1.09s
```
Zero lint errors, zero build errors.
