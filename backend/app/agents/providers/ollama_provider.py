import time
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.agents.base import (
    BaseLLMProvider,
    ProviderUnavailableError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
    ProviderError,
)
from app.core.config import settings

logger = logging.getLogger("lenny_assistant.llm.ollama")


class OllamaLLMProvider(BaseLLMProvider):
    """
    Local LLM Provider using the local Ollama REST service.
    Implements health diagnostics, model presence verification, bounded retries, and clear error reporting.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self._base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._model = model or getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
        self._timeout = timeout if timeout is not None else getattr(settings, "OLLAMA_TIMEOUT", 60.0)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def check_health(self) -> Dict[str, Any]:
        """
        Verifies whether the Ollama daemon is reachable and whether the configured model is installed.
        Does NOT automatically trigger model downloads.
        """
        tags_url = f"{self._base_url}/api/tags"
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(tags_url)
                if res.status_code != 200:
                    return {
                        "status": "unavailable",
                        "provider": self.provider_name,
                        "model": self._model,
                        "base_url": self._base_url,
                        "reachable": False,
                        "message": f"Ollama daemon returned HTTP {res.status_code} at {tags_url}."
                    }

                data = res.json()
                installed_models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check for direct match or tag match (e.g., 'llama3.2:3b' or 'llama3.2:latest')
                model_base = self._model.split(":")[0]
                has_model = any(
                    self._model == m or m.startswith(f"{model_base}:")
                    for m in installed_models
                )

                if has_model:
                    return {
                        "status": "available",
                        "provider": self.provider_name,
                        "model": self._model,
                        "base_url": self._base_url,
                        "reachable": True,
                        "model_installed": True,
                        "message": f"Ollama is online with model '{self._model}' ready for inference.",
                        "installed_models": installed_models
                    }
                else:
                    return {
                        "status": "missing_model",
                        "provider": self.provider_name,
                        "model": self._model,
                        "base_url": self._base_url,
                        "reachable": True,
                        "model_installed": False,
                        "message": (
                            f"Ollama is running at {self._base_url}, but model '{self._model}' is not pulled. "
                            f"Run `ollama pull {self._model}` in your terminal to install it."
                        ),
                        "installed_models": installed_models
                    }
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return {
                "status": "unavailable",
                "provider": self.provider_name,
                "model": self._model,
                "base_url": self._base_url,
                "reachable": False,
                "message": (
                    f"Could not connect to Ollama at {self._base_url}. "
                    "Please verify that Ollama is installed and running (`ollama serve`)."
                )
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "provider": self.provider_name,
                "model": self._model,
                "base_url": self._base_url,
                "reachable": False,
                "message": f"Ollama health probe failed: {e}"
            }

    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Executes chat completion with timeout, bounded retries on transient errors, and error categorization.
        """
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system"] and content:
                formatted_messages.append({"role": role, "content": content})

        payload = {
            "model": self._model,
            "messages": formatted_messages,
            "options": {"temperature": temperature},
            "stream": False
        }

        start_time = time.time()
        max_attempts = 2  # 1 retry on transient network glitch

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(f"{self._base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    if not content:
                        raise ProviderError("Ollama returned an empty completion response.")

                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.info(
                        "Ollama completion succeeded [model=%s, duration=%dms, attempt=%d]",
                        self._model, duration_ms, attempt
                    )
                    return content.strip()

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt < max_attempts:
                    time.sleep(0.5)
                    continue
                logger.error("Ollama connection failed at %s: %s", self._base_url, e)
                raise ProviderUnavailableError(
                    f"Could not connect to local Ollama service at {self._base_url}. "
                    "Please verify that Ollama is installed and running (`ollama serve`)."
                ) from e

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning("Ollama model '%s' not found (404)", self._model)
                    raise ProviderModelNotFoundError(
                        f"Model '{self._model}' was not found in Ollama. "
                        f"Please pull it first by running `ollama pull {self._model}` in your terminal."
                    ) from e
                elif status_code in [502, 503, 504] and attempt < max_attempts:
                    time.sleep(1.0)
                    continue

                logger.error("Ollama returned HTTP error %d", status_code)
                raise ProviderError(f"Ollama returned HTTP error {status_code}.") from e

            except httpx.TimeoutException as e:
                logger.error("Ollama generation timed out after %ss", self._timeout)
                raise ProviderTimeoutError(
                    f"Ollama generation timed out after {self._timeout} seconds. "
                    "Consider increasing OLLAMA_TIMEOUT or using a smaller/quantized model."
                ) from e

            except ProviderError:
                raise

            except Exception as e:
                logger.error("Ollama generation failed: %s", e)
                raise ProviderError(f"Ollama generation failed: {e}") from e

        raise ProviderUnavailableError(f"Ollama request failed after {max_attempts} attempts.")
