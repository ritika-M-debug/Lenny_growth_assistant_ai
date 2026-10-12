import re
from typing import Dict, Any, Optional, List
from app.skills.base import BaseSkill
from app.agents.base import BaseLLMProvider, AgentResponse, SourceCitation
from app.knowledge_base.retrieval import RetrievalService


class Ship30For30Skill(BaseSkill):
    """
    Dedicated Ship 30 for 30 Essay Generation Skill for The Lenny Growth Assistant.
    Generates high-signal, atomic ~1,250-word essays grounded in Lenny's Podcast transcripts.
    """

    TARGET_WORD_COUNT: int = 1250
    MIN_WORD_THRESHOLD: int = 700

    @property
    def name(self) -> str:
        return "ship_30_for_30"

    @property
    def description(self) -> str:
        return (
            "Generates structured ~1,250-word Ship 30 for 30-style essays on product management, "
            "growth strategy, and startup execution, strictly grounded in Lenny's Podcast transcripts."
        )

    def is_applicable(self, user_message: str) -> bool:
        """
        Determines whether the user request asks for an essay.
        Detects keywords like 'essay', 'ship 30 for 30', 'atomic essay', or structured article generation.
        """
        if not user_message or not user_message.strip():
            return False

        msg = user_message.strip().lower()

        # Direct Ship 30 for 30 mentions
        if "ship 30" in msg or "ship30" in msg or "atomic essay" in msg:
            return True

        # Verb + essay/article patterns
        essay_patterns = [
            r"\b(write|generate|draft|create|compose|produce)\b.*\b(essay|longform piece|deep dive essay)\b",
            r"\b(turn|synthesize)\b.*\binto\b.*\b(essay|article)\b",
            r"\bexplain\b.*\bthrough\b.*\b(essay|structured essay)\b",
            r"\bessay\s+(about|on|regarding|discussing)\b",
            r"^\s*essay:\s*",
        ]

        for pat in essay_patterns:
            if re.search(pat, msg, re.IGNORECASE):
                return True

        return False

    def extract_topic(self, user_message: str) -> str:
        """
        Extracts the central subject matter from the user prompt by stripping command boilerplate.
        """
        text = user_message.strip()

        # Check special patterns that embed topic in the middle
        # "explain X through an essay"
        m_explain = re.search(r"^(?:please\s+)?explain\s+(.*?)\s+through\s+(?:an?\s+)?(?:structured\s+)?essay", text, re.I)
        if m_explain:
            return m_explain.group(1).strip()

        # "turn insights from X into an essay" or "turn X into an essay"
        m_turn = re.search(r"^(?:please\s+)?turn\s+(?:insights\s+from\s+)?(.*?)\s+into\s+(?:an?\s+)?(?:practical\s+)?essay(?:\s+(?:on|about)\s+(.*))?", text, re.I)
        if m_turn:
            topic = m_turn.group(2) or m_turn.group(1)
            return topic.strip()

        # Leading command prefixes to strip
        prefix_pattern = (
            r"^(?:please\s+)?"
            r"(?:(?:write|generate|draft|create|compose|give\s+me)\s+)?"
            r"(?:an?\s+)?"
            r"(?:ship\s*30\s*(?:for|\/)?\s*30\s+)?"
            r"(?:atomic\s+)?"
            r"(?:essay|article|piece)\s*"
            r"(?:about|on|regarding|discussing|of|for|:)?\s*"
        )
        cleaned = re.sub(prefix_pattern, "", text, flags=re.I).strip()
        if cleaned:
            return cleaned.rstrip(".?!")

        return text.strip(".?!")

    @staticmethod
    def count_words(text: str) -> int:
        """
        Counts words in markdown text using whitespace-delimited tokens.
        Excludes word count footnote reporting notices.
        """
        if not text:
            return 0

        clean = text
        if "\n---\n*Word count:" in clean:
            clean = clean.split("\n---\n*Word count:")[0]

        words = [w for w in clean.strip().split() if w]
        return len(words)

    def build_system_prompt(self, topic: str, context_str: str, has_context: bool) -> str:
        """
        Builds the system prompt instructing the model to produce a high-signal Ship 30 for 30 essay.
        """
        kb_grounding_block = (
            f"REFERENCE TRANSCRIPT MATERIAL FROM LENNY'S PODCAST:\n"
            f"<retrieved_context>\n{context_str}\n</retrieved_context>\n\n"
            "GROUNDING & CITATION RULES:\n"
            "1. Ground all claims, quotes, and tactics attributed to Lenny or podcast guests strictly in <retrieved_context>.\n"
            "2. When attributing insights, explicitly cite the guest and source number, e.g., 'Todd Jackson notes [Source 1]' or '[Source 2: Lauryn Isford]'.\n"
            "3. Clearly distinguish general product management best practices from podcast-supported claims.\n"
            "4. NEVER invent or hallucinate guest names, podcast quotes, or URLs.\n"
            "5. Include a clean '### Sources & References' section at the end of the essay referencing the cited episodes."
            if has_context
            else
            "KNOWLEDGE BASE NOTICE:\n"
            "No matching podcast transcripts were found in the knowledge base for this topic.\n"
            "Explicitly start the essay with a clear notice block:\n"
            "> **Notice**: No specific podcast transcript passages were found matching this topic in the knowledge base. "
            "This essay synthesizes general product management principles, and does not cite specific Lenny's Podcast episodes.\n"
            "Do NOT fabricate Lenny quotations or fake citations."
        )

        return (
            "You are a master digital writer and product strategy operator who writes in the Ship 30 for 30 atomic essay format.\n"
            "Your task is to write a comprehensive, high-signal, ~1,250-word essay on the requested topic.\n\n"
            "SHIP 30 FOR 30 WRITING PRINCIPLES:\n"
            "- High signal-to-noise ratio: Every sentence delivers actionable insight or clarity. No empty corporate filler.\n"
            "- Rhythm and readability: Short, punchy paragraphs (1 to 3 sentences maximum). Use single-sentence punchlines.\n"
            "- Skimmable structure: Compelling subheadings, bolded core takeaways, and bulleted playbooks.\n"
            "- Practical frameworks: Concrete step-by-step methodologies rather than vague abstractions.\n\n"
            "REQUIRED ESSAY STRUCTURE:\n"
            "1. # Compelling, High-Converting Title (Clear promise of value)\n"
            "2. **The Hook & Problem Statement**: Open with the counterintuitive reality, industry trap, or painful misconception.\n"
            "3. **The Core Thesis**: One central premise that shifts how the reader thinks about the problem.\n"
            "4. **Modular Framework Sections (3-5 Sections with ## Headings)**:\n"
            "   - Pillar 1: Principles and foundational mental models\n"
            "   - Pillar 2: Tactical execution and concrete mechanisms\n"
            "   - Pillar 3: Real-world guest insights and case studies\n"
            "   - Pillar 4: Common pitfalls and failure modes to avoid\n"
            "5. **Actionable Implementation Playbook**: A clear, numbered checklist or playbook the reader can execute this week.\n"
            "6. **Conclusion**: A memorable final takeaway and rallying cry.\n"
            "7. **Sources & References**: List grounded references with title and guest names.\n\n"
            f"{kb_grounding_block}\n\n"
            f"TARGET LENGTH: Aim for approximately {self.TARGET_WORD_COUNT} words of substantial, detailed content."
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
        Executes the Ship 30 for 30 essay generation workflow:
        1. Extracts topic.
        2. Retrieves relevant transcript chunks from PostgreSQL.
        3. Formats grounding context and citations.
        4. Invokes LLM provider with structured Ship 30 for 30 instructions.
        5. Validates word count and allows a controlled expansion if significantly under target.
        6. Appends word-count transparency report.
        """
        topic = self.extract_topic(user_message)
        if not topic:
            topic = user_message.strip()

        # 1. Retrieve grounded context from Knowledge Base
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

        # 3. Construct System Prompt & Messages Payload
        system_prompt = self.build_system_prompt(topic, context_str, has_context)
        user_prompt = f"Write a comprehensive, ~1,250-word Ship 30 for 30-style essay on: '{topic}'."

        messages_payload = []
        if history:
            for h in history[-4:]:
                role = h.get("role")
                content = h.get("content")
                if role in ["user", "assistant"] and content:
                    messages_payload.append({"role": role, "content": content})

        messages_payload.append({"role": "user", "content": user_prompt})

        # 4. Generate Initial Essay Draft
        essay_text = llm_provider.generate_chat_response(
            messages=messages_payload,
            system_prompt=system_prompt,
            temperature=0.7
        )

        initial_word_count = self.count_words(essay_text)

        # 5. Controlled Expansion if Substantially Under Target (< 700 words)
        final_essay = essay_text
        if initial_word_count < self.MIN_WORD_THRESHOLD and not getattr(llm_provider, "is_mock", False):
            try:
                expansion_prompt = (
                    f"The draft above currently has {initial_word_count} words. To reach the comprehensive "
                    f"~{self.TARGET_WORD_COUNT}-word target in the Ship 30 for 30 format, please expand on the topic with:\n"
                    "1. An in-depth '## Tactical Playbook: 5-Step Execution Guide' with detailed operational steps.\n"
                    "2. A dedicated '## Real-World Failure Modes & Countermeasures' section explaining how startups fail on this.\n"
                    "Provide only the detailed new sections to append seamlessly before the conclusion."
                )
                continuation_messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": essay_text},
                    {"role": "user", "content": expansion_prompt}
                ]
                expansion_text = llm_provider.generate_chat_response(
                    messages=continuation_messages,
                    system_prompt=system_prompt,
                    temperature=0.7
                )
                if expansion_text and len(expansion_text.strip()) > 100:
                    # Append expansion before conclusion or at end
                    if "## Conclusion" in final_essay:
                        parts = final_essay.split("## Conclusion", 1)
                        final_essay = f"{parts[0]}\n\n{expansion_text}\n\n## Conclusion{parts[1]}"
                    elif "### Sources & References" in final_essay:
                        parts = final_essay.split("### Sources & References", 1)
                        final_essay = f"{parts[0]}\n\n{expansion_text}\n\n### Sources & References{parts[1]}"
                    else:
                        final_essay = f"{final_essay}\n\n{expansion_text}"
            except Exception:
                # If continuation fails, safely preserve initial draft
                pass

        final_word_count = self.count_words(final_essay)

        # 6. Extract Essay Title if available (first H1 line)
        essay_title = topic
        for line in final_essay.splitlines():
            line_str = line.strip()
            if line_str.startswith("# ") and not line_str.startswith("## "):
                essay_title = line_str.replace("#", "").strip()
                break

        # 7. Append Word Count Transparency Reporting
        reporting_footnote = (
            f"\n\n---\n*Word count: ~{final_word_count} words (whitespace-delimited markdown). "
            f"Target: ~{self.TARGET_WORD_COUNT} words.*"
        )
        final_content = final_essay + reporting_footnote

        status_flag = "success" if has_context else "empty_kb"

        return AgentResponse(
            content=final_content,
            citations=citations,
            provider=llm_provider.provider_name,
            model=llm_provider.model_name,
            retrieved_count=len(citations),
            status=status_flag,
            skill=self.name,
            extra_metadata={
                "skill": self.name,
                "topic": topic,
                "essay_title": essay_title,
                "artifact_type": "markdown",
                "artifact_title": essay_title,
                "artifact_content": final_content,
                "word_count": final_word_count,
                "target_word_count": self.TARGET_WORD_COUNT,
                "counting_convention": "whitespace_delimited_markdown"
            }
        )
