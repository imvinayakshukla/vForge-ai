"""Optional RAG module (ChromaDB-backed). The framework runs fully without it."""

from vforge.rag.engine import RAGEngine, RAGError

__all__ = ["RAGEngine", "RAGError"]
