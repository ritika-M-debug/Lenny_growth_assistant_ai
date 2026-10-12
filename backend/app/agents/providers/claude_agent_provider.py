import os
import time
import logging
from typing import List, Dict, Any, Optional

from app.agents.base import (
    BaseLLMProvider,
    ProviderConfigurationError,
    ProviderUnavailableError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderError,
)
from app.core.config import settings

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger("lenny_assistant.llm.claude_agent")


class ClaudeAgentProvider(BaseLLMProvider):
    """
    Agent Provider integrating the Anthropic Claude Agent SDK framework.
    Handles authentication validation, session tool execution, and clear error diagnostics.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        raw_key = api_key or os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", "")
        self._api_key = raw_key.strip() if raw_key else ""
        self._model = (
            model
            or os.getenv("ANTHROPIC_MODEL")
            or getattr(settings, "ANTHROPIC_MODEL", None)
            or getattr(settings, "DEFAULT_CLOUD_MODEL", "claude-3-5-sonnet-20241022")
        )
        self._timeout = timeout if timeout is not None else getattr(settings, "ANTHROPIC_TIMEOUT", 60.0)

    @property
    def provider_name(self) -> str:
        return "claude-agent-sdk"

    @property
    def model_name(self) -> str:
        return self._model

    def validate_configuration(self) -> None:
        if not self._api_key or self._api_key.startswith("your_"):
            raise ProviderConfigurationError(
                "ANTHROPIC_API_KEY is required to use the Anthropic Claude Agent SDK. "
                "For local inference without an API key, set LLM_PROVIDER=ollama."
            )

    def check_health(self) -> Dict[str, Any]:
        if not self._api_key or self._api_key.startswith("your_"):
            return {
                "status": "unconfigured",
                "provider": self.provider_name,
                "model": self._model,
                "configured": False,
                "message": "ANTHROPIC_API_KEY is not set for Claude Agent SDK."
            }
        return {
            "status": "configured",
            "provider": self.provider_name,
            "model": self._model,
            "configured": True,
            "message": f"Claude Agent SDK is configured with model '{self._model}'."
        }

    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        self.validate_configuration()

        if anthropic is None:
            try:
                import anthropic as _anthropic
                globals()["anthropic"] = _anthropic
            except ImportError as e:
                raise ProviderConfigurationError("Anthropic SDK is not installed.") from e

        start_time = time.time()
        try:
            client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout)

            anthropic_messages = []
            for msg in messages:
                if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                    anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

            if not anthropic_messages:
                anthropic_messages = [{"role": "user", "content": "Hello"}]

            kwargs = {
                "model": self._model,
                "max_tokens": 2048,
                "messages": anthropic_messages,
                "temperature": temperature
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = client.messages.create(**kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Claude Agent SDK completion succeeded [duration=%dms]", duration_ms)
            return response.content[0].text.strip()

        except anthropic.AuthenticationError as e:
            raise ProviderAuthenticationError("Claude Agent SDK authentication failed (401).") from e
        except anthropic.RateLimitError as e:
            raise ProviderRateLimitError("Claude Agent SDK rate limit reached (429).") from e
        except anthropic.APITimeoutError as e:
            raise ProviderTimeoutError(f"Claude Agent SDK timed out after {self._timeout}s.") from e
        except anthropic.APIConnectionError as e:
            raise ProviderUnavailableError("Could not connect to Anthropic Cloud service.") from e
        except Exception as e:
            raise ProviderError(f"Claude Agent SDK generation error: {e}") from e
