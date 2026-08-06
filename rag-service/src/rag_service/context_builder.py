from dataclasses import dataclass
from datetime import datetime, timezone

from rag_service.models import ReportType, SourceFilter
from rag_service.retrieval import tokenize
from rag_service.state import RetrievedChunk


DEFAULT_MAX_CONTEXT_TOKENS = 144
DEFAULT_MAX_CONTEXT_ITEMS = 6
DEFAULT_MAX_ITEM_TOKENS = 42
MIN_ITEM_TOKENS = 8

PRIMARY_SOURCE_BY_REPORT = {
    ReportType.FILING_ANALYSIS: SourceFilter.SEC,
    ReportType.EARNINGS_BRIEF: SourceFilter.EARNINGS,
    ReportType.EVENT_DRIVEN: SourceFilter.NEWS,
}

MATERIAL_TERMS = {
    "capex",
    "capital",
    "cash",
    "concentration",
    "customer",
    "demand",
    "export",
    "filing",
    "guidance",
    "liquidity",
    "margin",
    "material",
    "revenue",
    "risk",
    "supply",
}

POSITIVE_TERMS = {
    "accelerating",
    "expanded",
    "expanding",
    "growth",
    "improved",
    "strong",
    "upside",
}

NEGATIVE_TERMS = {
    "constraint",
    "constraints",
    "concentration",
    "decline",
    "delayed",
    "pressure",
    "risk",
    "weak",
}

UNCERTAINTY_TERMS = {
    "could",
    "depends",
    "may",
    "uncertain",
    "uncertainty",
    "unknown",
    "volatility",
}


@dataclass(frozen=True)
class ContextBuilderConfig:
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    max_context_items: int = DEFAULT_MAX_CONTEXT_ITEMS
    max_item_tokens: int = DEFAULT_MAX_ITEM_TOKENS


@dataclass(frozen=True)
class ContextCandidate:
    chunk: RetrievedChunk
    rank_score: float
    token_count: int
    recency_score: float
    materiality_score: float
    source_priority: float
    evidence_signal: str
    published_at: str


@dataclass(frozen=True)
class CitationSpan:
    citation_id: str
    chunk_id: str
    source_id: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    start_token: int
    end_token: int
    source_metadata: dict[str, str]


@dataclass(frozen=True)
class ContextDiagnostic:
    chunk_id: str
    source_type: SourceFilter
    included: bool
    reason: str
    token_count: int
    rank_score: float
    evidence_signal: str


@dataclass(frozen=True)
class ContextBuildResult:
    chunks: list[RetrievedChunk]
    citation_map: list[CitationSpan]
    diagnostics: list[ContextDiagnostic]
    total_tokens: int
    max_tokens: int


class ContextBuilder:
    def __init__(self, config: ContextBuilderConfig | None = None):
        self._config = config or ContextBuilderConfig()

    def build(
        self,
        chunks: list[RetrievedChunk],
        source_filters: list[SourceFilter],
        question: str,
        report_type: ReportType,
    ) -> ContextBuildResult:
        candidates = build_candidates(chunks, question, report_type)
        ordered_candidates = sorted(candidates, key=context_sort_key)
        selected: list[RetrievedChunk] = []
        citation_map: list[CitationSpan] = []
        diagnostics_by_chunk: dict[str, ContextDiagnostic] = {}
        selected_ids: set[str] = set()
        total_tokens = 0

        def try_add(candidate: ContextCandidate, reason: str) -> bool:
            nonlocal total_tokens
            chunk = candidate.chunk
            chunk_id = chunk["chunk_id"]
            if chunk_id in selected_ids:
                return False
            if is_near_duplicate(chunk, selected):
                diagnostics_by_chunk.setdefault(chunk_id, diagnostic_for(candidate, False, "near_duplicate"))
                return False
            if len(selected) >= self._config.max_context_items:
                diagnostics_by_chunk.setdefault(chunk_id, diagnostic_for(candidate, False, "item_limit"))
                return False

            remaining_tokens = self._config.max_context_tokens - total_tokens
            if remaining_tokens < MIN_ITEM_TOKENS:
                diagnostics_by_chunk.setdefault(chunk_id, diagnostic_for(candidate, False, "token_budget_exceeded"))
                return False

            packed_text, packed_tokens, truncated = pack_text(
                chunk["text"],
                max_tokens=min(self._config.max_item_tokens, remaining_tokens),
            )
            if packed_tokens == 0:
                diagnostics_by_chunk.setdefault(chunk_id, diagnostic_for(candidate, False, "empty_text"))
                return False

            context_rank = len(selected) + 1
            citation_id = f"C{context_rank}"
            start_token = total_tokens
            end_token = start_token + packed_tokens
            context_chunk = annotate_context_chunk(
                candidate,
                citation_id=citation_id,
                context_rank=context_rank,
                text=packed_text,
                start_token=start_token,
                end_token=end_token,
                token_count=packed_tokens,
                truncated=truncated,
            )
            selected.append(context_chunk)
            selected_ids.add(chunk_id)
            total_tokens = end_token
            citation_map.append(citation_span_for(context_chunk, citation_id, start_token, end_token))
            diagnostics_by_chunk[chunk_id] = diagnostic_for(candidate, True, reason)
            return True

        for source_filter in sorted(
            source_filters,
            key=lambda value: (-source_priority_score(value, report_type), value.value),
        ):
            source_candidate = next(
                (candidate for candidate in ordered_candidates if candidate.chunk["source_type"] == source_filter),
                None,
            )
            if source_candidate:
                try_add(source_candidate, "source_diversity")

        for signal in ("positive", "negative", "uncertainty", "mixed"):
            signal_candidate = next(
                (
                    candidate
                    for candidate in ordered_candidates
                    if candidate.evidence_signal == signal
                    and candidate.chunk["chunk_id"] not in selected_ids
                ),
                None,
            )
            if signal_candidate:
                try_add(signal_candidate, f"signal_preservation:{signal}")

        for candidate in ordered_candidates:
            if len(selected) >= self._config.max_context_items:
                break
            try_add(candidate, "ranked_fill")

        for candidate in ordered_candidates:
            diagnostics_by_chunk.setdefault(
                candidate.chunk["chunk_id"],
                diagnostic_for(candidate, False, "lower_ranked"),
            )

        return ContextBuildResult(
            chunks=selected,
            citation_map=citation_map,
            diagnostics=list(diagnostics_by_chunk.values()),
            total_tokens=total_tokens,
            max_tokens=self._config.max_context_tokens,
        )


def build_candidates(
    chunks: list[RetrievedChunk],
    question: str,
    report_type: ReportType,
) -> list[ContextCandidate]:
    latest_timestamp = latest_published_timestamp(chunks)
    return [
        candidate_for(chunk, question, report_type, latest_timestamp)
        for chunk in chunks
    ]


def candidate_for(
    chunk: RetrievedChunk,
    question: str,
    report_type: ReportType,
    latest_timestamp: datetime | None,
) -> ContextCandidate:
    materiality = materiality_score(chunk, question)
    recency = recency_score(chunk.get("metadata", {}).get("published_at", ""), latest_timestamp)
    source_priority = source_priority_score(chunk["source_type"], report_type)
    reranker_score = chunk.get("reranker_score", chunk.get("score", 0.0))
    low_confidence_penalty = 0.08 if chunk.get("low_confidence", False) else 0.0
    rank_score = max(
        0.0,
        (
            0.54 * reranker_score
            + 0.2 * materiality
            + 0.14 * recency
            + 0.12 * source_priority
            - low_confidence_penalty
        ),
    )
    return ContextCandidate(
        chunk=chunk,
        rank_score=round(rank_score, 6),
        token_count=len(tokenize(chunk["text"])),
        recency_score=round(recency, 6),
        materiality_score=round(materiality, 6),
        source_priority=round(source_priority, 6),
        evidence_signal=evidence_signal(chunk["text"]),
        published_at=chunk.get("metadata", {}).get("published_at", ""),
    )


def context_sort_key(candidate: ContextCandidate) -> tuple:
    chunk = candidate.chunk
    return (
        -candidate.rank_score,
        -chunk.get("reranker_score", chunk.get("score", 0.0)),
        -candidate.materiality_score,
        -candidate.recency_score,
        chunk["source_type"].value,
        chunk["chunk_id"],
    )


def materiality_score(chunk: RetrievedChunk, question: str) -> float:
    terms = set(tokenize(f"{question} {chunk['section']} {chunk['text']}"))
    hits = len(terms & MATERIAL_TERMS)
    base = min(1.0, hits / 5)
    section_bonus = 0.0
    section = chunk["section"].lower()
    if any(value in section for value in ("risk", "management", "guidance", "q&a", "financial")):
        section_bonus = 0.2
    return min(1.0, base + section_bonus)


def source_priority_score(source_type: SourceFilter, report_type: ReportType) -> float:
    preferred_source = PRIMARY_SOURCE_BY_REPORT.get(report_type)
    if preferred_source:
        return 1.0 if source_type == preferred_source else 0.65
    if source_type in (SourceFilter.SEC, SourceFilter.EARNINGS):
        return 0.9
    return 0.75


def recency_score(published_at: str, latest_timestamp: datetime | None) -> float:
    timestamp = parse_timestamp(published_at)
    if timestamp is None or latest_timestamp is None:
        return 0.2
    age_days = max(0, (latest_timestamp - timestamp).days)
    return max(0.0, 1 - min(age_days, 365) / 365)


def latest_published_timestamp(chunks: list[RetrievedChunk]) -> datetime | None:
    timestamps = [
        timestamp
        for chunk in chunks
        if (timestamp := parse_timestamp(chunk.get("metadata", {}).get("published_at", ""))) is not None
    ]
    if not timestamps:
        return None
    return max(timestamps)


def evidence_signal(text: str) -> str:
    terms = set(tokenize(text))
    positive = bool(terms & POSITIVE_TERMS)
    negative = bool(terms & NEGATIVE_TERMS)
    uncertainty = bool(terms & UNCERTAINTY_TERMS)
    if positive and (negative or uncertainty):
        return "mixed"
    if negative:
        return "negative"
    if positive:
        return "positive"
    if uncertainty:
        return "uncertainty"
    return "neutral"


def pack_text(text: str, max_tokens: int) -> tuple[str, int, bool]:
    tokens = tokenize(text)
    if not tokens:
        return "", 0, False
    if len(tokens) <= max_tokens:
        return " ".join(tokens), len(tokens), False
    return " ".join(tokens[:max_tokens]), max_tokens, True


def annotate_context_chunk(
    candidate: ContextCandidate,
    citation_id: str,
    context_rank: int,
    text: str,
    start_token: int,
    end_token: int,
    token_count: int,
    truncated: bool,
) -> RetrievedChunk:
    chunk = candidate.chunk
    metadata = {
        **chunk.get("metadata", {}),
        "context_citation_id": citation_id,
        "context_rank": str(context_rank),
        "context_span_start_token": str(start_token),
        "context_span_end_token": str(end_token),
        "context_token_count": str(token_count),
        "context_truncated": str(truncated).lower(),
        "context_evidence_signal": candidate.evidence_signal,
        "context_materiality_score": str(candidate.materiality_score),
        "context_recency_score": str(candidate.recency_score),
    }
    return {
        **chunk,
        "text": text,
        "context_rank": context_rank,
        "context_citation_id": citation_id,
        "context_span_start_token": start_token,
        "context_span_end_token": end_token,
        "context_token_count": token_count,
        "context_truncated": truncated,
        "evidence_signal": candidate.evidence_signal,
        "materiality_score": candidate.materiality_score,
        "recency_score": candidate.recency_score,
        "metadata": metadata,
    }


def citation_span_for(
    chunk: RetrievedChunk,
    citation_id: str,
    start_token: int,
    end_token: int,
) -> CitationSpan:
    return CitationSpan(
        citation_id=citation_id,
        chunk_id=chunk["chunk_id"],
        source_id=chunk["source_id"],
        source_type=chunk["source_type"],
        title=chunk["title"],
        url=chunk["url"],
        section=chunk["section"],
        start_token=start_token,
        end_token=end_token,
        source_metadata=dict(chunk.get("metadata", {})),
    )


def diagnostic_for(candidate: ContextCandidate, included: bool, reason: str) -> ContextDiagnostic:
    return ContextDiagnostic(
        chunk_id=candidate.chunk["chunk_id"],
        source_type=candidate.chunk["source_type"],
        included=included,
        reason=reason,
        token_count=candidate.token_count,
        rank_score=candidate.rank_score,
        evidence_signal=candidate.evidence_signal,
    )


def is_near_duplicate(chunk: RetrievedChunk, selected: list[RetrievedChunk]) -> bool:
    chunk_terms = set(tokenize(chunk["text"]))
    for selected_chunk in selected:
        if chunk["content_hash"] == selected_chunk["content_hash"]:
            return True
        if chunk["source_id"] == selected_chunk["source_id"] and chunk["section"] == selected_chunk["section"]:
            selected_terms = set(tokenize(selected_chunk["text"]))
            if jaccard_similarity(chunk_terms, selected_terms) >= 0.75:
                return True
    return False


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)
