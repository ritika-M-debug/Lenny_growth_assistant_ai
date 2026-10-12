import pytest
from unittest.mock import MagicMock
from app.skills.ship_30_for_30 import Ship30For30Skill
from app.agents.rag_agent import RAGAgent
from app.agents.base import AgentResponse, SourceCitation
from app.agents.providers.mock_provider import MockLLMProvider
from app.knowledge_base.retrieval import RetrievalService
from app.models.conversation import Conversation, Message


def test_skill_activation_applicability():
    """Verify Ship30For30Skill triggers on essay-intent queries and ignores ordinary Q&A."""
    skill = Ship30For30Skill()

    # Applicable queries
    assert skill.is_applicable("Write an essay about improving user activation.")
    assert skill.is_applicable("Generate an essay about finding product-market fit.")
    assert skill.is_applicable("Explain growth loops through a structured essay.")
    assert skill.is_applicable("Turn insights from a relevant podcast episode into a practical essay.")
    assert skill.is_applicable("Write a Ship 30 for 30 essay on retention.")
    assert skill.is_applicable("Create an atomic essay about onboarding.")
    assert skill.is_applicable("Draft an essay on product discovery.")

    # Non-applicable conversational queries
    assert not skill.is_applicable("What are common approaches to finding product-market fit?")
    assert not skill.is_applicable("Who is Elena Verna?")
    assert not skill.is_applicable("Tell me about growth teams.")
    assert not skill.is_applicable("Hello!")
    assert not skill.is_applicable("")


def test_topic_extraction():
    """Verify topic extraction strips command phrasing and isolates the core topic."""
    skill = Ship30For30Skill()

    assert skill.extract_topic("Write an essay about improving user activation.") == "improving user activation"
    assert skill.extract_topic("Generate an essay on finding product-market fit.") == "finding product-market fit"
    assert skill.extract_topic("Explain growth loops through a structured essay.") == "growth loops"
    assert skill.extract_topic("Write a Ship 30 for 30 essay on customer retention") == "customer retention"
    assert skill.extract_topic("Draft an essay about viral acquisition loops") == "viral acquisition loops"


def test_word_count_calculation():
    """Verify word counting follows whitespace-delimited tokens and excludes footnote."""
    skill = Ship30For30Skill()

    sample = "# Title\n\nThis is a sample paragraph with ten words in total here."
    assert skill.count_words(sample) == 13

    # With word count reporting footnote
    with_footnote = sample + "\n\n---\n*Word count: ~13 words (whitespace-delimited markdown). Target: ~1,250 words.*"
    assert skill.count_words(with_footnote) == 13


def test_retrieval_context_passed_to_skill(db_session):
    """Verify retrieved transcript context and citations are supplied to the essay prompt."""
    skill = Ship30For30Skill()
    mock_retrieval = MagicMock(spec=RetrievalService)
    mock_retrieval.retrieve_context.return_value = [
        {
            "content": "Todd Jackson discusses PMF frameworks and customer interviews.",
            "similarity_score": 0.85,
            "metadata": {
                "title": "A framework for finding product-market fit | Todd Jackson",
                "guest": "Todd Jackson",
                "source_type": "podcast",
                "source_url": "https://www.youtube.com/watch?v=yc1Uwhfxacs&t=1014s",
                "publication_date": "2024-04-11"
            }
        }
    ]
    mock_retrieval.format_context_for_prompt.return_value = (
        "--- Source [1]: A framework for finding product-market fit | Todd Jackson\n"
        "Todd Jackson discusses PMF frameworks and customer interviews."
    )

    captured_prompt = {}
    class CapturingMockLLM(MockLLMProvider):
        def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
            captured_prompt["system"] = system_prompt
            captured_prompt["messages"] = messages
            return super().generate_chat_response(messages, system_prompt, temperature)

    provider = CapturingMockLLM()
    response = skill.execute(
        user_message="Write an essay about product-market fit",
        llm_provider=provider,
        retrieval_service=mock_retrieval
    )

    # Verifications
    mock_retrieval.retrieve_context.assert_called_once()
    assert "REFERENCE TRANSCRIPT MATERIAL" in captured_prompt["system"]
    assert "Todd Jackson discusses PMF frameworks" in captured_prompt["system"]
    assert response.skill == "ship_30_for_30"
    assert len(response.citations) == 1
    assert response.citations[0].author == "Todd Jackson"
    assert response.citations[0].source_url == "https://www.youtube.com/watch?v=yc1Uwhfxacs&t=1014s"
    assert "Word count:" in response.content


def test_empty_knowledge_base_behavior(db_session):
    """Verify empty knowledge base returns empty_kb status and explicit disclaimer."""
    skill = Ship30For30Skill()
    mock_retrieval = MagicMock(spec=RetrievalService)
    mock_retrieval.retrieve_context.return_value = []
    mock_retrieval.format_context_for_prompt.return_value = ""

    provider = MockLLMProvider()
    response = skill.execute(
        user_message="Write an essay about quantum computing in biotech",
        llm_provider=provider,
        retrieval_service=mock_retrieval
    )

    assert response.status == "empty_kb"
    assert len(response.citations) == 0
    assert response.skill == "ship_30_for_30"
    assert "No specific podcast transcript passages were found" in response.content


def test_ordinary_chat_requests_unaffected(db_session):
    """Verify standard questions bypass the essay skill and use conversational Q&A."""
    agent = RAGAgent(db=db_session, provider=MockLLMProvider())
    
    # Standard question
    resp = agent.run("What are common approaches to finding product-market fit?")
    
    assert resp.skill is None
    assert "Word count:" not in resp.content


def test_conversation_api_essay_persistence(client):
    """Verify requesting an essay via the API persists the essay and metadata in PostgreSQL."""
    # 1. Create Conversation
    c_res = client.post("/api/conversations", json={"title": "Essay Test"})
    assert c_res.status_code == 201
    conv_id = c_res.json()["id"]

    # 2. Send Essay Request
    m_res = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Write an essay about improving user activation."}
    )
    assert m_res.status_code == 201
    data = m_res.json()

    assert data["role"] == "assistant"
    assert "# The Modern Growth Playbook" in data["content"]
    assert "Word count:" in data["content"]

    # 3. Retrieve conversation and verify persistence
    get_res = client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 2
    assert messages[1]["metadata_json"]["skill"] == "ship_30_for_30"
    assert messages[1]["metadata_json"]["word_count"] > 0


def test_model_failure_handling_in_essay(db_session):
    """Verify model failures during essay generation are handled gracefully."""
    class FailingProvider(MockLLMProvider):
        def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
            raise TimeoutError("Ollama service timed out after 120s")

    agent = RAGAgent(db=db_session, provider=FailingProvider())
    
    with pytest.raises(TimeoutError):
        agent.run("Write an essay about onboarding")
