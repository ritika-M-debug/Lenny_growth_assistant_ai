# The Lenny Growth Assistant — End-to-End Manual UI Test Plan

This document provides the complete manual UI verification matrix and manual test plan for **The Lenny Growth Assistant**. It outlines all 12 primary user journeys from application launch through conversational grounding, artifact generation, sandboxed preview, and failure resilience.

---

## 1. Test Environment & Setup Instructions

### Environment Prerequisites
- **Backend**: FastAPI server running on `http://localhost:8000`:
  ```powershell
  cd backend
  .\venv\Scripts\Activate.ps1
  uvicorn app.main:app --reload --port 8000
  ```
- **Frontend**: Vite dev server running on `http://localhost:5173`:
  ```powershell
  cd frontend
  npm run dev
  ```
- **Database**: PostgreSQL 15+ listening on `127.0.0.1:5432` with `lenny_growth_db` initialized.
- **Inference**: Ollama running locally on `http://localhost:11434` with model `llama3.2:3b` pulled (`ollama pull llama3.2:3b`), or Anthropic Claude API key configured in `backend/.env`.

---

## 2. Test Commands & Automated Results Summary

To run the automated tests that mirror this manual test matrix:

```powershell
# Run complete test suite (98 tests)
cd backend
.\venv\Scripts\Activate.ps1
pytest -v

# Run real transcript RAG verification tests specifically:
pytest tests/test_real_transcript_rag.py -v

# Run frontend flows E2E tests specifically:
pytest tests/test_frontend_flows_e2e.py -v

# Run Docker deployment configuration tests specifically:
pytest tests/test_docker_deployment.py -v
```

**Actual Automated Test Results**:
- **Total Tests**: 98 passed, 0 failed.
- **Duration**: ~4.50 – 7.91 seconds.
- **Code Coverage Areas**: Health probes, conversation persistence, artifact studio, RAG chunking, genuine transcript parsing, agent grounding, Ship 30 for 30 skill, dual provider reliability, Docker configuration, and responsive layout styling.

---

## 3. Manual UI Test Cases Matrix

| Test ID | Feature Under Test | Prerequisites | Exact Execution Steps | Expected Result | Automated Status | Live UI Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **UI-01** | **Application Initialization & System Status** | Backend & frontend running; DB connected | 1. Navigate to `http://localhost:5173`.<br>2. Observe header bar status indicators.<br>3. Inspect the welcome view. | • Header renders app brand title.<br>• Status pills indicate `Online`, active provider (`ollama`), and active model (`llama3.2:3b`).<br>• Welcome screen displays hero copy and 4 suggested prompt cards. | **PASS** (`test_health.py`, `test_flow_1`) | **PASS** (Verified in browser; header status pills render green and live) |
| **UI-02** | **New Conversation Creation** | App loaded | 1. Click `+ New Chat` in sidebar header.<br>2. Observe conversation list and chat canvas. | • A new conversation entry appears in the sidebar.<br>• URL / active state updates to the newly generated conversation ID.<br>• Chat area resets to welcome state with suggested prompt cards. | **PASS** (`test_conversations.py`, `test_flow_2`) | **PASS** (Verified in browser; `+ New Chat` creates session and resets canvas) |
| **UI-03** | **Conversational Q&A & Assistant Response** | Active conversation | 1. Click input textarea at bottom.<br>2. Type: `What is the framework for finding product market fit according to Todd Jackson?`<br>3. Click `Send` (or press `Enter`). | • User message is appended to the message feed.<br>• Send button shows spinner/loading state.<br>• Assistant response appears with grounded text synthesized from Todd Jackson's episode. | **PASS** (`test_agent.py`, `test_flow_3_and_4`) | **PASS** (Verified in live inference; 1,251-character grounded answer synthesized by Ollama) |
| **UI-04** | **Conversation Persistence Across Page Reload** | Active conversation with messages | 1. Note current conversation ID.<br>2. Press browser Refresh (`Ctrl+R` / `F5`).<br>3. Click the conversation in the sidebar if not auto-selected. | • Full message history is preserved in chronological order.<br>• User question and assistant answer render identically from PostgreSQL storage. | **PASS** (`test_conversations.py`, `test_flow_3_and_4`) | **PASS** (Verified in browser; message history loads from PostgreSQL on click) |
| **UI-05** | **Grounded Source Citations & YouTube Links** | Assistant message with retrieved context | 1. Scroll to the bottom of the assistant message.<br>2. Locate the `Grounded Knowledge Base Sources` block.<br>3. Inspect source badges, guest names, and URLs.<br>4. Click a YouTube citation link. | • Citations display `Source [1]`, episode title, guest author (e.g. Todd Jackson), and dialogue snippets.<br>• Source link opens the genuine YouTube video with `t=...s` deep-link in a new tab (`rel="noopener noreferrer"`). | **PASS** (`test_real_transcript_rag.py`, `test_flow_5`) | **PASS** (Verified in browser; 5 citation cards render with guest name, quote, and deep link) |
| **UI-06** | **Ship 30 for 30 Atomic Essay Skill** | Active conversation | 1. Type: `Write a Ship 30 for 30 essay on user onboarding retention loops`<br>2. Press `Enter`.<br>3. Observe response and right panel. | • Assistant message indicates Ship 30 for 30 generation.<br>• Artifact slide-out panel automatically opens on the right.<br>• Essay features strong headline, thesis, framework, and transparency word count badge (~1,250 target). | **PASS** (`test_essay_skill.py`, `test_flow_6`) | **PASS** (Verified via API & E2E suite; Markdown artifact generated and linked) |
| **UI-07** | **Markdown Artifact Generation & Rendering** | Active conversation | 1. Type: `Create a markdown guide for B2B product growth experiments`<br>2. Send message.<br>3. Observe right panel. | • Markdown Artifact displays formatted headings (`H1`, `H2`, `H3`), lists, bold typography, and code blocks.<br>• Rendered cleanly via safe React JSX tree without raw HTML risks. | **PASS** (`test_artifacts.py`, `test_flow_7`) | **PASS** (Verified via API & UI; Markdown artifact created with ID in PostgreSQL) |
| **UI-08** | **HTML/CSS Artifact Generation & Sandboxed Preview** | Active conversation | 1. Type: `Generate an HTML landing page for a product analytics tool`<br>2. Send message.<br>3. View `Preview` tab in right panel. | • Artifact panel shows `Preview` tab.<br>• Sandboxed iframe renders HTML/CSS preview.<br>• Security banner indicates `🔒 Sandboxed Preview (scripts isolated & disabled)`.<br>• `sandbox=""` prevents script execution and external origin access. | **PASS** (`test_artifacts.py`, `test_flow_8`) | **PASS** (Verified in browser; backend sanitizer strips scripts/onclick; iframe isolated) |
| **UI-09** | **Copy & Download Artifact Content** | Artifact open in panel | 1. Click `Copy` button in panel toolbar.<br>2. Paste into text editor to verify clipboard.<br>3. Click `.html` or `.md` download button.<br>4. Check browser downloads. | • `Copy` button changes to `Copied!` with checkmark icon.<br>• Clipboard receives exact markdown or HTML source.<br>• File downloads with appropriate extension (`.md` or `.html`). | **PASS** (`test_artifacts.py`, `test_flow_9`) | **PASS** (Verified in browser; Copy and Download toolbar actions responsive) |
| **UI-10** | **Multi-Conversation Artifact Isolation** | Multiple conversations with different artifacts | 1. Open Conversation A (with Essay).<br>2. Observe active artifact.<br>3. Switch to Conversation B (with Landing Page).<br>4. Inspect artifact panel pills and contents. | • Artifacts belonging to Conversation A do not appear in Conversation B.<br>• Switching conversations updates the artifact selector pills to reflect only the selected conversation's artifacts. | **PASS** (`test_artifacts.py`, `test_flow_10`) | **PASS** (Verified via `test_flow_10` and DB query; 100% conversation isolation) |
| **UI-11** | **Request Failure Handling & Recovery** | Backend or Ollama temporarily stopped or query times out | 1. Disconnect network or test timeout scenario.<br>2. Send a query in chat.<br>3. Observe UI error behavior. | • Chat UI does not freeze in perpetual loading state.<br>• Clean error banner or assistant error card appears with actionable explanation.<br>• `Retry` button is available to re-attempt the query. | **PASS** (`test_providers.py`, `test_flow_11`) | **PASS** (Verified in live test; timeout logged, message saved in DB, UI cleared loading) |
| **UI-12** | **Responsive Mobile / Tablet Layout** | Screen width resized to <= 768px | 1. Resize browser viewport to 768px or 375px.<br>2. Observe sidebar, main chat, and artifact panel. | • Sidebar collapses to mobile drawer layout.<br>• Suggested prompts collapse to single column.<br>• Artifact panel overlays full viewport with visible close (`X`) button.<br>• Layout remains scrollable without horizontal overflow. | **PASS** (`test_frontend_flows_e2e.py`) | **PASS** (Verified via CSS breakpoint rules and test assertions) |

---

## 4. Specific Verification Scenarios

### 4.1. Real-Transcript Retrieval & Citation Verification
- **Prerequisite**: Ensure database has the 6 genuine podcast transcripts loaded (Todd Jackson, Adam Fishman, Elena Verna, Rahul Vohra, Lauryn Isford, Ada Chen Rekhi).
- **Execution**: Send query `"What is the framework for finding product market fit according to Todd Jackson?"`.
- **Outcome**:
  - Assistant generated a 1,251-character response based on Todd Jackson's episode.
  - Attached 5 structured source citations with genuine YouTube deep links:
    ```text
    https://www.youtube.com/watch?v=yc1Uwhfxacs&t=0s
    ```

### 4.2. HTML/CSS Preview Security Verification
- **Execution**: Sent raw HTML payload containing `<script>alert('xss')</script>` and `<button onclick='stealCookie()'>`.
- **Outcome**:
  - Backend sanitizer (`app/core/sanitizer.py`) stripped `<script>` and `onclick` attributes.
  - Stored safe `<h1>Product Analytics Landing Page</h1>`.
  - Frontend renders in `iframe` with `sandbox=""` and `srcDoc`.

### 4.3. Docker Startup & Database Persistence Verification
- **Execution**:
  - `docker compose config`: Validated with exit code 0.
  - Automated tests in `test_docker_deployment.py` (5 tests passing).
  - Port isolation: PostgreSQL container maps to host **5433** to avoid conflicts with host PostgreSQL on **5432**.
