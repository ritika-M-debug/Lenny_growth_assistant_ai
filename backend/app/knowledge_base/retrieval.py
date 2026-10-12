from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.knowledge_base.embeddings import get_embedding_provider, BaseEmbeddingProvider
from app.knowledge_base.vector_store import search_similar_chunks

class RetrievalService:
    """
    RAG Retrieval Service providing grounded chunk context for user queries.
    Independent of chat APIs and LLM generation layers.
    """

    def __init__(self, db: Session, embedding_provider: Optional[BaseEmbeddingProvider] = None):
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
        filter_guest: Optional[str] = None,
        filter_episode: Optional[str] = None,
        boost_terms: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves relevant grounded document chunks for a question/query.

        :param query: The user input text.
        :param top_k: Maximum number of relevant chunks to return (default 5).
        :param min_similarity: Minimum cosine similarity threshold (default 0.0).
        :param filter_guest: Optional guest name filter.
        :param filter_episode: Optional episode title filter.
        :param boost_terms: Optional list of keyword/topic terms to boost relevance scores.
        :return: List of chunk dictionary payloads with content, similarity_score, and grounded metadata.
        """
        if not query or not query.strip():
            return []

        # Auto-extract significant query keywords for relevance boosting
        if boost_terms is None:
            raw_words = query.strip().split()
            # Pick keywords of 4+ characters, ignoring common stop words
            common_stops = {"what", "when", "where", "which", "about", "could", "would", "should", "their", "there", "these", "those"}
            boost_terms = [w.strip("?,.!") for w in raw_words if len(w) >= 4 and w.lower() not in common_stops]

        # 1. Generate query embedding using configured provider
        query_embedding = self.embedding_provider.embed_text(query.strip())

        # 2. Search PostgreSQL database for top-k similar chunks
        results = search_similar_chunks(
            db=self.db,
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_guest=filter_guest,
            filter_episode=filter_episode,
            boost_terms=boost_terms
        )

        return results

    def format_context_for_prompt(self, results: List[Dict[str, Any]]) -> str:
        """
        Formats retrieved search results into a clean reference context string
        suitable for feeding to an LLM prompt with strict grounded source citations.
        """
        if not results:
            return "No relevant knowledge base context found."

        context_blocks = []
        for idx, res in enumerate(results, start=1):
            meta = res.get("metadata", {})
            title = meta.get("title", "Untitled Document")
            source_type = meta.get("source_type", "podcast")
            author = meta.get("guest") or meta.get("author")
            episode = meta.get("episode_title")
            timestamp = meta.get("timestamp")
            source_url = meta.get("source_url") or meta.get("youtube_url")

            header_parts = [f"Source [{idx}]: {title}"]
            if author:
                header_parts.append(f"Guest/Speaker: {author}")
            if episode and episode != title:
                header_parts.append(f"Episode: {episode}")
            if timestamp:
                header_parts.append(f"Timestamp: {timestamp}")
            if source_url:
                header_parts.append(f"URL: {source_url}")
            header_parts.append(f"Type: {source_type}")

            header_str = " | ".join(header_parts)
            content = res.get("content", "").strip()

            block = f"--- {header_str} ---\n{content}"
            context_blocks.append(block)

        return "\n\n".join(context_blocks)
