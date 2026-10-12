from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from app.agents.base import BaseLLMProvider, AgentResponse
from app.knowledge_base.retrieval import RetrievalService

class BaseSkill(ABC):
    """
    Abstract base class for modular agent skills in The Lenny Growth Assistant.
    Skills encapsulate specialized workflows (e.g. essay writing, artifact design)
    and are executed by RAGAgent when applicable.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the skill."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of skill behavior and capabilities."""
        pass

    @abstractmethod
    def is_applicable(self, user_message: str) -> bool:
        """Evaluates whether the skill should be activated for this message."""
        pass

    @abstractmethod
    def execute(
        self,
        user_message: str,
        llm_provider: BaseLLMProvider,
        retrieval_service: RetrievalService,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AgentResponse:
        """Executes the skill workflow and returns an AgentResponse."""
        pass
