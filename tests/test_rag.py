"""RAG chunking tests (engine itself requires the optional chromadb extra)."""

from vforge.rag.engine import chunk_text


def test_short_text_single_chunk():
    assert chunk_text("hello world", 100, 10) == ["hello world"]


def test_empty_text_no_chunks():
    assert chunk_text("   ", 100, 10) == []


def test_long_text_chunks_with_overlap():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(text, 200, 50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    # full coverage: every word appears somewhere
    joined = " ".join(chunks)
    assert "word0" in joined and "word199" in joined
