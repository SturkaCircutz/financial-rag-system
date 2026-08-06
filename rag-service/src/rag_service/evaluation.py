import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from rag_service.financial_report import StructuredFinancialReport, evidence_claim_fields
from rag_service.models import ReportType, SourceFilter
from rag_service.retrieval import tokenize
from rag_service.state import RetrievedChunk


EVALUATION_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "evaluation"
GOLDEN_QUESTION_PATH = EVALUATION_DATA_ROOT / "golden_questions.json"
BASELINE_METRICS_PATH = EVALUATION_DATA_ROOT / "baseline_metrics.json"
DEFAULT_RETRIEVAL_K = 5

SOURCE_CLAIM_FIELDS = {
    SourceFilter.SEC: "latest_sec_filing_signals",
    SourceFilter.NEWS: "recent_news_signals",
    SourceFilter.EARNINGS: "earnings_and_guidance_signals",
}

PROHIBITED_TONE_MARKERS = (
    "guaranteed",
    "risk-free",
    "must buy",
    "definitely buy",
    "certain upside",
)

LOWER_IS_BETTER_METRICS = (
    "unsupported_claim_rate",
    "latency_ms",
    "estimated_cost_usd",
)


@dataclass(frozen=True)
class GoldenQuestion:
    question_id: str
    tickers: tuple[str, ...]
    question: str
    report_type: ReportType
    source_filters: tuple[SourceFilter, ...]
    expected_evidence_ids: tuple[str, ...]
    preferred_evidence_order: tuple[str, ...] = ()
    required_source_types: tuple[SourceFilter, ...] = ()
    metadata_expectations: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    source_diversity: float
    metadata_filter_accuracy: float


@dataclass(frozen=True)
class RerankingMetrics:
    pairwise_preference_accuracy: float
    recall_improvement: float


@dataclass(frozen=True)
class GenerationMetrics:
    citation_coverage: float
    unsupported_claim_rate: float
    answer_completeness: float
    tone_compliance: float


@dataclass(frozen=True)
class BenchmarkMetrics:
    workflow: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class WorkflowEvaluationInput:
    workflow: str
    retrieved_chunks: list[RetrievedChunk]
    reranked_chunks: list[RetrievedChunk]
    selected_context: list[RetrievedChunk]
    structured_report: StructuredFinancialReport | dict[str, Any]
    prompt: str = ""
    response_text: str = ""
    latency_ms: int = 0
    prompt_cost_per_1k: float = 0.0
    completion_cost_per_1k: float = 0.0


@dataclass(frozen=True)
class EvaluationReport:
    question_id: str
    retrieval: RetrievalMetrics
    reranking: RerankingMetrics
    generation: GenerationMetrics
    benchmark: BenchmarkMetrics

    def to_dict(self) -> dict[str, Any]:
        return enum_safe(
            {
                "question_id": self.question_id,
                "retrieval": asdict(self.retrieval),
                "reranking": asdict(self.reranking),
                "generation": asdict(self.generation),
                "benchmark": asdict(self.benchmark),
            }
        )


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    reasons: list[str]


def load_golden_questions(path: Path = GOLDEN_QUESTION_PATH) -> list[GoldenQuestion]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [golden_question_from_payload(item) for item in payload.get("questions", [])]


def load_baseline_metrics(path: Path = BASELINE_METRICS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_workflow_result(
    golden_question: GoldenQuestion,
    workflow_result: WorkflowEvaluationInput,
    k: int = DEFAULT_RETRIEVAL_K,
) -> EvaluationReport:
    return EvaluationReport(
        question_id=golden_question.question_id,
        retrieval=retrieval_metrics(golden_question, workflow_result.retrieved_chunks, k=k),
        reranking=reranking_metrics(
            golden_question,
            workflow_result.retrieved_chunks,
            workflow_result.reranked_chunks,
            k=k,
        ),
        generation=generation_metrics(
            golden_question,
            workflow_result.structured_report,
            workflow_result.selected_context,
        ),
        benchmark=benchmark_metrics(
            workflow_result.workflow,
            latency_ms=workflow_result.latency_ms,
            prompt=workflow_result.prompt,
            response_text=workflow_result.response_text,
            prompt_cost_per_1k=workflow_result.prompt_cost_per_1k,
            completion_cost_per_1k=workflow_result.completion_cost_per_1k,
        ),
    )


def retrieval_metrics(
    golden_question: GoldenQuestion,
    retrieved_chunks: list[RetrievedChunk],
    k: int = DEFAULT_RETRIEVAL_K,
) -> RetrievalMetrics:
    top_k = retrieved_chunks[:k]
    return RetrievalMetrics(
        recall_at_k=round(recall_at_k(golden_question.expected_evidence_ids, top_k), 6),
        mrr=round(mean_reciprocal_rank(golden_question.expected_evidence_ids, top_k), 6),
        ndcg_at_k=round(ndcg_at_k(golden_question.expected_evidence_ids, top_k, k=k), 6),
        source_diversity=round(source_diversity(golden_question, top_k), 6),
        metadata_filter_accuracy=round(metadata_filter_accuracy(golden_question, top_k), 6),
    )


def reranking_metrics(
    golden_question: GoldenQuestion,
    raw_chunks: list[RetrievedChunk],
    reranked_chunks: list[RetrievedChunk],
    k: int = DEFAULT_RETRIEVAL_K,
) -> RerankingMetrics:
    raw_recall = recall_at_k(golden_question.expected_evidence_ids, raw_chunks[:k])
    reranked_recall = recall_at_k(golden_question.expected_evidence_ids, reranked_chunks[:k])
    return RerankingMetrics(
        pairwise_preference_accuracy=round(pairwise_preference_accuracy(golden_question, reranked_chunks), 6),
        recall_improvement=round(reranked_recall - raw_recall, 6),
    )


def generation_metrics(
    golden_question: GoldenQuestion,
    report_payload: StructuredFinancialReport | dict[str, Any],
    selected_context: list[RetrievedChunk],
) -> GenerationMetrics:
    report = report_payload if isinstance(report_payload, StructuredFinancialReport) else StructuredFinancialReport.model_validate(report_payload)
    claims = report_claims(report)
    valid_citation_ids = {citation.citation_id for citation in report.source_citations}
    cited_claims = [
        claim
        for claim in claims
        if claim.citation_ids and set(claim.citation_ids).issubset(valid_citation_ids)
    ]
    unsupported_claims = [
        claim
        for claim in claims
        if not claim.citation_ids or not set(claim.citation_ids).issubset(valid_citation_ids)
    ]
    claim_count = len(claims)
    return GenerationMetrics(
        citation_coverage=round(safe_ratio(len(cited_claims), claim_count, default=1.0), 6),
        unsupported_claim_rate=round(safe_ratio(len(unsupported_claims), claim_count), 6),
        answer_completeness=round(answer_completeness(golden_question, report, selected_context), 6),
        tone_compliance=round(tone_compliance(report), 6),
    )


def benchmark_metrics(
    workflow: str,
    latency_ms: int,
    prompt: str = "",
    response_text: str = "",
    prompt_cost_per_1k: float = 0.0,
    completion_cost_per_1k: float = 0.0,
) -> BenchmarkMetrics:
    prompt_tokens = estimated_tokens(prompt)
    completion_tokens = estimated_tokens(response_text)
    estimated_cost = (
        prompt_tokens / 1000 * prompt_cost_per_1k
        + completion_tokens / 1000 * completion_cost_per_1k
    )
    return BenchmarkMetrics(
        workflow=workflow,
        latency_ms=max(0, latency_ms),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=round(estimated_cost, 8),
    )


def evaluate_quality_gate(
    evaluation_report: EvaluationReport,
    baseline: Mapping[str, Any] | None = None,
) -> QualityGateResult:
    baseline = baseline or load_baseline_metrics()
    current = evaluation_report.to_dict()
    gate = baseline.get("quality_gate", {})
    reasons: list[str] = []

    for metric_path, minimum in gate.get("minimums", {}).items():
        actual = metric_value(current, metric_path)
        if actual < minimum:
            reasons.append(f"{metric_path}={actual} is below minimum {minimum}")

    for metric_path, maximum in gate.get("maximums", {}).items():
        actual = metric_value(current, metric_path)
        if actual > maximum:
            reasons.append(f"{metric_path}={actual} is above maximum {maximum}")

    baseline_metrics = baseline.get("baseline_metrics", {})
    for metric_path, allowed_regression in gate.get("allowed_regressions", {}).items():
        actual = metric_value(current, metric_path)
        previous = metric_value(baseline_metrics, metric_path)
        if lower_is_better(metric_path):
            if actual > previous + allowed_regression:
                reasons.append(f"{metric_path} regressed from {previous} to {actual}")
        elif actual < previous - allowed_regression:
            reasons.append(f"{metric_path} regressed from {previous} to {actual}")

    return QualityGateResult(passed=not reasons, reasons=reasons)


def golden_question_from_payload(item: Mapping[str, Any]) -> GoldenQuestion:
    return GoldenQuestion(
        question_id=item["question_id"],
        tickers=tuple(ticker.upper() for ticker in item["tickers"]),
        question=item["question"],
        report_type=ReportType(item["report_type"]),
        source_filters=tuple(SourceFilter(source_type) for source_type in item["source_filters"]),
        expected_evidence_ids=tuple(item["expected_evidence_ids"]),
        preferred_evidence_order=tuple(item.get("preferred_evidence_order", [])),
        required_source_types=tuple(SourceFilter(source_type) for source_type in item.get("required_source_types", [])),
        metadata_expectations={
            key: tuple(str(value) for value in values)
            for key, values in item.get("metadata_expectations", {}).items()
        },
    )


def recall_at_k(expected_evidence_ids: tuple[str, ...], chunks: list[RetrievedChunk]) -> float:
    expected_ids = set(expected_evidence_ids)
    if not expected_ids:
        return 1.0
    observed_ids = {chunk["evidence_id"] for chunk in chunks}
    return safe_ratio(len(expected_ids & observed_ids), len(expected_ids))


def mean_reciprocal_rank(expected_evidence_ids: tuple[str, ...], chunks: list[RetrievedChunk]) -> float:
    expected_ids = set(expected_evidence_ids)
    for rank, chunk in enumerate(chunks, start=1):
        if chunk["evidence_id"] in expected_ids:
            return 1 / rank
    return 0.0


def ndcg_at_k(expected_evidence_ids: tuple[str, ...], chunks: list[RetrievedChunk], k: int) -> float:
    expected_ids = set(expected_evidence_ids)
    if not expected_ids:
        return 1.0
    relevance = [1.0 if chunk["evidence_id"] in expected_ids else 0.0 for chunk in chunks[:k]]
    ideal_relevance = [1.0] * min(len(expected_ids), k)
    ideal_relevance.extend([0.0] * max(0, k - len(ideal_relevance)))
    ideal = discounted_cumulative_gain(ideal_relevance)
    if ideal == 0:
        return 0.0
    return discounted_cumulative_gain(relevance) / ideal


def discounted_cumulative_gain(relevance: list[float]) -> float:
    return sum(value / math.log2(rank + 1) for rank, value in enumerate(relevance, start=1))


def source_diversity(golden_question: GoldenQuestion, chunks: list[RetrievedChunk]) -> float:
    required_sources = set(golden_question.required_source_types or golden_question.source_filters)
    if not required_sources:
        return 1.0
    observed_sources = {chunk["source_type"] for chunk in chunks}
    return safe_ratio(len(required_sources & observed_sources), len(required_sources))


def metadata_filter_accuracy(golden_question: GoldenQuestion, chunks: list[RetrievedChunk]) -> float:
    if not chunks:
        return 1.0 if not golden_question.expected_evidence_ids else 0.0
    matching = sum(1 for chunk in chunks if chunk_matches_expected_metadata(golden_question, chunk))
    return safe_ratio(matching, len(chunks))


def chunk_matches_expected_metadata(golden_question: GoldenQuestion, chunk: RetrievedChunk) -> bool:
    if golden_question.tickers:
        ticker = metadata_value(chunk, "ticker").upper()
        if ticker not in golden_question.tickers:
            return False
    if golden_question.source_filters and chunk["source_type"] not in golden_question.source_filters:
        return False
    for key, allowed_values in golden_question.metadata_expectations.items():
        value = metadata_value(chunk, key)
        if value and value in allowed_values:
            continue
        if key == "source_type" and chunk["source_type"].value in allowed_values:
            continue
        return False
    return True


def metadata_value(chunk: RetrievedChunk, key: str) -> str:
    if key == "section":
        return chunk.get("section", "")
    return chunk.get("metadata", {}).get(key, "")


def pairwise_preference_accuracy(golden_question: GoldenQuestion, chunks: list[RetrievedChunk]) -> float:
    preferred = list(golden_question.preferred_evidence_order or golden_question.expected_evidence_ids)
    if len(preferred) < 2:
        return 1.0
    ranks = {chunk["evidence_id"]: index for index, chunk in enumerate(chunks)}
    correct = 0
    total = 0
    for left_index, left_id in enumerate(preferred):
        for right_id in preferred[left_index + 1:]:
            total += 1
            if ranks.get(left_id, len(chunks) + left_index) < ranks.get(right_id, len(chunks) + left_index + 1):
                correct += 1
    return safe_ratio(correct, total, default=1.0)


def report_claims(report: StructuredFinancialReport):
    return [
        claim
        for field_name in evidence_claim_fields()
        for claim in getattr(report, field_name)
    ]


def answer_completeness(
    golden_question: GoldenQuestion,
    report: StructuredFinancialReport,
    selected_context: list[RetrievedChunk],
) -> float:
    required_sources = set(golden_question.required_source_types or golden_question.source_filters)
    if not required_sources:
        return 1.0
    selected_sources = {chunk["source_type"] for chunk in selected_context}
    complete = 0
    for source_type in required_sources:
        field_name = SOURCE_CLAIM_FIELDS[source_type]
        if getattr(report, field_name) and source_type in selected_sources:
            complete += 1
    return safe_ratio(complete, len(required_sources))


def tone_compliance(report: StructuredFinancialReport) -> float:
    report_text = " ".join(iter_report_text(report)).lower()
    if any(marker in report_text for marker in PROHIBITED_TONE_MARKERS):
        return 0.0
    limitations_text = " ".join(report.methodology_and_limitations).lower()
    if "not trading advice" not in limitations_text:
        return 0.0
    return 1.0


def iter_report_text(report: StructuredFinancialReport):
    yield report.executive_summary
    for claim in report_claims(report):
        yield claim.claim
    for event in report.evidence_timeline:
        yield event.event
    yield from report.methodology_and_limitations


def estimated_tokens(value: str) -> int:
    if not value:
        return 0
    return len(tokenize(value))


def metric_value(payload: Mapping[str, Any], metric_path: str) -> float:
    value: Any = payload
    for part in metric_path.split("."):
        value = value[part]
    return float(value)


def lower_is_better(metric_path: str) -> bool:
    return any(metric_path.endswith(metric_name) for metric_name in LOWER_IS_BETTER_METRICS)


def safe_ratio(numerator: int | float, denominator: int | float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def enum_safe(value: Any) -> Any:
    if isinstance(value, (SourceFilter, ReportType)):
        return value.value
    if isinstance(value, dict):
        return {key: enum_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [enum_safe(item) for item in value]
    return value
