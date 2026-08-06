import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rag_service.models import SourceFilter


SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class Document:
    source_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
    company_name: str = ""
    published_at: str = ""
    ingested_at: str = ""
    period: str = ""
    provider: str = ""

    @property
    def content_hash(self) -> str:
        return content_hash(self.text)

    def canonical_metadata(self, ingested_at: str | None = None) -> dict[str, str]:
        metadata = dict(self.metadata)
        fiscal_period = " ".join(
            part
            for part in (
                metadata.get("fiscal_year", ""),
                metadata.get("fiscal_quarter", ""),
            )
            if part
        )
        canonical = {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "ticker": self.ticker,
            "company_name": self.company_name or metadata.get("company_name", ""),
            "published_at": (
                self.published_at
                or metadata.get("published_at", "")
                or metadata.get("filing_date", "")
                or metadata.get("call_date", "")
            ),
            "ingested_at": ingested_at or self.ingested_at or metadata.get("ingested_at", current_timestamp()),
            "document_url": self.url,
            "document_title": self.title,
            "section": self.section,
            "period": self.period or metadata.get("period", "") or metadata.get("report_period", "") or fiscal_period,
            "provider": (
                self.provider
                or metadata.get("provider", "")
                or metadata.get("publisher", "")
                or metadata.get("source_kind", "")
                or f"local-{self.source_type.value.lower()}"
            ),
            "content_hash": self.content_hash,
        }
        return {**metadata, **canonical}

    def storage_key(self) -> str:
        return stable_storage_key(self.source_id, self.content_hash)


@dataclass(frozen=True)
class Chunk:
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
    metadata: dict[str, str]

    def storage_key(self) -> str:
        return stable_storage_key(self.chunk_id, self.content_hash)


@dataclass(frozen=True)
class ChunkMetadataFilter:
    tickers: tuple[str, ...] = ()
    source_types: tuple[SourceFilter, ...] = ()
    published_after: str | None = None
    published_before: str | None = None
    form_types: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()
    fiscal_periods: tuple[str, ...] = ()


def metadata_for_chunk(
    document: Document,
    chunk_id: str,
    chunk_text: str,
    ingested_at: str | None = None,
) -> dict[str, str]:
    metadata = document.canonical_metadata(ingested_at=ingested_at)
    metadata["chunk_id"] = chunk_id
    metadata["content_hash"] = content_hash(chunk_text)
    return metadata


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stable_storage_key(identifier: str, hash_value: str) -> str:
    return f"{safe_name(identifier)}--{hash_value[:12]}"


def safe_name(value: str) -> str:
    safe = SLUG_PATTERN.sub("-", value).strip("-")
    return safe or "item"
