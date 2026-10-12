from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class SourceCitation:
    source_number: int
    title: str
    source_type: str
    author: Optional[str] = None
    episode_title: Optional[str] = None
    publication_date: Optional[str] = None
    source_url: Optional[str] = None
    snippet: Optional[str] = None
    similarity_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AgentResponse:
    content: str
    citations: List[SourceCitation]
    provider: str
    model: str
    retrieved_count: int = 0
    status: str = "success"
    skill: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "content": self.content,
            "citations": [c.to_dict() for c in self.citations],
            "provider": self.provider,
            "model": self.model,
            "retrieved_count": self.retrieved_count,
            "status": self.status
        }
        if self.skill:
            data["skill"] = self.skill
        if self.extra_metadata:
            data.update(self.extra_metadata)
        return data


class ProviderError(RuntimeError):
    """Base error for LLM provider failures."""
    pass

class ProviderConfigurationError(ProviderError):
    """Raised when provider configuration or credentials are missing or invalid."""
    pass

class ProviderUnavailableError(ProviderError):
    """Raised when provider daemon or API endpoint cannot be reached."""
    pass

class ProviderModelNotFoundError(ProviderError):
    """Raised when configured model is not pulled or does not exist."""
    pass

class ProviderRateLimitError(ProviderError):
    """Raised when cloud API rate limit is reached."""
    pass

class ProviderAuthenticationError(ProviderError):
    """Raised when cloud API authentication fails."""
    pass

class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""
    pass


class BaseLLMProvider(ABC):
    """Abstract interface for LLM model providers (Ollama, Anthropic, Mock)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generates a text completion response given chat messages and system prompt."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Checks connectivity, model availability, and configuration status.
        Returns dict with status ('available', 'unavailable', 'misconfigured') and message.
        """
        pass
