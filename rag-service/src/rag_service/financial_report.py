from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError, field_validator

from rag_service.models import ContractModel, GenerateReportRequest, ReportType, SourceFilter
from rag_service.state import RetrievedChunk


SECTION_NAMES = (
    "Executive Summary",
    "Company And Ticker Context",
    "Latest SEC Filing Signals",
    "Recent News Signals",
    "Earnings And Guidance Signals",
    "Bull Case",
    "Bear Case",
    "Key Risks And Unknowns",
    "Evidence Timeline",
    "Source Citations",
    "Methodology And Limitations",
)

PROMPT_TEMPLATES = {
    ReportType.COMPANY_BRIEF: (
        "Create a concise company brief using only the provided cited context. "
        "Balance SEC, news, and earnings evidence when available."
    ),
    ReportType.EARNINGS_BRIEF: (
        "Create an earnings brief focused on prepared remarks, Q&A, guidance, "
        "margins, capital expenditure, buybacks, risks, and speaker attribution."
    ),
    ReportType.FILING_ANALYSIS: (
        "Create a filing analysis focused on SEC sections, filing type, filing date, "
        "risk factors, MD&A, financial statement signals, and material changes."
    ),
    ReportType.EVENT_DRIVEN: (
        "Create an event-driven report focused on recent news, timeline, market reaction, "
        "legal/regulatory developments, and uncertainty."
    ),
    ReportType.COMPARATIVE: (
        "Create a comparative report across requested tickers using only cited evidence. "
        "Separate common themes from ticker-specific signals."
    ),
}

MISSING_SOURCE_LIMITATIONS = {
    SourceFilter.SEC: "No SEC filing evidence was selected for this report.",
    SourceFilter.NEWS: "No recent news evidence was selected for this report.",
    SourceFilter.EARNINGS: "No earnings or guidance evidence was selected for this report.",
}

SOURCE_SECTION_LABELS = {
    SourceFilter.SEC: "Latest SEC Filing Signals",
    SourceFilter.NEWS: "Recent News Signals",
    SourceFilter.EARNINGS: "Earnings And Guidance Signals",
}


class EvidenceClaim(ContractModel):
    claim: str = Field(min_length=1)
    citation_ids: list[str] = Field(min_length=1)

    @field_validator("citation_ids")
    @classmethod
    def citation_ids_must_be_context_ids(cls, value: list[str]) -> list[str]:
        for citation_id in value:
            if not citation_id.startswith("C"):
                raise ValueError("citation IDs must reference context citations")
        return value


class TimelineEvent(ContractModel):
    date: str
    event: str = Field(min_length=1)
    citation_ids: list[str] = Field(default_factory=list)


class ReportCitation(ContractModel):
    citation_id: str
    evidence_id: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    source_metadata: dict[str, str] = Field(default_factory=dict)


class StructuredFinancialReport(ContractModel):
    executive_summary: str = Field(min_length=1)
    key_evidence: list[EvidenceClaim] = Field(default_factory=list)
    company_and_ticker_context: list[EvidenceClaim] = Field(default_factory=list)
    latest_sec_filing_signals: list[EvidenceClaim] = Field(default_factory=list)
    recent_news_signals: list[EvidenceClaim] = Field(default_factory=list)
    earnings_and_guidance_signals: list[EvidenceClaim] = Field(default_factory=list)
    bull_case: list[EvidenceClaim] = Field(default_factory=list)
    bear_case: list[EvidenceClaim] = Field(default_factory=list)
    key_risks_and_unknowns: list[EvidenceClaim] = Field(default_factory=list)
    evidence_timeline: list[TimelineEvent] = Field(default_factory=list)
    source_citations: list[ReportCitation] = Field(default_factory=list)
    methodology_and_limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ReportGenerationResult:
    report: StructuredFinancialReport
    prompt: str
    validation_status: str
    repair_attempted: bool
    hallucination_warnings: list[str]


class StructuredReportValidationError(ValueError):
    pass


class LocalFinancialReportGenerator:
    def generate(
        self,
        request: GenerateReportRequest,
        tickers: list[str],
        selected_context: list[RetrievedChunk],
    ) -> ReportGenerationResult:
        prompt = build_prompt(request, tickers, selected_context)
        raw_payload = build_report_payload(request, tickers, selected_context)
        report, validation_status, repair_attempted = validate_or_repair_report_payload(raw_payload, selected_context)
        hallucination_warnings = hallucination_warnings_for(report)
        if hallucination_warnings:
            repaired_payload = repair_structured_report_payload(report.model_dump(mode="json"), selected_context)
            report = StructuredFinancialReport.model_validate(repaired_payload)
            hallucination_warnings = hallucination_warnings_for(report)
            repair_attempted = True
            validation_status = "repaired"
        return ReportGenerationResult(
            report=report,
            prompt=prompt,
            validation_status=validation_status,
            repair_attempted=repair_attempted,
            hallucination_warnings=hallucination_warnings,
        )


def build_prompt(
    request: GenerateReportRequest,
    tickers: list[str],
    selected_context: list[RetrievedChunk],
) -> str:
    template = PROMPT_TEMPLATES[request.report_type]
    context_lines = [
        (
            f"[{citation_id_for(chunk)}] {chunk['source_type'].value} | "
            f"{chunk['title']} | {chunk['section']} | "
            f"published_at={chunk.get('metadata', {}).get('published_at', 'unknown')} | "
            f"{chunk['text']}"
        )
        for chunk in selected_context
    ]
    return "\n".join(
        [
            template,
            "Return JSON matching the StructuredFinancialReport schema.",
            "Every material claim must include at least one citation ID from the provided context.",
            f"Tickers: {', '.join(tickers)}",
            f"Question: {request.question}",
            f"Report type: {request.report_type.value}",
            "Required sections: " + "; ".join(SECTION_NAMES),
            "Context:",
            *context_lines,
        ]
    )


def build_report_payload(
    request: GenerateReportRequest,
    tickers: list[str],
    selected_context: list[RetrievedChunk],
) -> dict[str, Any]:
    citations = [report_citation_for(chunk) for chunk in selected_context]
    claims = [evidence_claim_for(chunk) for chunk in selected_context]
    claims_by_source = {
        source_type: [claim for claim, chunk in zip(claims, selected_context, strict=True) if chunk["source_type"] == source_type]
        for source_type in SourceFilter
    }
    positive_claims = [
        claim
        for claim, chunk in zip(claims, selected_context, strict=True)
        if chunk.get("evidence_signal") == "positive"
    ]
    bearish_claims = [
        claim
        for claim, chunk in zip(claims, selected_context, strict=True)
        if chunk.get("evidence_signal") in {"negative", "mixed"}
    ]
    uncertainty_claims = [
        claim
        for claim, chunk in zip(claims, selected_context, strict=True)
        if chunk.get("evidence_signal") in {"uncertainty", "mixed", "negative"}
    ]

    if not positive_claims and claims:
        positive_claims = claims[:1]
    if not bearish_claims and claims:
        bearish_claims = claims[-1:]
    if not uncertainty_claims and claims:
        uncertainty_claims = claims[-1:]

    return {
        "executive_summary": executive_summary_for(request, tickers, selected_context),
        "key_evidence": claims[:5],
        "company_and_ticker_context": company_context_claims(tickers, claims),
        "latest_sec_filing_signals": claims_by_source[SourceFilter.SEC],
        "recent_news_signals": claims_by_source[SourceFilter.NEWS],
        "earnings_and_guidance_signals": claims_by_source[SourceFilter.EARNINGS],
        "bull_case": positive_claims[:3],
        "bear_case": bearish_claims[:3],
        "key_risks_and_unknowns": uncertainty_claims[:3],
        "evidence_timeline": timeline_events_for(selected_context),
        "source_citations": citations,
        "methodology_and_limitations": limitations_for(request, selected_context),
    }


def validate_or_repair_report_payload(
    payload: dict[str, Any],
    selected_context: list[RetrievedChunk],
) -> tuple[StructuredFinancialReport, str, bool]:
    try:
        return validate_structured_report_payload(payload), "validated", False
    except (ValidationError, StructuredReportValidationError):
        repaired_payload = repair_structured_report_payload(payload, selected_context)
        return validate_structured_report_payload(repaired_payload), "repaired", True


def validate_structured_report_payload(payload: dict[str, Any]) -> StructuredFinancialReport:
    report = StructuredFinancialReport.model_validate(payload)
    warnings = hallucination_warnings_for(report)
    if warnings:
        raise StructuredReportValidationError("; ".join(warnings))
    return report


def repair_structured_report_payload(
    payload: dict[str, Any],
    selected_context: list[RetrievedChunk],
) -> dict[str, Any]:
    repaired = dict(payload)
    source_citations = repaired.get("source_citations") or [
        report_citation_for(chunk) for chunk in selected_context
    ]
    valid_citation_ids = {
        citation["citation_id"] if isinstance(citation, dict) else citation.citation_id
        for citation in source_citations
    }
    fallback_citation_id = next(iter(valid_citation_ids), "C1")
    repaired["executive_summary"] = repaired.get("executive_summary") or "No cited evidence was available."
    if valid_citation_ids and not any(citation_id in repaired["executive_summary"] for citation_id in valid_citation_ids):
        repaired["executive_summary"] = f"{repaired['executive_summary']} [{fallback_citation_id}]"
    repaired["source_citations"] = source_citations
    for field in evidence_claim_fields():
        repaired[field] = repair_claim_list(repaired.get(field, []), fallback_citation_id, valid_citation_ids)
    repaired["evidence_timeline"] = repair_timeline_events(
        repaired.get("evidence_timeline", []),
        fallback_citation_id,
        valid_citation_ids,
    )
    repaired["methodology_and_limitations"] = repaired.get("methodology_and_limitations") or [
        "Generated from selected cited local RAG context only."
    ]
    return repaired


def hallucination_warnings_for(report: StructuredFinancialReport) -> list[str]:
    warnings: list[str] = []
    valid_citation_ids = {citation.citation_id for citation in report.source_citations}
    if valid_citation_ids and not any(citation_id in report.executive_summary for citation_id in valid_citation_ids):
        warnings.append("executive_summary has no citation reference")
    for field in evidence_claim_fields():
        claims: list[EvidenceClaim] = getattr(report, field)
        for index, claim in enumerate(claims):
            if not claim.citation_ids:
                warnings.append(f"{field}[{index}] has no citation")
                continue
            unknown_ids = [citation_id for citation_id in claim.citation_ids if citation_id not in valid_citation_ids]
            if unknown_ids:
                warnings.append(f"{field}[{index}] references unknown citations: {', '.join(unknown_ids)}")
    for index, event in enumerate(report.evidence_timeline):
        unknown_ids = [citation_id for citation_id in event.citation_ids if citation_id not in valid_citation_ids]
        if unknown_ids:
            warnings.append(f"evidence_timeline[{index}] references unknown citations: {', '.join(unknown_ids)}")
    return warnings


def flatten_report_to_key_findings(report: StructuredFinancialReport) -> list[str]:
    findings = [
        format_claim("Key Evidence", claim)
        for claim in report.key_evidence
    ]
    if not findings:
        findings.extend(report.methodology_and_limitations)
    return findings


def citation_id_for(chunk: RetrievedChunk) -> str:
    return chunk.get("context_citation_id") or chunk.get("metadata", {}).get("context_citation_id", "C?")


def evidence_claim_for(chunk: RetrievedChunk) -> dict[str, Any]:
    citation_id = citation_id_for(chunk)
    claim = f"{chunk['source_type'].value} evidence from {chunk['section']} says {chunk['text']} [{citation_id}]"
    return {"claim": claim, "citation_ids": [citation_id]}


def report_citation_for(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "citation_id": citation_id_for(chunk),
        "evidence_id": chunk["evidence_id"],
        "source_type": chunk["source_type"],
        "title": chunk["title"],
        "url": chunk["url"],
        "section": chunk["section"],
        "source_metadata": dict(chunk.get("metadata", {})),
    }


def executive_summary_for(
    request: GenerateReportRequest,
    tickers: list[str],
    selected_context: list[RetrievedChunk],
) -> str:
    report_label = request.report_type.value.lower().replace("_", " ")
    if not selected_context:
        return (
            f"Local structured {report_label} for {', '.join(tickers)} could not find cited evidence "
            "for the requested source filters."
        )
    citation_ids = ", ".join(citation_id_for(chunk) for chunk in selected_context[:3])
    return (
        f"Local structured {report_label} for {', '.join(tickers)} is based only on "
        f"{len(selected_context)} cited evidence items ({citation_ids})."
    )


def company_context_claims(tickers: list[str], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if claims:
        ticker_label = ", ".join(tickers)
        first_claim = dict(claims[0])
        first_claim["claim"] = f"{ticker_label} context is grounded in selected cited evidence. {first_claim['claim']}"
        return [first_claim]
    return []


def timeline_events_for(selected_context: list[RetrievedChunk]) -> list[dict[str, Any]]:
    events = []
    for chunk in selected_context:
        published_at = chunk.get("metadata", {}).get("published_at", "")
        if not published_at:
            continue
        citation_id = citation_id_for(chunk)
        events.append(
            {
                "date": published_at,
                "event": f"{chunk['source_type'].value} evidence from {chunk['section']} was published. [{citation_id}]",
                "citation_ids": [citation_id],
            }
        )
    return sorted(events, key=lambda event: (event["date"], event["event"]))


def limitations_for(
    request: GenerateReportRequest,
    selected_context: list[RetrievedChunk],
) -> list[str]:
    selected_source_types = {chunk["source_type"] for chunk in selected_context}
    limitations = [
        "Generated from selected cited local RAG context only.",
        "This is not trading advice and does not place orders.",
    ]
    for source_filter in request.source_filters or SourceFilter.defaults():
        if source_filter not in selected_source_types:
            limitations.append(MISSING_SOURCE_LIMITATIONS[source_filter])
    if not selected_context:
        limitations.append("No cited evidence matched the request; missing data is reported instead of fabricated.")
    return limitations


def repair_claim_list(
    values: Any,
    fallback_citation_id: str,
    valid_citation_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        values = []
    repaired = []
    for value in values:
        if isinstance(value, EvidenceClaim):
            item = value.model_dump(mode="json")
        elif isinstance(value, dict):
            item = dict(value)
        elif isinstance(value, str):
            item = {"claim": value}
        else:
            continue
        citation_ids = [
            citation_id
            for citation_id in item.get("citation_ids", [])
            if citation_id in valid_citation_ids
        ]
        item["citation_ids"] = citation_ids or [fallback_citation_id]
        item["claim"] = item.get("claim") or "Claim repaired from cited evidence."
        repaired.append(item)
    return repaired


def repair_timeline_events(
    values: Any,
    fallback_citation_id: str,
    valid_citation_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    repaired = []
    for value in values:
        if isinstance(value, TimelineEvent):
            item = value.model_dump(mode="json")
        elif isinstance(value, dict):
            item = dict(value)
        else:
            continue
        item["date"] = item.get("date", "")
        item["event"] = item.get("event") or "Timeline event repaired from cited evidence."
        citation_ids = [
            citation_id
            for citation_id in item.get("citation_ids", [])
            if citation_id in valid_citation_ids
        ]
        item["citation_ids"] = citation_ids or [fallback_citation_id]
        repaired.append(item)
    return repaired


def format_claim(section: str, claim: EvidenceClaim) -> str:
    citation_ids = ", ".join(claim.citation_ids)
    if citation_ids and citation_ids not in claim.claim:
        return f"{section}: {claim.claim} [{citation_ids}]"
    return f"{section}: {claim.claim}"


def evidence_claim_fields() -> tuple[str, ...]:
    return (
        "key_evidence",
        "company_and_ticker_context",
        "latest_sec_filing_signals",
        "recent_news_signals",
        "earnings_and_guidance_signals",
        "bull_case",
        "bear_case",
        "key_risks_and_unknowns",
    )
