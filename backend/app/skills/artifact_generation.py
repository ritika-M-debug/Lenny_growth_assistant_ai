import re
from typing import Dict, Any, Optional, List
from app.skills.base import BaseSkill
from app.agents.base import BaseLLMProvider, AgentResponse, SourceCitation
from app.knowledge_base.retrieval import RetrievalService
from app.core.sanitizer import sanitize_html


class ArtifactGenerationSkill(BaseSkill):
    """
    Dedicated skill for generating interactive HTML/CSS landing pages,
    mockups, and comprehensive Markdown reports/guides.
    """

    @property
    def name(self) -> str:
        return "artifact_generation"

    @property
    def description(self) -> str:
        return (
            "Generates structured Markdown documents, comprehensive growth reports, and "
            "sandboxed HTML/CSS landing pages grounded in product management and growth principles."
        )

    def is_applicable(self, user_message: str) -> bool:
        """
        Detects whether user prompt explicitly requests a document, landing page,
        HTML mockup, guide, or report artifact.
        """
        if not user_message or not user_message.strip():
            return False

        msg = user_message.strip().lower()

        # HTML / Landing page patterns
        html_triggers = [
            r"\b(html|landing\s+page|webpage|web\s+page|html\s+mockup|html\s+widget|html\s+component|html/css)\b",
            r"\b(generate|create|build|code|design)\b.*\b(landing\s+page|html\s+page|mockup)\b"
        ]
        for pat in html_triggers:
            if re.search(pat, msg):
                return True

        # Markdown guide / report / document patterns
        doc_triggers = [
            r"\b(create|generate|draft|build|write)\b.*\b(markdown\s+(guide|doc|document|report)|growth\s+report|cheat\s+sheet|playbook|checklist|blueprint|framework\s+guide|summary\s+report)\b",
            r"\b(create|generate)\s+(an?\s+)?artifact\b",
            r"\bmarkdown\s+(guide|report|document)\s+(on|about|for)\b"
        ]
        for pat in doc_triggers:
            if re.search(pat, msg):
                return True

        return False

    def determine_artifact_type(self, user_message: str) -> str:
        """Determines whether the requested artifact is 'html' or 'markdown'."""
        msg = user_message.lower()
        if any(k in msg for k in ["html", "landing page", "webpage", "web page", "css", "mockup", "widget", "ui template"]):
            return "html"
        return "markdown"

    def extract_topic(self, user_message: str) -> str:
        """Extracts the core topic by stripping action verbs and artifact descriptors."""
        text = user_message.strip()

        cleaning_patterns = [
            r"^(please\s+)?(create|generate|build|code|design|draft|write)\s+(an?\s+)?(interactive\s+)?(html\s+)?(css\s+)?(landing\s+page|mockup|webpage|widget|component)\s+(for|about|on)\s+",
            r"^(please\s+)?(create|generate|build|draft|write)\s+(an?\s+)?(markdown\s+)?(guide|report|playbook|checklist|blueprint|cheat\s+sheet|document)\s+(on|about|for|regarding)\s+",
            r"^(please\s+)?(create|generate)\s+(an?\s+)?artifact\s+(on|about|for)\s+",
        ]

        for pat in cleaning_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                rem = text[m.end():].strip()
                if rem:
                    return rem.rstrip(".?!")

        return text.strip(".?!")

    def build_system_prompt(self, topic: str, artifact_type: str, context_str: str, has_context: bool) -> str:
        """Constructs system prompt enforcing security constraints and aesthetic guidelines."""
        kb_block = (
            f"REFERENCE MATERIAL FROM LENNY'S PODCAST:\n"
            f"<retrieved_context>\n{context_str}\n</retrieved_context>\n\n"
            "GROUNDING RULES:\n"
            "1. Ground relevant tactics, frameworks, and guest quotes in <retrieved_context>.\n"
            "2. Never hallucinate fake podcast guests or made-up URLs.\n"
            "3. Cite referenced sources clearly.\n\n"
            if has_context
            else
            "KNOWLEDGE BASE NOTE:\n"
            "No specific matching podcast transcripts were found in the knowledge base. "
            "Synthesize industry best practices and clear product management principles without fabricating fake podcast citations.\n\n"
        )

        if artifact_type == "html":
            return (
                "You are an expert Frontend Design Engineer creating responsive, modern HTML/CSS artifacts.\n"
                f"Your task is to generate a complete, beautiful HTML/CSS artifact for: '{topic}'.\n\n"
                f"{kb_block}"
                "DESIGN & AESTHETICS REQUIREMENTS:\n"
                "- Create a complete, self-contained HTML document with a <style> block inside <head>.\n"
                "- Use a modern, premium design with curated CSS color tokens, sleek typography (system fonts), "
                "subtle box-shadows, responsive flexbox/grid layout, and clean card components.\n"
                "- Include a compelling Hero section, Key Features / Pillars, Metric Highlights, and a Call-To-Action (CTA).\n\n"
                "STRICT SECURITY RULES:\n"
                "- Output ONLY pure HTML and CSS.\n"
                "- Absolutely NO <script> tags, NO JavaScript code, and NO inline event handlers (no onload, onerror, onclick, etc.).\n"
                "- Do NOT link external scripts, iframes, or tracking pixels.\n"
                "- Provide raw HTML code ready to render safely in a sandboxed preview frame."
            )
        else:
            return (
                "You are an expert Product Strategy Lead creating comprehensive Markdown documentation and guides.\n"
                f"Your task is to generate a thorough, beautifully formatted Markdown artifact on: '{topic}'.\n\n"
                f"{kb_block}"
                "STRUCTURE & FORMATTING REQUIREMENTS:\n"
                "- # Main Title\n"
                "- Executive Summary / Core Objective\n"
                "- ## Section 1: Foundational Mental Models & Principles\n"
                "- ## Section 2: Step-by-Step Tactical Implementation Playbook\n"
                "- ## Section 3: Metric Scorecard & Validation Checklist (with Markdown tables or checkboxes)\n"
                "- ## Section 4: Common Pitfalls & Countermeasures\n"
                "- ## Sources & Grounded References (if transcript sources were provided)\n"
                "- Use bold highlights, bulleted lists, and clear structured markdown."
            )

    def execute(
        self,
        user_message: str,
        llm_provider: BaseLLMProvider,
        retrieval_service: RetrievalService,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 3,
        **kwargs
    ) -> AgentResponse:
        """
        Executes artifact generation workflow:
        1. Determines artifact type (HTML or Markdown).
        2. Retrieves grounded context from PostgreSQL.
        3. Generates artifact content with LLM.
        4. Sanitizes HTML outputs for preview safety.
        5. Returns structured AgentResponse with artifact payload.
        """
        topic = self.extract_topic(user_message)
        artifact_type = self.determine_artifact_type(user_message)

        # 1. Retrieve grounded context
        retrieved_chunks = retrieval_service.retrieve_context(topic, top_k=top_k, min_similarity=0.25)
        has_context = len(retrieved_chunks) > 0

        # 2. Extract citations
        citations: List[SourceCitation] = []
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            meta = chunk.get("metadata", {})
            content_snippet = chunk.get("content", "")[:150] + "..." if len(chunk.get("content", "")) > 150 else chunk.get("content", "")
            citations.append(SourceCitation(
                source_number=idx,
                title=meta.get("title", f"Source {idx}"),
                source_type=meta.get("source_type", "podcast"),
                author=meta.get("guest") or meta.get("author"),
                episode_title=meta.get("episode_title"),
                publication_date=meta.get("publication_date"),
                source_url=meta.get("source_url"),
                snippet=content_snippet,
                similarity_score=chunk.get("similarity_score", 0.0)
            ))

        context_str = retrieval_service.format_context_for_prompt(retrieved_chunks)

        # 3. Build Prompt
        system_prompt = self.build_system_prompt(topic, artifact_type, context_str, has_context)
        user_prompt = f"Generate the complete {artifact_type.upper()} artifact for: '{topic}'."

        messages_payload = [
            {"role": "user", "content": user_prompt}
        ]

        # 4. Generate Artifact with LLM
        raw_output = llm_provider.generate_chat_response(
            messages=messages_payload,
            system_prompt=system_prompt,
            temperature=0.7
        )

        # Extract code block if model wrapped output in markdown fences
        artifact_content = raw_output
        if artifact_type == "html":
            html_fence_match = re.search(r"```(?:html)?\s*(<!DOCTYPE[\s\S]*?</html>|<html[\s\S]*?</html>|<div[\s\S]*?</div>)\s*```", raw_output, re.IGNORECASE)
            if html_fence_match:
                artifact_content = html_fence_match.group(1).strip()
            elif "```html" in raw_output:
                artifact_content = raw_output.split("```html", 1)[1].split("```", 1)[0].strip()
            elif "```" in raw_output and "<" in raw_output:
                artifact_content = raw_output.split("```", 1)[1].split("```", 1)[0].strip()

            # Sanitize generated HTML to guarantee safety
            artifact_content = sanitize_html(artifact_content)
        else:
            # For markdown, strip outer markdown code fences if wrapped as a block
            if raw_output.startswith("```markdown") and raw_output.endswith("```"):
                artifact_content = raw_output[len("```markdown"): -3].strip()

        # Derive Artifact Title
        artifact_title = topic.title()
        if len(artifact_title) > 60:
            artifact_title = artifact_title[:57] + "..."

        # Chat message summary text
        chat_summary = (
            f"I have generated the requested **{artifact_type.upper()} Artifact**: **{artifact_title}**.\n\n"
            f"You can view, preview, copy, or download it in the dedicated **Artifact Panel** on the right."
        )

        status_flag = "success" if has_context else "empty_kb"

        return AgentResponse(
            content=chat_summary,
            citations=citations,
            provider=llm_provider.provider_name,
            model=llm_provider.model_name,
            retrieved_count=len(citations),
            status=status_flag,
            skill=self.name,
            extra_metadata={
                "skill": self.name,
                "topic": topic,
                "artifact_title": artifact_title,
                "artifact_type": artifact_type,
                "artifact_content": artifact_content
            }
        )
