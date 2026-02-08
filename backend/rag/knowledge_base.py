"""RAG knowledge base: semantic search over course materials using Supabase pgvector."""

import logging
from typing import Optional

from openai import OpenAI

from rag.document_processor import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Semantic search over embedded course materials."""

    def __init__(self, db, openai_api_key: str):
        self.db = db
        self.openai_client = OpenAI(api_key=openai_api_key)

    def _embed_query(self, query: str) -> list[float]:
        response = self.openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    async def search(
        self,
        query: str,
        match_count: int = 5,
        threshold: float = 0.5,
    ) -> list[dict]:
        """Search for relevant course material chunks.

        Returns list of {id, document_id, content, metadata, similarity}.
        """
        from database import search_chunks

        embedding = self._embed_query(query)
        results = await search_chunks(
            self.db,
            query_embedding=embedding,
            match_count=match_count,
            threshold=threshold,
        )
        logger.info(f"Knowledge search for '{query[:50]}...' returned {len(results)} results")
        return results

    async def get_context(self, query: str, max_chunks: int = 5) -> str:
        """Get formatted context string for the teaching agent."""
        results = await self.search(query, match_count=max_chunks)
        if not results:
            return ""

        context_parts = []
        for r in results:
            similarity = r.get('similarity', 0)
            content = r.get('content', '')
            context_parts.append(f"[Релевантность: {similarity:.2f}]\n{content}")

        return "\n\n---\n\n".join(context_parts)
