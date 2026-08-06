import re

from rag_service.documents import Chunk, Document, content_hash, metadata_for_chunk
from rag_service.models import SourceFilter

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
PARAGRAPH_PATTERN = re.compile(r"\n\s*\n+")

SourceChunk = Chunk


def chunk_documents(
    documents: list[Document],
    max_tokens: int = 24,
    overlap_tokens: int = 6,
    ingested_at: str | None = None,
) -> list[Chunk]:
    return [
        chunk
        for document in documents
        for chunk in chunk_document(
            document,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            ingested_at=ingested_at,
        )
    ]


def chunk_document(
    document: Document,
    max_tokens: int = 24,
    overlap_tokens: int = 6,
    ingested_at: str | None = None,
) -> list[Chunk]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative")
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    if document.source_type == SourceFilter.NEWS:
        return chunk_news_document(document, max_tokens=max_tokens, ingested_at=ingested_at)
    if document.source_type == SourceFilter.EARNINGS:
        return chunk_earnings_document(document, max_tokens=max_tokens, ingested_at=ingested_at)
    return chunk_sec_document(
        document,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
        ingested_at=ingested_at,
    )


def chunk_sec_document(
    document: Document,
    max_tokens: int = 24,
    overlap_tokens: int = 6,
    ingested_at: str | None = None,
) -> list[Chunk]:
    tokens = tokenize(document.text)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_text = " ".join(tokens[start:end])
        chunks.append(build_chunk(document, chunk_text, len(chunks) + 1, ingested_at=ingested_at))
        if end == len(tokens):
            break
        start = end - overlap_tokens
    return chunks


def chunk_news_document(
    document: Document,
    max_tokens: int = 96,
    ingested_at: str | None = None,
) -> list[Chunk]:
    paragraphs = split_paragraphs(document.text)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    for paragraph in paragraphs:
        tokens = tokenize(paragraph)
        if len(tokens) <= max_tokens:
            chunks.append(
                build_chunk(
                    document,
                    normalize_whitespace(paragraph),
                    len(chunks) + 1,
                    ingested_at=ingested_at,
                )
            )
            continue

        for chunk_text in token_windows(tokens, max_tokens=max_tokens, overlap_tokens=0):
            chunks.append(build_chunk(document, chunk_text, len(chunks) + 1, ingested_at=ingested_at))
    return chunks


def chunk_earnings_document(
    document: Document,
    max_tokens: int = 128,
    ingested_at: str | None = None,
) -> list[Chunk]:
    tokens = tokenize(document.text)
    if not tokens:
        return []
    if len(tokens) <= max_tokens:
        return [build_chunk(document, normalize_whitespace(document.text), 1, ingested_at=ingested_at)]
    return [
        build_chunk(document, chunk_text, index, ingested_at=ingested_at)
        for index, chunk_text in enumerate(token_windows(tokens, max_tokens=max_tokens, overlap_tokens=0), start=1)
    ]


def build_chunk(
    document: Document,
    chunk_text: str,
    chunk_index: int,
    ingested_at: str | None = None,
) -> Chunk:
    chunk_id = f"{document.source_id}#chunk-{chunk_index:03d}"
    return Chunk(
        source_id=document.source_id,
        chunk_id=chunk_id,
        ticker=document.ticker,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        section=document.section,
        text=chunk_text,
        content_hash=content_hash(chunk_text),
        chunk_index=chunk_index,
        metadata=metadata_for_chunk(document, chunk_id, chunk_text, ingested_at=ingested_at),
    )


def token_windows(tokens: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - overlap_tokens
    return chunks


def split_paragraphs(value: str) -> list[str]:
    return [
        normalize_whitespace(paragraph)
        for paragraph in PARAGRAPH_PATTERN.split(value.strip())
        if paragraph.strip()
    ]


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value)
