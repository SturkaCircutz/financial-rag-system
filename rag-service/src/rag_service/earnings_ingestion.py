import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rag_service.models import SourceFilter
from rag_service.sec_ingestion import slugify


@dataclass(frozen=True)
class LocalEarningsSource:
    source_id: str
    ticker: str
    title: str
    fiscal_quarter: str
    fiscal_year: str
    call_date: str
    source_url: str
    source_kind: str
    file_path: str


@dataclass(frozen=True)
class EarningsSegment:
    transcript_segment: str
    speaker: str
    role: str
    topic: str
    text: str


@dataclass(frozen=True)
class IngestedEarningsDocument:
    source_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    metadata: dict[str, str]


EARNINGS_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "earnings"
FIELD_PATTERN = re.compile(r"^(SEGMENT|SPEAKER|ROLE|TOPIC):\s*(.+)$", re.IGNORECASE)


class LocalEarningsIngestor:
    def __init__(
        self,
        sources: tuple[LocalEarningsSource, ...] | None = None,
        data_root: Path = EARNINGS_DATA_ROOT,
        manifest_path: Path | None = None,
    ):
        self._data_root = data_root
        self._sources = sources if sources is not None else load_local_earnings_sources(manifest_path or data_root / "manifest.json")

    def ingest(self, tickers: list[str], latest_only: bool = False) -> list[IngestedEarningsDocument]:
        ticker_set = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
        sources = [source for source in self._sources if source.ticker in ticker_set]
        if latest_only:
            sources = latest_sources_by_ticker(sources)
        return [
            document
            for source in sources
            for document in self._documents_for_source(source)
        ]

    def _documents_for_source(self, source: LocalEarningsSource) -> list[IngestedEarningsDocument]:
        source_text = self._read_source_text(source)
        return [
            IngestedEarningsDocument(
                source_id=source_id_for_segment(source, segment),
                ticker=source.ticker,
                source_type=SourceFilter.EARNINGS,
                title=source.title,
                url=f"{source.source_url}#{slugify(segment.transcript_segment)}",
                section=segment.transcript_segment,
                text=segment.text,
                metadata={
                    "fiscal_quarter": source.fiscal_quarter,
                    "fiscal_year": source.fiscal_year,
                    "call_date": source.call_date,
                    "speaker": segment.speaker,
                    "role": segment.role,
                    "topic": segment.topic,
                    "source_url": source.source_url,
                    "source_kind": source.source_kind,
                    "transcript_segment": segment.transcript_segment,
                    "source_path": source.file_path,
                },
            )
            for segment in parse_earnings_segments(source_text)
        ]

    def _read_source_text(self, source: LocalEarningsSource) -> str:
        path = self._data_root / source.file_path
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Local earnings file not found: {path}") from exc


def load_local_earnings_sources(manifest_path: Path) -> tuple[LocalEarningsSource, ...]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest.get("sources", [])
    return tuple(local_earnings_source_from_manifest(item) for item in sources)


def local_earnings_source_from_manifest(item: dict[str, str]) -> LocalEarningsSource:
    return LocalEarningsSource(
        source_id=item["source_id"],
        ticker=item["ticker"].strip().upper(),
        title=item["title"],
        fiscal_quarter=item["fiscal_quarter"],
        fiscal_year=item["fiscal_year"],
        call_date=item["call_date"],
        source_url=item["source_url"],
        source_kind=item["source_kind"],
        file_path=item["file_path"],
    )


def parse_earnings_segments(text: str) -> list[EarningsSegment]:
    segments: list[EarningsSegment] = []
    current: dict[str, str] = {}
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = FIELD_PATTERN.match(line)
        if match:
            field = match.group(1).lower()
            value = match.group(2).strip()
            if field == "segment" and current:
                append_segment(segments, current, current_lines)
                current = {}
                current_lines = []
            current[field] = value
            continue

        current_lines.append(line)

    if current:
        append_segment(segments, current, current_lines)
    return segments


def append_segment(
    segments: list[EarningsSegment],
    current: dict[str, str],
    current_lines: list[str],
) -> None:
    segments.append(
        EarningsSegment(
            transcript_segment=current.get("segment", "Unknown"),
            speaker=current.get("speaker", "Unknown"),
            role=current.get("role", "Unknown"),
            topic=current.get("topic", "Unknown"),
            text=" ".join(current_lines),
        )
    )


def latest_sources_by_ticker(sources: list[LocalEarningsSource]) -> list[LocalEarningsSource]:
    latest: dict[str, LocalEarningsSource] = {}
    for source in sources:
        existing = latest.get(source.ticker)
        if existing is None or parse_date(source.call_date) > parse_date(existing.call_date):
            latest[source.ticker] = source
    return list(latest.values())


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def source_id_for_segment(source: LocalEarningsSource, segment: EarningsSegment) -> str:
    return f"earnings-{source.ticker.lower()}-{source.fiscal_year}-{source.fiscal_quarter.lower()}-{slugify(segment.topic)}"
