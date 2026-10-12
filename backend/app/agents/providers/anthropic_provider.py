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

logger = logging.getLogger("lenny_assistant.llm.anthropic")


class AnthropicLLMProvider(BaseLLMProvider):
    """
    Cloud Agent Provider using Anthropic Claude API.
    Handles authentication validation, bounded retries on transient errors, and robust error classification.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
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
        self._max_retries = max_retries if max_retries is not None else getattr(settings, "ANTHROPIC_MAX_RETRIES", 2)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def validate_configuration(self) -> None:
        """Validates that a non-empty, non-placeholder API key is set."""
        if not self._api_key or self._api_key.startswith("your_") or self._api_key == "placeholder":
            raise ProviderConfigurationError(
                "ANTHROPIC_API_KEY is not configured or contains a placeholder. "
                "Please set a valid ANTHROPIC_API_KEY in backend/.env, or set LLM_PROVIDER=ollama for local inference."
            )

    def check_health(self) -> Dict[str, Any]:
        """
        Diagnostic probe to verify provider configuration.
        Does NOT expose the secret API key.
        """
        if not self._api_key or self._api_key.startswith("your_"):
            return {
                "status": "unconfigured",
                "provider": self.provider_name,
                "model": self._model,
                "configured": False,
                "message": (
                    "ANTHROPIC_API_KEY is missing or contains a placeholder. "
                    "To enable Claude inference, configure ANTHROPIC_API_KEY in backend/.env or use LLM_PROVIDER=ollama."
                )
            }

        masked_key = f"{self._api_key[:4]}...{self._api_key[-4:]}" if len(self._api_key) >= 10 else "***"
        return {
            "status": "configured",
            "provider": self.provider_name,
            "model": self._model,
            "configured": True,
            "key_preview": masked_key,
            "message": f"Anthropic cloud provider is configured with model '{self._model}'."
        }

    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Executes Claude API completion with validation, timeouts, and error handling.
        """
        self.validate_configuration()

        if anthropic is None:
            try:
                import anthropic as _anthropic
                globals()["anthropic"] = _anthropic
            except ImportError as e:
                raise ProviderConfigurationError(
                    "The 'anthropic' Python library is not installed. Please run: pip install anthropic"
                ) from e

        start_time = time.time()
        try:
            client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries
            )

            anthropic_messages = []
            for msg in messages:
                if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                    anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

            # Ensure at least one message is present
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
            logger.info("Anthropic completion succeeded [model=%s, duration=%dms]", self._model, duration_ms)

            if not response.content or not hasattr(response.content[0], "text"):
                raise ProviderError("Anthropic returned an empty response.")

            return response.content[0].text.strip()

        except anthropic.AuthenticationError as e:
            logger.error("Anthropic authentication failed (401)")
            raise ProviderAuthenticationError(
                "Anthropic API authentication failed. Please verify that your ANTHROPIC_API_KEY is valid and active."
            ) from e

        except anthropic.RateLimitError as e:
            logger.warning("Anthropic rate limit reached (429)")
            raise ProviderRateLimitError(
                "Anthropic API rate limit exceeded. Please wait a moment before sending another message."
            ) from e

        except anthropic.APITimeoutError as e:
            logger.error("Anthropic request timed out after %ss", self._timeout)
            raise ProviderTimeoutError(
                f"Anthropic API request timed out after {self._timeout} seconds."
            ) from e

        except anthropic.APIConnectionError as e:
            logger.error("Anthropic connection failed: %s", e)
            raise ProviderUnavailableError(
                "Could not connect to Anthropic API. Please check your network connection."
            ) from e

        except anthropic.APIStatusError as e:
            logger.error("Anthropic returned status %d", e.status_code)
            raise ProviderError(
                f"Anthropic API returned error status {e.status_code}."
            ) from e

        except ProviderError:
            raise

        except Exception as e:
            logger.error("Anthropic generation failed: %s", e)
            raise ProviderError(f"Anthropic request failed: {e}") from e
