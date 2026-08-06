import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from rag_service.documents import ChunkMetadataFilter
from rag_service.models import SourceFilter
from rag_service.state import AgentResult, RetrievedChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

QUERY_EXPANSIONS = {
    "10k": ("annual", "filing"),
    "10q": ("quarterly", "filing"),
    "capex": ("capital", "expenditure"),
    "revenue": ("sales",),
    "revenues": ("sales",),
    "buyback": ("repurchase",),
    "buybacks": ("repurchases",),
    "datacenter": ("data", "center"),
    "cybersecurity": ("security",),
}

PHRASE_EXPANSIONS = {
    "gross margin": ("profitability",),
    "export controls": ("licensing", "restrictions"),
    "data center": ("datacenter", "cloud"),
    "risk factors": ("filing", "risk"),
}

SEMANTIC_ALIASES = {
    "accelerator": "gpu",
    "accelerators": "gpu",
    "chip": "gpu",
    "chips": "gpu",
    "delivery": "shipment",
    "deliveries": "shipment",
    "schedule": "timing",
    "outlook": "guidance",
    "forecast": "guidance",
    "profitability": "margin",
    "liquidity": "cash",
    "stress": "pressure",
    "restrictions": "controls",
    "licensing": "controls",
    "repurchase": "buyback",
    "repurchases": "buyback",
    "sales": "revenue",
}

RRF_K = 60


@dataclass(frozen=True)
class CandidateScore:
    result: AgentResult
    score: float
    rank: int


@dataclass(frozen=True)
class RetrievalCandidateDiagnostic:
    chunk_id: str
    source_id: str
    candidate_source: str
    score: float
    rank: int | None
    included: bool
    filter_path: list[str]


@dataclass(frozen=True)
class HybridRetrievalResult:
    chunks: list[RetrievedChunk]
    diagnostics: list[RetrievalCandidateDiagnostic]


class Bm25Index:
    def __init__(self, agent_results: list[AgentResult]):
        self._agent_results = agent_results
        self._tokenized_documents = [
            tokenize(searchable_text(result))
            for result in agent_results
        ]
        self._document_frequency = Counter(
            token
            for tokens in self._tokenized_documents
            for token in set(tokens)
        )
        self._average_document_length = average_document_length(self._tokenized_documents)

    def rank(self, query: str) -> list[CandidateScore]:
        if not self._agent_results:
            return []

        rewritten_query = rewrite_finance_query(query)
        query_terms = Counter(tokenize(rewritten_query))
        scored = [
            CandidateScore(
                result=result,
                score=bm25_score(
                    document_tokens=tokens,
                    query_terms=query_terms,
                    document_frequency=self._document_frequency,
                    document_count=len(self._tokenized_documents),
                    average_document_length=self._average_document_length,
                ),
                rank=0,
            )
            for result, tokens in zip(self._agent_results, self._tokenized_documents, strict=True)
        ]
        return ranked_positive_scores(scored)


class LocalFaissVectorIndex:
    """Local FAISS-shaped vector index; swap internals for real FAISS later."""

    def __init__(self, agent_results: list[AgentResult]):
        self._agent_results = agent_results
        self._vectors = [semantic_vector(searchable_text(result)) for result in agent_results]

    def rank(self, query: str) -> list[CandidateScore]:
        query_vector = semantic_vector(query)
        scored = [
            CandidateScore(
                result=result,
                score=round(cosine_similarity(query_vector, document_vector), 6),
                rank=0,
            )
            for result, document_vector in zip(self._agent_results, self._vectors, strict=True)
        ]
        return ranked_positive_scores(scored)


def rank_agent_results(
    agent_results: list[AgentResult],
    query: str,
    filters: ChunkMetadataFilter | None = None,
    candidate_limit: int = 25,
) -> list[RetrievedChunk]:
    return retrieve_agent_results(
        agent_results,
        query,
        filters=filters,
        candidate_limit=candidate_limit,
    ).chunks


def retrieve_agent_results(
    agent_results: list[AgentResult],
    query: str,
    filters: ChunkMetadataFilter | None = None,
    candidate_limit: int = 25,
) -> HybridRetrievalResult:
    if not agent_results:
        return HybridRetrievalResult(chunks=[], diagnostics=[])

    included, filter_diagnostics = filter_agent_results(agent_results, filters or ChunkMetadataFilter())
    if not included:
        return HybridRetrievalResult(chunks=[], diagnostics=filter_diagnostics)

    bm25_ranked = Bm25Index(included).rank(query)
    vector_ranked = LocalFaissVectorIndex(included).rank(query)
    chunks, ranking_diagnostics = fuse_ranked_candidates(
        bm25_ranked,
        vector_ranked,
        filter_diagnostics,
        candidate_limit=candidate_limit,
    )
    return HybridRetrievalResult(
        chunks=chunks,
        diagnostics=[*filter_diagnostics, *ranking_diagnostics],
    )


def filter_agent_results(
    agent_results: list[AgentResult],
    filters: ChunkMetadataFilter,
) -> tuple[list[AgentResult], list[RetrievalCandidateDiagnostic]]:
    included: list[AgentResult] = []
    diagnostics: list[RetrievalCandidateDiagnostic] = []
    for result in agent_results:
        filter_path = metadata_filter_path(result, filters)
        is_included = filter_path[-1] == "metadata_filter:included"
        if is_included:
            included.append(result)
        diagnostics.append(
            RetrievalCandidateDiagnostic(
                chunk_id=result["chunk_id"],
                source_id=result["source_id"],
                candidate_source="metadata_filter",
                score=0.0,
                rank=None,
                included=is_included,
                filter_path=filter_path,
            )
        )
    return included, diagnostics


def metadata_filter_path(result: AgentResult, filters: ChunkMetadataFilter) -> list[str]:
    metadata = result.get("metadata", {})
    path: list[str] = []

    if filters.tickers:
        ticker = metadata.get("ticker", "")
        allowed_tickers = {ticker.upper() for ticker in filters.tickers}
        if ticker.upper() not in allowed_tickers:
            return [*path, f"ticker:excluded:{ticker or 'missing'}", "metadata_filter:excluded"]
        path.append(f"ticker:included:{ticker}")

    if filters.source_types:
        if result["source_type"] not in filters.source_types:
            return [
                *path,
                f"source_type:excluded:{result['source_type'].value}",
                "metadata_filter:excluded",
            ]
        path.append(f"source_type:included:{result['source_type'].value}")

    if filters.published_after or filters.published_before:
        published_at = parse_timestamp(metadata.get("published_at", ""))
        if published_at is None:
            return [*path, "published_at:excluded:missing", "metadata_filter:excluded"]
        if filters.published_after and published_at < parse_timestamp(filters.published_after):
            return [*path, f"published_at:excluded:{metadata['published_at']}", "metadata_filter:excluded"]
        if filters.published_before and published_at > parse_timestamp(filters.published_before):
            return [*path, f"published_at:excluded:{metadata['published_at']}", "metadata_filter:excluded"]
        path.append(f"published_at:included:{metadata['published_at']}")

    if filters.form_types:
        form_type = metadata.get("form_type", "")
        allowed_forms = {form.upper() for form in filters.form_types}
        if form_type.upper() not in allowed_forms:
            return [*path, f"form_type:excluded:{form_type or 'missing'}", "metadata_filter:excluded"]
        path.append(f"form_type:included:{form_type}")

    if filters.sections:
        allowed_sections = {section.casefold() for section in filters.sections}
        if result["section"].casefold() not in allowed_sections:
            return [*path, f"section:excluded:{result['section']}", "metadata_filter:excluded"]
        path.append(f"section:included:{result['section']}")

    if filters.fiscal_periods:
        period = fiscal_period(metadata)
        allowed_periods = {period.casefold() for period in filters.fiscal_periods}
        if period.casefold() not in allowed_periods:
            return [*path, f"period:excluded:{period or 'missing'}", "metadata_filter:excluded"]
        path.append(f"period:included:{period}")

    if not path:
        path.append("metadata_filter:skipped")
    return [*path, "metadata_filter:included"]


def fuse_ranked_candidates(
    bm25_ranked: list[CandidateScore],
    vector_ranked: list[CandidateScore],
    filter_diagnostics: list[RetrievalCandidateDiagnostic],
    candidate_limit: int,
) -> tuple[list[RetrievedChunk], list[RetrievalCandidateDiagnostic]]:
    candidates: dict[str, AgentResult] = {}
    bm25_scores: dict[str, float] = {}
    vector_scores: dict[str, float] = {}
    fusion_scores: dict[str, float] = {}
    matched_by: dict[str, list[str]] = {}
    filter_paths = {
        diagnostic.chunk_id: diagnostic.filter_path
        for diagnostic in filter_diagnostics
        if diagnostic.included
    }

    for source_name, ranked, score_map in (
        ("bm25", bm25_ranked, bm25_scores),
        ("vector", vector_ranked, vector_scores),
    ):
        for candidate in ranked:
            chunk_id = candidate.result["chunk_id"]
            candidates[chunk_id] = candidate.result
            score_map[chunk_id] = candidate.score
            fusion_scores[chunk_id] = fusion_scores.get(chunk_id, 0.0) + reciprocal_rank_score(candidate.rank)
            matched_by.setdefault(chunk_id, []).append(source_name)

    sorted_chunk_ids = sorted(
        fusion_scores,
        key=lambda chunk_id: (
            fusion_scores[chunk_id],
            bm25_scores.get(chunk_id, 0.0),
            vector_scores.get(chunk_id, 0.0),
        ),
        reverse=True,
    )[:candidate_limit]
    chunks = [
        to_retrieved_chunk(
            candidates[chunk_id],
            score=round(fusion_scores[chunk_id], 6),
            rank=rank,
            bm25_score=bm25_scores.get(chunk_id, 0.0),
            vector_score=vector_scores.get(chunk_id, 0.0),
            matched_by=matched_by.get(chunk_id, []),
            filter_path=filter_paths.get(chunk_id, []),
        )
        for rank, chunk_id in enumerate(sorted_chunk_ids, start=1)
    ]
    diagnostics = [
        RetrievalCandidateDiagnostic(
            chunk_id=chunk["chunk_id"],
            source_id=chunk["source_id"],
            candidate_source="+".join(chunk.get("matched_by", [])),
            score=chunk["score"],
            rank=chunk["rank"],
            included=True,
            filter_path=[
                *chunk.get("filter_path", []),
                f"bm25_score:{chunk.get('bm25_score', 0.0)}",
                f"vector_score:{chunk.get('vector_score', 0.0)}",
                f"fusion_rank:{chunk['rank']}",
            ],
        )
        for chunk in chunks
    ]
    return chunks, diagnostics


def ranked_positive_scores(scored: list[CandidateScore]) -> list[CandidateScore]:
    ranked = sorted(
        (candidate for candidate in scored if candidate.score > 0),
        key=lambda candidate: candidate.score,
        reverse=True,
    )
    return [
        CandidateScore(result=candidate.result, score=candidate.score, rank=rank)
        for rank, candidate in enumerate(ranked, start=1)
    ]


def reciprocal_rank_score(rank: int) -> float:
    return 1 / (RRF_K + rank)


def searchable_text(result: AgentResult) -> str:
    metadata = result.get("metadata", {})
    metadata_text = " ".join(
        metadata.get(field, "")
        for field in (
            "ticker",
            "company_name",
            "document_title",
            "provider",
            "form_type",
            "period",
            "fiscal_quarter",
            "fiscal_year",
        )
    )
    return f"{metadata_text} {result['title']} {result['section']} {result['text']}"


def rewrite_finance_query(query: str) -> str:
    expanded_terms = list(tokenize(query))
    query_lower = query.lower()
    for phrase, replacements in PHRASE_EXPANSIONS.items():
        if phrase in query_lower:
            expanded_terms.extend(replacements)
    for token in list(expanded_terms):
        expanded_terms.extend(QUERY_EXPANSIONS.get(token, ()))
    return " ".join(expanded_terms)


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def semantic_vector(value: str) -> Counter[str]:
    return Counter(semantic_token(token) for token in tokenize(value))


def semantic_token(token: str) -> str:
    return SEMANTIC_ALIASES.get(token, token)


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0

    numerator = sum(left[token] * right.get(token, 0) for token in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def average_document_length(tokenized_documents: list[list[str]]) -> float:
    if not tokenized_documents:
        return 0.0
    return sum(len(tokens) for tokens in tokenized_documents) / len(tokenized_documents)


def bm25_score(
    document_tokens: list[str],
    query_terms: Counter[str],
    document_frequency: Counter[str],
    document_count: int,
    average_document_length: float,
) -> float:
    if not document_tokens or not query_terms or average_document_length == 0:
        return 0.0

    term_frequency = Counter(document_tokens)
    document_length = len(document_tokens)
    k1 = 1.2
    b = 0.75
    score = 0.0
    for term, query_count in query_terms.items():
        if term not in term_frequency:
            continue
        idf = math.log(1 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
        tf_component = (
            term_frequency[term] * (k1 + 1)
        ) / (
            term_frequency[term]
            + k1 * (1 - b + b * document_length / average_document_length)
        )
        score += idf * tf_component * query_count
    return round(score, 6)


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def fiscal_period(metadata: dict[str, str]) -> str:
    if metadata.get("period"):
        return metadata["period"]
    return " ".join(value for value in (metadata.get("fiscal_year", ""), metadata.get("fiscal_quarter", "")) if value)


def to_retrieved_chunk(
    result: AgentResult,
    score: float,
    rank: int = 0,
    bm25_score: float = 0.0,
    vector_score: float = 0.0,
    matched_by: list[str] | None = None,
    filter_path: list[str] | None = None,
) -> RetrievedChunk:
    return {
        "source_id": result["source_id"],
        "chunk_id": result["chunk_id"],
        "evidence_id": result["evidence_id"],
        "source_type": result["source_type"],
        "title": result["title"],
        "url": result["url"],
        "section": result["section"],
        "text": result["text"],
        "content_hash": result["content_hash"],
        "score": score,
        "rank": rank,
        "bm25_score": bm25_score,
        "vector_score": vector_score,
        "fusion_score": score,
        "matched_by": matched_by or [],
        "filter_path": filter_path or [],
        "metadata": result.get("metadata", {}),
    }
