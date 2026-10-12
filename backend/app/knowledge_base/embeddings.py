from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import math
import hashlib
import os
import httpx
from app.core.config import settings

class BaseEmbeddingProvider(ABC):
    """Abstract base class for configurable embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the vector dimension produced by this provider."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generates a normalized embedding vector for a single string."""
        pass

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of string inputs."""
        return [self.embed_text(t) for t in texts]


class DeterministicHashEmbeddingProvider(BaseEmbeddingProvider):
    """
    Zero-dependency, fast, local embedding generator.
    Produces deterministic 384-dimensional normalized n-gram feature vectors.
    Requires no internet connection, no API keys, and no heavy model downloads.
    """

    def __init__(self, vector_dim: int = 384):
        self._dim = vector_dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._dim
        
        vec = [0.0] * self._dim
        words = text.lower().split()
        
        # Word n-gram feature hashing
        for i, word in enumerate(words):
            # Unigram feature
            h_uni = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % self._dim
            vec[h_uni] += 1.0
            
            # Bigram feature if available
            if i > 0:
                bigram = f"{words[i-1]}_{word}"
                h_bi = int(hashlib.md5(bigram.encode('utf-8')).hexdigest(), 16) % self._dim
                vec[h_bi] += 1.5

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
            
        return vec


_cached_hash_provider: Optional["DeterministicHashEmbeddingProvider"] = None


def get_hash_provider() -> "DeterministicHashEmbeddingProvider":
    """Returns singleton instance of DeterministicHashEmbeddingProvider to save memory."""
    global _cached_hash_provider
    if _cached_hash_provider is None:
        _cached_hash_provider = DeterministicHashEmbeddingProvider()
    return _cached_hash_provider


class SentenceTransformersProvider(BaseEmbeddingProvider):
    """
    Local high-quality semantic embedding provider using SentenceTransformers (e.g. all-MiniLM-L6-v2).
    Uses class-level singleton model caching to avoid reloading multi-hundred-megabyte PyTorch models into memory.
    """
    _cached_model = None
    _cached_dim = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformersProvider._cached_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                try:
                    SentenceTransformersProvider._cached_model = SentenceTransformer(model_name, local_files_only=True)
                except Exception:
                    SentenceTransformersProvider._cached_model = SentenceTransformer(model_name)
                if hasattr(SentenceTransformersProvider._cached_model, "get_embedding_dimension"):
                    SentenceTransformersProvider._cached_dim = SentenceTransformersProvider._cached_model.get_embedding_dimension()
                else:
                    SentenceTransformersProvider._cached_dim = SentenceTransformersProvider._cached_model.get_sentence_embedding_dimension()

            except Exception as e:
                raise RuntimeError(f"Failed to initialize SentenceTransformer '{model_name}': {e}")

        self.model = SentenceTransformersProvider._cached_model
        self._dim = SentenceTransformersProvider._cached_dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        vec = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.tolist()


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local embedding provider using Ollama HTTP service."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or getattr(settings, "OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self._dim = 768  # Standard dimension for nomic-embed-text

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embedding"]
        except Exception as e:
            raise RuntimeError(f"Ollama embedding request failed: {e}")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Cloud embedding provider using OpenAI API."""

    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAIEmbeddingProvider.")
        self.model = model
        self._dim = 1536

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"input": text, "model": self.model}
        try:
            response = httpx.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding request failed: {e}")


def get_embedding_provider(provider_type: str = None) -> BaseEmbeddingProvider:
    """
    Factory function for instantiating the configured embedding provider.
    Priority order:
    1. Explicit provider_type parameter.
    2. Environment variable EMBEDDING_PROVIDER or settings.EMBEDDING_PROVIDER.
    3. If LLM_PROVIDER is mock (or EMBEDDING_PROVIDER is unset), defaults to DeterministicHashEmbeddingProvider
       to maintain low memory usage (<50MB vs ~500MB with PyTorch) on Render 512MB tier.
    """
    active_llm = (os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "ollama")).strip().lower()

    # When running with mock LLM (such as in free tier or tests), avoid loading heavy neural networks
    if active_llm == "mock" and not provider_type and not os.getenv("EMBEDDING_PROVIDER"):
        return get_hash_provider()

    raw_choice = provider_type or os.getenv("EMBEDDING_PROVIDER") or getattr(settings, "EMBEDDING_PROVIDER", "hash")
    provider_name = (raw_choice or "hash").strip().lower()

    if provider_name in ["hash", "local", "deterministic"]:
        return get_hash_provider()
    elif provider_name == "ollama":
        return OllamaEmbeddingProvider()
    elif provider_name in ["openai", "cloud"]:
        return OpenAIEmbeddingProvider()
    elif provider_name in ["sentence-transformers", "sentence_transformers"]:
        try:
            return SentenceTransformersProvider()
        except Exception as e:
            print(f"Notice: SentenceTransformers fallback to DeterministicHashEmbeddingProvider ({e})")
            return get_hash_provider()

    # Safe default fallback
    return get_hash_provider()
