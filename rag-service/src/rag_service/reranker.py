import time
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from rag_service.models import ReportType, SourceFilter
from rag_service.retrieval import rewrite_finance_query, semantic_token, tokenize
from rag_service.state import RetrievedChunk


DEFAULT_MIN_RELEVANCE_SCORE = 0.18
DEFAULT_BATCH_SIZE = 8
DEFAULT_LATENCY_BUDGET_MS = 250


@dataclass(frozen=True)
class RerankInput:
    user_question: str
    report_intent: ReportType
    chunk_id: str
    source_type: SourceFilter
    title: str
    section: str
    chunk_text: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class RerankDiagnostic:
    chunk_id: str
    original_rank: int
    reranked_rank: int | None
    original_score: float
    reranker_score: float
    included: bool
    low_confidence: bool
    reason: str


@dataclass(frozen=True)
class RerankResult:
    chunks: list[RetrievedChunk]
    diagnostics: list[RerankDiagnostic]
    status: str
    latency_ms: int
    fallback_used: bool


class CrossEncoderScorer(Protocol):
    available: bool

    def score_batch(self, inputs: list[RerankInput]) -> list[float]:
        pass


class LocalCrossEncoderScorer:
    available = True

    def score_batch(self, inputs: list[RerankInput]) -> list[float]:
        return [calibrated_score(local_cross_encoder_score(item)) for item in inputs]


class UnavailableCrossEncoderScorer:
    available = False

    def score_batch(self, inputs: list[RerankInput]) -> list[float]:
        raise RuntimeError("cross-encoder scorer unavailable")


class CrossEncoderReranker:
    def __init__(
        self,
        scorer: CrossEncoderScorer | None = None,
        min_relevance_score: float = DEFAULT_MIN_RELEVANCE_SCORE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        latency_budget_ms: int = DEFAULT_LATENCY_BUDGET_MS,
        exclude_low_confidence: bool = True,
    ):
        self._scorer = scorer or LocalCrossEncoderScorer()
        self._min_relevance_score = min_relevance_score
        self._batch_size = batch_size
        self._latency_budget_ms = latency_budget_ms
        self._exclude_low_confidence = exclude_low_confidence

    def rerank(
        self,
        chunks: list[RetrievedChunk],
        user_question: str,
        report_intent: ReportType,
    ) -> RerankResult:
        start = time.perf_counter()
        if not chunks:
            return RerankResult(chunks=[], diagnostics=[], status="completed", latency_ms=0, fallback_used=False)

        inputs = [rerank_input_for(chunk, user_question, report_intent) for chunk in chunks]
        if not self._scorer.available:
            return self._fallback(chunks, start, "fallback_unavailable")

        try:
            scores = [
                score
                for batch in batched(inputs, self._batch_size)
                for score in self._scorer.score_batch(batch)
            ]
        except Exception:
            return self._fallback(chunks, start, "fallback_error")

        reranked_items = sorted(
            zip(chunks, scores, strict=True),
            key=lambda item: (
                item[1],
                item[0].get("score", 0.0),
                -item[0].get("rank", 0),
            ),
            reverse=True,
        )
        output_chunks: list[RetrievedChunk] = []
        diagnostics: list[RerankDiagnostic] = []

        for chunk, score in reranked_items:
            low_confidence = score < self._min_relevance_score
            included = not low_confidence or not self._exclude_low_confidence
            reranked_rank = len(output_chunks) + 1 if included else None
            updated_chunk = annotate_chunk(
                chunk,
                score=score,
                status="completed",
                reranked_rank=reranked_rank,
                low_confidence=low_confidence,
            )
            if included:
                output_chunks.append(updated_chunk)
            diagnostics.append(
                RerankDiagnostic(
                    chunk_id=chunk["chunk_id"],
                    original_rank=chunk.get("rank", 0),
                    reranked_rank=reranked_rank,
                    original_score=chunk.get("score", 0.0),
                    reranker_score=score,
                    included=included,
                    low_confidence=low_confidence,
                    reason=rerank_reason(included, low_confidence),
                )
            )

        latency_ms = elapsed_ms(start)
        status = "completed"
        if latency_ms > self._latency_budget_ms:
            status = "completed_over_budget"
        return RerankResult(
            chunks=output_chunks,
            diagnostics=diagnostics,
            status=status,
            latency_ms=latency_ms,
            fallback_used=False,
        )

    def _fallback(self, chunks: list[RetrievedChunk], start: float, status: str) -> RerankResult:
        sorted_chunks = sorted(chunks, key=lambda chunk: chunk.get("score", 0.0), reverse=True)
        output_chunks = [
            annotate_chunk(
                chunk,
                score=chunk.get("score", 0.0),
                status=status,
                reranked_rank=rank,
                low_confidence=False,
            )
            for rank, chunk in enumerate(sorted_chunks, start=1)
        ]
        return RerankResult(
            chunks=output_chunks,
            diagnostics=[
                RerankDiagnostic(
                    chunk_id=chunk["chunk_id"],
                    original_rank=chunk.get("rank", 0),
                    reranked_rank=rank,
                    original_score=chunk.get("score", 0.0),
                    reranker_score=chunk.get("score", 0.0),
                    included=True,
                    low_confidence=False,
                    reason=status,
                )
                for rank, chunk in enumerate(sorted_chunks, start=1)
            ],
            status=status,
            latency_ms=elapsed_ms(start),
            fallback_used=True,
        )


def rerank_input_for(
    chunk: RetrievedChunk,
    user_question: str,
    report_intent: ReportType,
) -> RerankInput:
    return RerankInput(
        user_question=user_question,
        report_intent=report_intent,
        chunk_id=chunk["chunk_id"],
        source_type=chunk["source_type"],
        title=chunk["title"],
        section=chunk["section"],
        chunk_text=chunk["text"],
        metadata=chunk.get("metadata", {}),
    )


def local_cross_encoder_score(item: RerankInput) -> float:
    question_terms = normalized_terms(rewrite_finance_query(item.user_question))
    chunk_terms = normalized_terms(candidate_text(item))
    if not question_terms or not chunk_terms:
        return 0.0

    overlap_count = sum(min(question_terms[term], chunk_terms.get(term, 0)) for term in question_terms)
    overlap_score = overlap_count / sum(question_terms.values())
    coverage_score = len(set(question_terms) & set(chunk_terms)) / len(set(question_terms))
    phrase_score = phrase_match_score(item.user_question, candidate_text(item))
    intent_score = report_intent_score(item.report_intent, item)
    metadata_score = metadata_alignment_score(item)
    return (
        0.52 * overlap_score
        + 0.24 * coverage_score
        + 0.12 * phrase_score
        + 0.08 * intent_score
        + 0.04 * metadata_score
    )


def calibrated_score(raw_score: float) -> float:
    return round(max(0.0, min(1.0, raw_score)), 6)


def candidate_text(item: RerankInput) -> str:
    metadata_text = " ".join(
        item.metadata.get(field, "")
        for field in (
            "ticker",
            "company_name",
            "document_title",
            "form_type",
            "period",
            "fiscal_quarter",
            "fiscal_year",
            "speaker",
            "topic",
        )
    )
    return f"{metadata_text} {item.title} {item.section} {item.chunk_text}"


def normalized_terms(value: str) -> Counter[str]:
    return Counter(semantic_token(token) for token in tokenize(value))


def phrase_match_score(question: str, text: str) -> float:
    question_lower = question.lower()
    text_lower = text.lower()
    phrases = [
        phrase
        for phrase in (
            "gross margin",
            "export controls",
            "risk factors",
            "capital expenditure",
            "data center",
            "supply availability",
            "customer concentration",
        )
        if phrase in question_lower
    ]
    if not phrases:
        return 0.0
    return sum(1 for phrase in phrases if phrase in text_lower) / len(phrases)


def report_intent_score(report_intent: ReportType, item: RerankInput) -> float:
    preferred_source = {
        ReportType.FILING_ANALYSIS: SourceFilter.SEC,
        ReportType.EARNINGS_BRIEF: SourceFilter.EARNINGS,
        ReportType.EVENT_DRIVEN: SourceFilter.NEWS,
    }.get(report_intent)
    if preferred_source is None:
        return 1.0
    return 1.0 if item.source_type == preferred_source else 0.0


def metadata_alignment_score(item: RerankInput) -> float:
    if item.report_intent == ReportType.FILING_ANALYSIS and item.metadata.get("form_type"):
        return 1.0
    if item.report_intent == ReportType.EARNINGS_BRIEF and item.metadata.get("fiscal_quarter"):
        return 1.0
    if item.report_intent == ReportType.EVENT_DRIVEN and item.metadata.get("published_at"):
        return 1.0
    return 0.75


def rerank_reason(included: bool, low_confidence: bool) -> str:
    if included and low_confidence:
        return "included_low_confidence"
    if included:
        return "included"
    return "below_min_relevance"


def annotate_chunk(
    chunk: RetrievedChunk,
    score: float,
    status: str,
    reranked_rank: int | None,
    low_confidence: bool,
) -> RetrievedChunk:
    updated: RetrievedChunk = {
        **chunk,
        "reranker_score": score,
        "reranker_status": status,
        "low_confidence": low_confidence,
    }
    if reranked_rank is not None:
        updated["rank"] = reranked_rank
        updated["reranker_rank"] = reranked_rank
    return updated


def batched(items: list[RerankInput], batch_size: int) -> list[list[RerankInput]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
