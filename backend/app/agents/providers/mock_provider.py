from typing import List, Dict, Optional
from app.agents.base import BaseLLMProvider

class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider for unit tests."""

    def __init__(self, model_name: str = "mock-agent-v1", custom_response: Optional[str] = None):
        self._model = model_name
        self.custom_response = custom_response
        self.is_mock = True

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        if self.custom_response:
            return self.custom_response

        user_query = messages[-1].get("content", "") if messages else "question"

        # Check if essay skill requested Ship 30 for 30 generation
        if system_prompt and "Ship 30 for 30" in system_prompt:
            has_sources = "REFERENCE TRANSCRIPT MATERIAL" in system_prompt and "--- Source [1]:" in system_prompt
            citation_note = (
                "As discussed on Lenny's Podcast by Todd Jackson in [Source 1], finding true product-market fit "
                "requires rigorous qualitative interviews paired with quantifiable retention dynamics."
                if has_sources
                else
                "> **Notice**: No specific podcast transcript passages were found matching this topic in the knowledge base. "
                "This essay synthesizes general product management principles, and does not cite specific Lenny's Podcast episodes."
            )
            
            # Construct a structured, multi-section mock atomic essay
            essay = f"""# The Modern Growth Playbook: How Top Teams Solve {user_query.replace("Write a comprehensive, ~1,250-word Ship 30 for 30-style essay on: ", "").strip("'")}

Most founders make the fatal mistake of optimizing top-of-funnel acquisition before solving core value delivery.

When acquisition scales prematurely, it merely pours water into a leaky bucket.
Retention is the only metric that guarantees enduring product defensibility.

## The Counterintuitive Reality

The conventional playbook tells you to double down on paid channels and viral referral loops.
In reality, unsustainable growth tactics inevitably break down without a sticky core experience.

{citation_note}

## Framework 1: The Core Mental Model

1. **Activation Velocity**: The speed at which a new user experiences the core product value.
2. **Value Exchange Threshold**: Delivering more tangible utility than the setup friction required.
3. **Retention Loops**: Ensuring natural triggers bring users back without artificial push notifications.

## Framework 2: Concrete Tactical Execution

To implement this framework inside your organization, execute these essential steps:
- Map every single step in your onboarding flow and measure exact drop-off points.
- Eliminate all unnecessary form fields, configuration barriers, and delays.
- Create interactive default templates so the user reaches the "aha moment" in seconds.

## Tactical Playbook: 5-Step Execution Guide

1. Audit your current customer conversion funnels using cohort analysis.
2. Conduct five direct customer interviews with churned users every single week.
3. Align product, marketing, and engineering around one shared North Star metric.
4. Ship rapid weekly experiments focused strictly on activation velocity.
5. Continuously measure 30-day retention curves before scaling ad spend.

## Conclusion

Sustainable growth is never an accident; it is the compounding output of deliberate product mechanics.
Focus relentlessly on customer delight, activation velocity, and foundational retention.

### Sources & References
- [Source 1]: A framework for finding product-market fit | Todd Jackson (First Round Capital)
"""
            return essay.strip()

        # Check if retrieved context was included in system prompt
        if system_prompt and "--- Source [1]:" in system_prompt:
            return (
                f"Based on Lenny's Podcast reference [Source 1], regarding '{user_query}': "
                "The core principle is focusing on user retention and core activation loops before scaling acquisition."
            )
        else:
            return (
                "No specific transcript context was retrieved from Lenny's knowledge base. "
                f"As general product management guidance for '{user_query}': Focus on defining clear North Star metrics "
                "and conducting rigorous user interviews."
            )

    def check_health(self) -> Dict[str, Any]:
        return {
            "status": "available",
            "provider": self.provider_name,
            "model": self.model_name,
            "message": "Mock test provider ready for hermetic evaluation."
        }
