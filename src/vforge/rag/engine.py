"""Optional retrieval-augmented generation backed by ChromaDB.

When ``rag.enabled`` is true, documents from ``rag.documents_dir`` are
chunked and indexed at startup, and every agent gains a ``search_knowledge``
tool. When disabled (the default) nothing is imported or indexed.

Requires the ``vforge[rag]`` extra (``pip install vforge[rag]``).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from vforge.agents.agent import ToolBinding
from vforge.config.models import RAGConfig
from vforge.providers.llm.base import ToolDef

logger = logging.getLogger(__name__)

_TEXT_SUFFIXES = {".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml", ".csv", ".html"}


class RAGError(RuntimeError):
    """Raised when the RAG module cannot start."""


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character chunks on whitespace boundaries."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            space = text.rfind(" ", start + chunk_size // 2, end)
            if space != -1:
                end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


class RAGEngine:
    """Indexes documents into Chroma and answers similarity queries."""

    def __init__(self, config: RAGConfig, app_dir: Path) -> None:
        self._config = config
        self._app_dir = app_dir
        try:
            import chromadb
        except ImportError as exc:
            raise RAGError(
                "RAG is enabled but 'chromadb' is not installed. Run: pip install 'vforge[rag]'"
            ) from exc

        if config.persist_directory:
            self._client = chromadb.PersistentClient(path=str(app_dir / config.persist_directory))
        else:
            self._client = chromadb.EphemeralClient()
        self._collection = self._client.get_or_create_collection(config.collection)

    async def index_documents(self) -> int:
        """Index all text documents under ``documents_dir``. Returns chunk count."""
        if not self._config.documents_dir:
            return 0
        docs_dir = self._app_dir / self._config.documents_dir
        if not docs_dir.is_dir():
            raise RAGError(f"rag.documents_dir does not exist: {docs_dir}")

        ids, texts, metadatas = [], [], []
        for path in sorted(docs_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, chunk in enumerate(
                chunk_text(text, self._config.chunk_size, self._config.chunk_overlap)
            ):
                digest = hashlib.sha256(f"{path}:{i}:{chunk}".encode()).hexdigest()[:16]
                ids.append(digest)
                texts.append(chunk)
                metadatas.append({"source": str(path.relative_to(docs_dir)), "chunk": i})

        if ids:
            # Chroma embeds with its default embedding function; upsert is idempotent.
            await asyncio.to_thread(
                self._collection.upsert, ids=ids, documents=texts, metadatas=metadatas
            )
        logger.info("RAG: indexed %d chunk(s) from %s", len(ids), docs_dir)
        return len(ids)

    async def query(self, question: str) -> str:
        result = await asyncio.to_thread(
            self._collection.query, query_texts=[question], n_results=self._config.top_k
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        if not documents:
            return "No relevant documents found."
        parts = [
            f"[{meta.get('source', '?')}#{meta.get('chunk', 0)}]\n{doc}"
            for doc, meta in zip(documents, metadatas)
        ]
        return "\n\n---\n\n".join(parts)

    def tool_binding(self) -> ToolBinding:
        async def executor(arguments: dict) -> str:
            question = arguments.get("query", "")
            if not question:
                return "ERROR: search_knowledge requires 'query'"
            return await self.query(question)

        return ToolBinding(
            definition=ToolDef(
                name="search_knowledge",
                description="Search the indexed knowledge base for relevant document excerpts.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            ),
            executor=executor,
        )
