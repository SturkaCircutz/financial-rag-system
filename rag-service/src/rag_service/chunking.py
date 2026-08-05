import hashlib
import re
from dataclasses import dataclass

from rag_service.corpus import EvidenceDocument
from rag_service.models import SourceFilter

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class SourceChunk:
    source_id: str
    chunk_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    content_hash: str
    chunk_index: int


def chunk_documents(
    documents: list[EvidenceDocument],
    max_tokens: int = 24,
    overlap_tokens: int = 6,
) -> list[SourceChunk]:
    return [
        chunk
        for document in documents
        for chunk in chunk_document(document, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    ]


def chunk_document(
    document: EvidenceDocument,
    max_tokens: int = 24,
    overlap_tokens: int = 6,
) -> list[SourceChunk]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative")
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    tokens = tokenize(document.text)
    if not tokens:
        return []

    chunks: list[SourceChunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_text = " ".join(tokens[start:end])
        chunk_index = len(chunks) + 1
        chunks.append(
            SourceChunk(
                source_id=document.source_id,
                chunk_id=f"{document.source_id}#chunk-{chunk_index:03d}",
                ticker=document.ticker,
                source_type=document.source_type,
                title=document.title,
                url=document.url,
                section=document.section,
                text=chunk_text,
                content_hash=content_hash(chunk_text),
                chunk_index=chunk_index,
            )
        )
        if end == len(tokens):
            break
        start = end - overlap_tokens
    return chunks


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value)


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
