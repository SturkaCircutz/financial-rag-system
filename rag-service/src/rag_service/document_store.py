import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_service.documents import Chunk, ChunkMetadataFilter, Document, safe_name
from rag_service.models import SourceFilter


LOCAL_STORE_ROOT = Path(__file__).resolve().parents[2] / "data" / "processed"


@dataclass(frozen=True)
class StoreWriteResult:
    manifest_path: Path
    raw_document_count: int
    parsed_document_count: int
    chunk_count: int
    embedding_count: int


class LocalDocumentStore:
    def __init__(self, root: Path = LOCAL_STORE_ROOT):
        self.root = root

    def persist(self, documents: list[Document], chunks: list[Chunk]) -> StoreWriteResult:
        manifest = self._load_manifest()
        updated_at = current_timestamp()

        for document in documents:
            self._persist_document(document, manifest, updated_at)
        for chunk in chunks:
            self._persist_chunk(chunk, manifest, updated_at)

        manifest["updated_at"] = updated_at
        self._write_json(self.manifest_path, manifest)
        return StoreWriteResult(
            manifest_path=self.manifest_path,
            raw_document_count=len(manifest["raw_documents"]),
            parsed_document_count=len(manifest["parsed_documents"]),
            chunk_count=len(manifest["chunks"]),
            embedding_count=len(manifest["embeddings"]),
        )

    def query_chunks(self, filters: ChunkMetadataFilter = ChunkMetadataFilter()) -> list[Chunk]:
        manifest = self._load_manifest()
        chunks: list[Chunk] = []
        for item in manifest["chunks"].values():
            chunk_path = self.root / item["path"]
            if not chunk_path.exists():
                continue
            chunk = chunk_from_record(json.loads(chunk_path.read_text(encoding="utf-8")))
            if chunk_matches_filter(chunk, filters):
                chunks.append(chunk)
        return sorted(chunks, key=lambda chunk: (chunk.ticker, chunk.source_type.value, chunk.chunk_id))

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifests" / "ingestion_manifest.json"

    def _persist_document(self, document: Document, manifest: dict[str, Any], updated_at: str) -> None:
        raw_key = document.storage_key()
        parsed_key = document.source_id
        raw_path = Path("raw_documents") / document.source_type.value.lower() / f"{safe_name(raw_key)}.json"
        parsed_path = Path("parsed_documents") / document.source_type.value.lower() / f"{safe_name(parsed_key)}.json"
        metadata = document.canonical_metadata(ingested_at=updated_at)

        raw_record = {
            "storage_kind": "raw_document",
            "source_id": document.source_id,
            "source_type": document.source_type.value,
            "ticker": document.ticker,
            "text": document.text,
            "content_hash": document.content_hash,
            "metadata": metadata,
        }
        parsed_record = {
            "storage_kind": "parsed_document",
            "source_id": document.source_id,
            "source_type": document.source_type.value,
            "ticker": document.ticker,
            "title": document.title,
            "url": document.url,
            "section": document.section,
            "text": document.text,
            "content_hash": document.content_hash,
            "metadata": metadata,
        }

        self._write_json(self.root / raw_path, raw_record)
        self._write_json(self.root / parsed_path, parsed_record)
        manifest["raw_documents"][raw_key] = manifest_entry(
            raw_path,
            document.source_id,
            document.content_hash,
            updated_at,
        )
        manifest["parsed_documents"][parsed_key] = manifest_entry(
            parsed_path,
            document.source_id,
            document.content_hash,
            updated_at,
        )

    def _persist_chunk(self, chunk: Chunk, manifest: dict[str, Any], updated_at: str) -> None:
        chunk_key = chunk.chunk_id
        embedding_key = chunk.chunk_id
        chunk_path = Path("chunks") / chunk.source_type.value.lower() / f"{safe_name(chunk.storage_key())}.json"
        embedding_path = Path("embeddings") / chunk.source_type.value.lower() / f"{safe_name(chunk.storage_key())}.json"
        metadata = {**chunk.metadata, "ingested_at": updated_at}
        chunk_record = {**asdict(chunk), "source_type": chunk.source_type.value, "metadata": metadata}
        embedding_record = {
            "storage_kind": "embedding",
            "chunk_id": chunk.chunk_id,
            "source_id": chunk.source_id,
            "source_type": chunk.source_type.value,
            "content_hash": chunk.content_hash,
            "embedding_model": "local-hash-v0",
            "vector": local_hash_embedding(chunk.content_hash),
            "metadata": metadata,
        }

        self._write_json(self.root / chunk_path, chunk_record)
        self._write_json(self.root / embedding_path, embedding_record)
        manifest["chunks"][chunk_key] = manifest_entry(
            chunk_path,
            chunk.source_id,
            chunk.content_hash,
            updated_at,
        )
        manifest["embeddings"][embedding_key] = manifest_entry(
            embedding_path,
            chunk.source_id,
            chunk.content_hash,
            updated_at,
        )

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return empty_manifest()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        for key in ("raw_documents", "parsed_documents", "chunks", "embeddings"):
            manifest.setdefault(key, {})
        return manifest

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": "",
        "raw_documents": {},
        "parsed_documents": {},
        "chunks": {},
        "embeddings": {},
    }


def manifest_entry(path: Path, source_id: str, hash_value: str, updated_at: str) -> dict[str, str]:
    return {
        "path": path.as_posix(),
        "source_id": source_id,
        "content_hash": hash_value,
        "updated_at": updated_at,
    }


def chunk_from_record(record: dict[str, Any]) -> Chunk:
    return Chunk(
        source_id=record["source_id"],
        chunk_id=record["chunk_id"],
        ticker=record["ticker"],
        source_type=SourceFilter(record["source_type"]),
        title=record["title"],
        url=record["url"],
        section=record["section"],
        text=record["text"],
        content_hash=record["content_hash"],
        chunk_index=record["chunk_index"],
        metadata=record.get("metadata", {}),
    )


def chunk_matches_filter(chunk: Chunk, filters: ChunkMetadataFilter) -> bool:
    metadata = chunk.metadata
    if filters.tickers and chunk.ticker.upper() not in {ticker.upper() for ticker in filters.tickers}:
        return False
    if filters.source_types and chunk.source_type not in filters.source_types:
        return False
    if filters.form_types and metadata.get("form_type", "").upper() not in {
        form.upper() for form in filters.form_types
    }:
        return False
    if filters.sections and chunk.section.casefold() not in {section.casefold() for section in filters.sections}:
        return False
    if filters.fiscal_periods and fiscal_period(metadata).casefold() not in {
        period.casefold() for period in filters.fiscal_periods
    }:
        return False
    if filters.published_after or filters.published_before:
        published_at = parse_timestamp(metadata.get("published_at", ""))
        if published_at is None:
            return False
        if filters.published_after and published_at < parse_timestamp(filters.published_after):
            return False
        if filters.published_before and published_at > parse_timestamp(filters.published_before):
            return False
    return True


def fiscal_period(metadata: dict[str, str]) -> str:
    if metadata.get("period"):
        return metadata["period"]
    return " ".join(value for value in (metadata.get("fiscal_year", ""), metadata.get("fiscal_quarter", "")) if value)


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_hash_embedding(hash_value: str, dimensions: int = 8) -> list[float]:
    return [
        round(int(hash_value[index:index + 4], 16) / 65535, 6)
        for index in range(0, dimensions * 4, 4)
    ]
