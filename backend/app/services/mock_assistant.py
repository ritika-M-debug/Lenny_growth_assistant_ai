"""
Mock Assistant Service for Step 4 Prototype.
Decoupled service that generates mock responses without inventing fake citations or pretending to query LLMs.
"""

def generate_mock_assistant_response(user_content: str) -> str:
    """
    Generates a clearly labeled mock response for user messages.
    Can be replaced in Step 5 with RAG/LLM agent execution.
    """
    lower = user_content.lower()

    if "product-market fit" in lower or "pmf" in lower:
        return (
            "[DEMO MOCK RESPONSE - Step 4 Persistent Backend]\n\n"
            "Product-Market Fit (PMF) Key Principles:\n\n"
            "1. 40% Rule: At least 40% of surveyed users indicate they would be 'Very Disappointed' if the product was discontinued.\n"
            "2. Retention Stability: Cohort retention curves flatten out over time rather than dropping to zero.\n"
            "3. High Organic Pull: Word-of-mouth referral accounts for a significant portion of user acquisition."
        )
    elif "activation" in lower or "onboarding" in lower:
        return (
            "[DEMO MOCK RESPONSE - Step 4 Persistent Backend]\n\n"
            "User Activation Guidance:\n\n"
            "1. Identify your product's core 'Aha! Moment'.\n"
            "2. Streamline signup and onboarding to reduce time-to-value (TTV).\n"
            "3. Guide users directly to their first core milestone."
        )
    elif "growth loop" in lower or "loop" in lower:
        return (
            "[DEMO MOCK RESPONSE - Step 4 Persistent Backend]\n\n"
            "Growth Loop Framework:\n\n"
            "1. Viral Loops: Existing users invite new users as part of the core product workflow.\n"
            "2. Content/SEO Loops: User-generated content attracts organic search traffic.\n"
            "3. Paid Acquisition Loops: Revenue per customer funds customer acquisition marketing."
        )
    elif "interview" in lower or "research" in lower:
        return (
            "[DEMO MOCK RESPONSE - Step 4 Persistent Backend]\n\n"
            "User Interviewing Principles:\n\n"
            "1. Focus on past concrete actions rather than hypothetical promises.\n"
            "2. Identify manual workarounds users currently use.\n"
            "3. Allow the user to speak without leading their answers."
        )
    else:
        return (
            f"[DEMO MOCK RESPONSE - Step 4 Persistent Backend]\n\n"
            f"Received: '{user_content}'\n\n"
            "This response was stored and persisted in your PostgreSQL database! "
            "Real AI responses with transcript ingestion will be integrated in future steps."
        )
