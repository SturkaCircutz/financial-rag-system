import math
import re
from collections import Counter

from rag_service.state import AgentResult, RetrievedChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def rank_agent_results(agent_results: list[AgentResult], query: str) -> list[RetrievedChunk]:
    if not agent_results:
        return []

    tokenized_documents = [
        tokenize(f"{result['title']} {result['text']}")
        for result in agent_results
    ]
    query_terms = Counter(tokenize(query))
    document_count = len(tokenized_documents)
    average_document_length = sum(len(tokens) for tokens in tokenized_documents) / document_count
    document_frequency = Counter(
        token
        for tokens in tokenized_documents
        for token in set(tokens)
    )

    chunks = [
        to_retrieved_chunk(
            result,
            bm25_score(
                document_tokens=tokens,
                query_terms=query_terms,
                document_frequency=document_frequency,
                document_count=document_count,
                average_document_length=average_document_length,
            ),
        )
        for result, tokens in zip(agent_results, tokenized_documents, strict=True)
    ]
    return sorted(chunks, key=lambda chunk: chunk["score"], reverse=True)


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def bm25_score(
    document_tokens: list[str],
    query_terms: Counter[str],
    document_frequency: Counter[str],
    document_count: int,
    average_document_length: float,
) -> float:
    if not document_tokens or not query_terms:
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


def to_retrieved_chunk(result: AgentResult, score: float) -> RetrievedChunk:
    return {
        "evidence_id": result["evidence_id"],
        "source_type": result["source_type"],
        "title": result["title"],
        "url": result["url"],
        "text": result["text"],
        "score": score,
    }
