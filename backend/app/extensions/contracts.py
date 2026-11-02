from typing import Protocol, Sequence

class EmbeddingProvider(Protocol):
    """Future adapter: sentence-transformers or a remote embedding API."""
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

class DocumentTextExtractor(Protocol):
    """Future adapters: pdfplumber and python-docx. No extraction in MVP."""
    def extract(self, content: bytes, media_type: str) -> str: ...

class LanguageModelProvider(Protocol):
    """Future LLM API boundary; keys and network calls are absent in MVP."""
    def complete(self, prompt: str) -> str: ...
