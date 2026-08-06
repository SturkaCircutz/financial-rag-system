from dataclasses import dataclass
from typing import Protocol

from rag_service.chunking import SourceChunk, chunk_documents
from rag_service.document_store import LocalDocumentStore, StoreWriteResult
from rag_service.documents import content_hash, current_timestamp
from rag_service.corpus import EvidenceDocument, documents_for
from rag_service.models import SourceFilter
from rag_service.state import AgentResult


@dataclass(frozen=True)
class SourceManifest:
    source_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    content_hash: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class ChunkPointer:
    source_id: str
    chunk_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    content_hash: str
    chunk_index: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class SourceMemoryResult:
    manifests: list[SourceManifest]
    chunk_pointers: list[ChunkPointer]
    chunks: list[AgentResult]
    store_write: StoreWriteResult | None = None


class SourceMemory(Protocol):
    def collect(self, source_type: SourceFilter, tickers: list[str]) -> SourceMemoryResult:
        pass


class LocalSourceMemory:
    def __init__(self, store: LocalDocumentStore | None = None):
        self._store = store or LocalDocumentStore()

    def collect(self, source_type: SourceFilter, tickers: list[str]) -> SourceMemoryResult:
        documents = documents_for(source_type, tickers)
        ingested_at = current_timestamp()
        chunks = chunk_documents(documents, ingested_at=ingested_at)
        store_write = self._store.persist(documents, chunks)
        return SourceMemoryResult(
            manifests=[manifest_for(document, ingested_at=ingested_at) for document in documents],
            chunk_pointers=[pointer_for(chunk) for chunk in chunks],
            chunks=[agent_result_for(chunk) for chunk in chunks],
            store_write=store_write,
        )


def manifest_for(document: EvidenceDocument, ingested_at: str | None = None) -> SourceManifest:
    return SourceManifest(
        source_id=document.source_id,
        ticker=document.ticker,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        section=document.section,
        content_hash=content_hash(document.text),
        metadata=document.canonical_metadata(ingested_at=ingested_at),
    )


def pointer_for(chunk: SourceChunk) -> ChunkPointer:
    return ChunkPointer(
        source_id=chunk.source_id,
        chunk_id=chunk.chunk_id,
        ticker=chunk.ticker,
        source_type=chunk.source_type,
        title=chunk.title,
        url=chunk.url,
        section=chunk.section,
        content_hash=chunk.content_hash,
        chunk_index=chunk.chunk_index,
        metadata=dict(chunk.metadata),
    )


def agent_result_for(chunk: SourceChunk) -> AgentResult:
    return {
        "source_id": chunk.source_id,
        "chunk_id": chunk.chunk_id,
        "source_type": chunk.source_type,
        "status": "completed",
        "evidence_id": chunk.chunk_id,
        "title": chunk.title,
        "url": chunk.url,
        "section": chunk.section,
        "text": chunk.text,
        "content_hash": chunk.content_hash,
        "metadata": dict(chunk.metadata),
    }
