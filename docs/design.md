# Product & UI Design Specification

## Project Name: The Lenny Growth Assistant
**Document Version:** 1.0.0  
**Design System:** Custom Vanilla CSS Design System (`global.css`, `chat.css`)  
**Status:** Completed & Verified  

---

## 1. Design Overview & Philosophy

**The Lenny Growth Assistant** is designed as a focused, high-productivity workspace tailored for product managers, growth leads, and founders. The interface emphasizes:

- **Clarity & Information Density**: Clean typography, high contrast, and structured visual hierarchy to facilitate reading deep essays and technical playbooks.
- **Glassmorphic Modern Dark Aesthetic**: Tailored dark-mode palette (`#0a0d14` background, `#121826` panel cards, `#1e293b` borders) with vibrant indigo/blue accents (`#3b82f6`, `#6366f1`) and emerald success accents (`#10b981`).
- **Interactive Multi-Panel Workflow**: Split-view architecture providing seamless transition between conversational reasoning and side-by-side artifact inspection.
- **Defensive Sandbox Security**: Visual cues (e.g. `🔒 Sandboxed Preview`) ensuring complete transparency that generated web artifacts are isolated and safe.

---

## 2. Layout Architecture & Main Screens

The web application follows a responsive three-pane layout:

```text
+---------------------------------------------------------------------------------------------------------+
|                                              HEADER BAR                                                 |
|  [Logo & Brand: The Lenny Growth Assistant]                  [Status: Online] [Provider: Ollama] [Model]|
+-----------------------+----------------------------------------------------+----------------------------+
|        SIDEBAR        |                     CHAT AREA                      |       ARTIFACT PANEL       |
|                       |                                                    |      (Slides out when      |
|  [+ New Chat Button]  |  [Welcome Hero & Prompt Starter Cards]             |     deliverables exist)    |
|                       |  or                                                |                            |
|  Conversation List:   |  [Message Stream]                                  |  [Title & Type Badge]      |
|  • Active Chat        |   - User Query Bubble (Right-aligned)              |  [Artifact Switcher Pills] |
|  • Saved Chat A       |   - Assistant Bubble (Left-aligned)                |                            |
|  • Saved Chat B       |     + Grounded Text                                |  [Page Preview | Raw Code] |
|                       |     + [Source Citation Cards & YouTube Links]      |  [Sandboxed Iframe View]   |
|  [Delete Action]      |                                                    |                            |
|                       |  [Input Textarea & Send / Spinner Button]          |  [Copy] [Download] [Close] |
+-----------------------+----------------------------------------------------+----------------------------+
```

### Component Breakdown

1. **[`Header.jsx`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/frontend/src/components/Header.jsx)**:
   - Application identity with spark/growth icon badge.
   - Dynamic system status pills:
     - `Online` / `Offline` server status probe.
     - Active LLM Provider (`ollama`, `anthropic`, or `mock`).
     - Configured model (`llama3.2:3b`, `claude-3-5-sonnet-20241022`).
     - Tooltip with provider diagnostics from `GET /health/llm`.

2. **[`Sidebar.jsx`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/frontend/src/components/Sidebar.jsx)**:
   - Top action: `+ New Chat` button with hover elevation.
   - Chronological list of saved conversations fetched from PostgreSQL.
   - Active conversation pill highlighting with border glow (`#3b82f6`).
   - Per-item inline delete button with confirmation tooltip.
   - Responsive slide-over drawer on mobile/tablet viewports.

3. **[`ChatArea.jsx`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/frontend/src/components/ChatArea.jsx)**:
   - **Welcome State**: High-converting hero copy and 4 suggested prompt cards:
     1. *"What is the 40% rule for finding product-market fit?"*
     2. *"How should I structure a high-performing growth team?"*
     3. *"Write a Ship 30 for 30 essay on user onboarding retention loops"*
     4. *"Generate an HTML landing page for a B2B product analytics tool"*
   - **Message Feed**: Auto-scrolling chronological message stream.
   - **Prompt Input**: Multi-line auto-resizing textarea with `Enter` submit and `Shift+Enter` newline support.
   - **Loading State**: Active animated typing dots and disabled submit button.

4. **[`ArtifactPanel.jsx`](file:///d:/oogway/lenny%20growth%20assistant/lenny-growth-assistant/frontend/src/components/ArtifactPanel.jsx)**:
   - Slide-out side drawer that opens automatically when an artifact is synthesized.
   - Header with artifact title, type badge (`HTML Landing Page` or `Markdown Document`), and control actions (`Copy`, `Download`, `Close`).
   - Multiple artifact tabs/pills if a conversation contains multiple deliverables.
   - View mode toggle: `Page Preview` vs `Raw Code`.
   - Security sandbox alert banner.

---

## 3. Chat Interface & Message States

### 3.1. Message States

| State | Visual Treatment | Interaction Details |
|---|---|---|
| **User Message** | Right-aligned bubble, dark navy accent (`#1e293b`), crisp border | Displays user text verbatim, preserves formatting |
| **Assistant Message** | Left-aligned card, deep background (`#121826`), high-contrast text | Markdown headings, bold bullet points, and code formatting |
| **Empty Knowledge Base** | Amber warning callout border (`#f59e0b`) | Informs user that no podcast chunks matched the prompt and answers using general principles |
| **Loading / Generating** | Animated wave dots spinner in input area and assistant bubble | Send button transitions to loading state; input disabled |
| **Error / Timeout** | Red tinted banner (`#ef4444`) with warning icon | Displays actionable resolution message and `<RefreshCw />` **Retry** button |

### 3.2. Citation Presentation & Provenance

When an assistant response uses retrieved knowledge chunks, a dedicated **Grounded Knowledge Base Sources** accordion is rendered beneath the message:

- **Source Badge**: `Source [1]`, `Source [2]`, etc., matching bracket citations in the body text.
- **Guest / Author**: Verified guest name (e.g. *Todd Jackson*, *Elena Verna*, *Lauryn Isford*).
- **Episode Title**: Full official podcast title (e.g. *A framework for finding product-market fit*).
- **Dialogue Snippet**: Collapsible blockquote showing the transcript excerpt that informed the answer.
- **YouTube Timestamp Deep Link**: Direct hyperlink formatted with exact timestamp seconds (`&t=1014s`).
  - Strict security validation: Only renders clickable links if starting with `http://` or `https://`.
  - Links open in a new tab with `target="_blank"` and `rel="noopener noreferrer"`.

---

## 4. Artifact Studio & Sandboxed Preview

### 4.1. Visual & Source Switching

- **Page Preview Tab**: Renders HTML/CSS landing pages and widgets directly inside a responsive sandboxed iframe container.
- **Raw Code Tab**: Syntax-formatted code view allowing users to inspect the clean HTML, CSS, or Markdown source.

### 4.2. Action Toolbar

- **Copy Button**: Copies raw source code to the system clipboard using the browser Clipboard API. Provides instant visual feedback by switching to `✓ Copied!` for 2 seconds.
- **Download Button**: Exports the artifact as an external file directly through the browser:
  - Markdown artifacts download as `<title-slug>.md`
  - HTML artifacts download as `<title-slug>.html`
- **Close Button (`✕`)**: Closes the studio panel to maximize chat canvas space. Can be reopened anytime by clicking the artifact pill in the chat message.

### 4.3. HTML/CSS Preview Isolation Architecture

To ensure 100% defense-in-depth against Cross-Site Scripting (XSS) and client code injection, artifacts undergo two layers of isolation:

```text
[ LLM Generated HTML ]
          │
          ▼
[ Backend Sanitizer: app/core/sanitizer.py ]
  • Strips <script> tags
  • Strips inline handlers (onclick, onerror, onload)
  • Strips javascript: pseudo-protocols
  • Strips <object>, <embed>, <applet>
          │
          ▼
[ PostgreSQL Storage: artifacts table ]
          │
          ▼
[ Frontend ArtifactPanel.jsx ]
  • Sandboxed <iframe> element:
      <iframe
        sandbox=""
        srcDoc={sanitizedHtml}
        title="Artifact Sandboxed Preview"
      />
  • No 'allow-scripts' -> Browser rejects JS execution
  • No 'allow-same-origin' -> Blocked from accessing parent cookies / localStorage
  • Security banner: "🔒 Sandboxed Preview (scripts isolated & disabled)"
```

---

## 5. Responsive Behavior & Breakpoints

The application enforces a fluid, responsive layout across all device viewports:

| Viewport Range | Breakpoint | Sidebar Behavior | Chat Area Behavior | Artifact Panel Behavior |
|---|---|---|---|---|
| **Desktop** | `> 1024px` | Fixed left column (280px) | Expands to fill available middle space (max 860px reading column) | Slides out as right column (520px or 50% split view) |
| **Tablet** | `768px - 1024px` | Collapsible left drawer with toggle button | Full width of tablet canvas | Overlays right 70% with dismiss backdrop |
| **Mobile** | `<= 768px` | Off-canvas drawer (100% width on mobile menu toggle) | Full viewport width; prompt cards collapse to 1 column | Full-screen overlay with sticky header and close button |

---

## 6. Design System Tokens (`global.css` & `chat.css`)

```css
:root {
  /* Surface Colors */
  --bg-primary: #0a0d14;
  --bg-secondary: #121826;
  --bg-tertiary: #1a2234;
  --bg-card: #161f30;
  --border-subtle: #1e293b;
  --border-focus: #3b82f6;

  /* Typography Colors */
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;

  /* Accent & State Colors */
  --accent-blue: #3b82f6;
  --accent-indigo: #6366f1;
  --accent-purple: #8b5cf6;
  --accent-emerald: #10b981;
  --state-warning: #f59e0b;
  --state-error: #ef4444;

  /* Elevation & Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
  --shadow-glow: 0 0 15px rgba(59, 130, 246, 0.3);

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 7. Important Design Decisions & Rationale

1. **Vanilla CSS over Tailwind CSS**:
   - The design uses custom Vanilla CSS (`global.css` and `chat.css`) to maintain complete control over complex layout transitions, custom scrollbars, and iframe sandboxing without build tool abstraction or CSS purging conflicts.
2. **Side-by-Side Artifact Panel vs. Modal**:
   - Rather than rendering generated artifacts inside disruptive modal dialogues, the application uses a split-screen side panel. This allows product managers to simultaneously read conversational explanations on the left while interacting with the deliverable on the right.
3. **Explicit Word-Count Badge on Essays**:
   - Instead of hiding word metrics, Ship 30 for 30 essays render a visible transparent word count badge (e.g. `Word count: ~1,169 words`). This gives founders and writers immediate confidence that the output meets long-form publishing standards.
4. **Permanent Chat Persistence with Zero Login Friction**:
   - To maximize developer and evaluator experience during local assessment, conversations persist seamlessly to PostgreSQL without requiring authentication or session tokens.
