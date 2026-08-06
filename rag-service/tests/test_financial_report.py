import pytest

from rag_service.financial_report import (
    LlmProviderError,
    PROMPT_TEMPLATES,
    LocalFinancialReportGenerator,
    OpenAiFinancialReportGenerator,
    extract_response_text,
    financial_report_generator_from_env,
    StructuredReportValidationError,
    build_prompt,
    repair_structured_report_payload,
    validate_or_repair_report_payload,
    validate_structured_report_payload,
)
from rag_service.models import GenerateReportRequest, ReportType, SourceFilter
from rag_service.state import RetrievedChunk


def test_prompt_templates_cover_each_report_type_and_require_json_sections():
    assert set(PROMPT_TEMPLATES) == set(ReportType)

    for report_type in ReportType:
        prompt = build_prompt(
            GenerateReportRequest(
                tickers=["NVDA"],
                question="What changed?",
                report_type=report_type,
            ),
            ["NVDA"],
            [context_chunk("sec-risk", SourceFilter.SEC, "Risk factors discuss export controls.", "C1")],
        )

        assert "Return JSON matching the StructuredFinancialReport schema." in prompt
        assert "Executive Summary" in prompt
        assert "Source Citations" in prompt
        assert "[C1]" in prompt


def test_local_generator_creates_structured_report_with_cited_material_claims():
    result = LocalFinancialReportGenerator().generate(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="Which risk factors changed?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        ),
        ["NVDA"],
        [
            context_chunk(
                "sec-risk",
                SourceFilter.SEC,
                "Risk factors discuss export controls and customer concentration.",
                "C1",
                section="Risk Factors",
            )
        ],
    )

    assert result.validation_status == "validated"
    assert result.hallucination_warnings == []
    assert "C1" in result.report.executive_summary
    assert result.report.latest_sec_filing_signals[0].citation_ids == ["C1"]
    assert result.report.source_citations[0].citation_id == "C1"


def test_openai_generator_uses_mocked_llm_payload_when_valid():
    result = OpenAiFinancialReportGenerator(
        MockStructuredReportClient(valid_llm_payload())
    ).generate(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="Which risk factors changed?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        ),
        ["NVDA"],
        [context_chunk("sec-risk", SourceFilter.SEC, "Risk factors discuss export controls.", "C1")],
    )

    assert result.provider == "openai_llm"
    assert result.validation_status == "validated"
    assert result.hallucination_warnings == []
    assert result.report.executive_summary == "OpenAI structured summary based on cited evidence [C1]."
    assert result.report.key_evidence[0].citation_ids == ["C1"]


def test_openai_generator_repairs_mocked_llm_payload_when_citation_is_missing():
    payload = valid_llm_payload()
    payload["executive_summary"] = "OpenAI summary missing a citation."
    payload["key_evidence"][0]["citation_ids"] = []

    result = OpenAiFinancialReportGenerator(MockStructuredReportClient(payload)).generate(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="Which risk factors changed?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        ),
        ["NVDA"],
        [context_chunk("sec-risk", SourceFilter.SEC, "Risk factors discuss export controls.", "C1")],
    )

    assert result.provider == "openai_llm"
    assert result.validation_status == "repaired"
    assert result.repair_attempted is True
    assert "C1" in result.report.executive_summary
    assert result.report.key_evidence[0].citation_ids == ["C1"]


def test_openai_generator_falls_back_to_local_generation_when_provider_fails():
    result = OpenAiFinancialReportGenerator(FailingStructuredReportClient()).generate(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="Which risk factors changed?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        ),
        ["NVDA"],
        [context_chunk("sec-risk", SourceFilter.SEC, "Risk factors discuss export controls.", "C1")],
    )

    assert result.provider == "local_retrieval"
    assert result.validation_status == "fallback_after_openai_error:LlmProviderError"
    assert any("OpenAI LLM generation failed" in warning for warning in result.hallucination_warnings)
    assert "Local structured" in result.report.executive_summary


def test_financial_report_generator_from_env_selects_openai_only_when_fully_configured():
    local_generator = financial_report_generator_from_env({})
    openai_generator = financial_report_generator_from_env(
        {
            "RAG_LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
        }
    )

    assert isinstance(local_generator, LocalFinancialReportGenerator)
    assert isinstance(openai_generator, OpenAiFinancialReportGenerator)


def test_extract_response_text_supports_responses_api_shapes():
    assert extract_response_text({"output_text": "{\"executive_summary\":\"ok [C1]\"}"}) == "{\"executive_summary\":\"ok [C1]\"}"
    assert extract_response_text(
        {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "{\"executive_summary\":\"nested [C1]\"}"}
                    ]
                }
            ]
        }
    ) == "{\"executive_summary\":\"nested [C1]\"}"


def test_generator_reports_missing_data_instead_of_fabricating_sources():
    result = LocalFinancialReportGenerator().generate(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="Summarize all sources.",
            report_type=ReportType.COMPANY_BRIEF,
            source_filters=[SourceFilter.SEC, SourceFilter.NEWS, SourceFilter.EARNINGS],
        ),
        ["NVDA"],
        [context_chunk("sec-risk", SourceFilter.SEC, "Risk factors discuss export controls.", "C1")],
    )

    assert "No recent news evidence was selected for this report." in result.report.methodology_and_limitations
    assert "No earnings or guidance evidence was selected for this report." in result.report.methodology_and_limitations
    assert result.report.recent_news_signals == []
    assert result.report.earnings_and_guidance_signals == []


def test_structured_report_validation_catches_malformed_payloads():
    malformed_payload = {
        "executive_summary": "Unsupported claim without a valid citation.",
        "key_evidence": [{"claim": "Claim cites missing evidence.", "citation_ids": ["C99"]}],
        "source_citations": [],
        "methodology_and_limitations": ["Generated from selected cited local RAG context only."],
    }

    with pytest.raises(StructuredReportValidationError):
        validate_structured_report_payload(malformed_payload)


def test_repair_path_fixes_missing_citations_and_summary_reference():
    selected_context = [
        context_chunk(
            "sec-risk",
            SourceFilter.SEC,
            "Risk factors discuss export controls.",
            "C1",
        )
    ]
    payload = {
        "executive_summary": "Summary has no citation marker.",
        "key_evidence": [{"claim": "Risk factors discuss export controls.", "citation_ids": []}],
        "source_citations": [],
        "methodology_and_limitations": [],
    }

    report, status, repair_attempted = validate_or_repair_report_payload(payload, selected_context)

    assert status == "repaired"
    assert repair_attempted is True
    assert "C1" in report.executive_summary
    assert report.key_evidence[0].citation_ids == ["C1"]
    assert report.source_citations[0].citation_id == "C1"


def test_repair_structured_report_payload_removes_unknown_citation_ids():
    selected_context = [context_chunk("sec-risk", SourceFilter.SEC, "Risk text.", "C1")]
    repaired = repair_structured_report_payload(
        {
            "executive_summary": "Summary [C99]",
            "key_evidence": [{"claim": "Risk text.", "citation_ids": ["C99"]}],
            "source_citations": [],
        },
        selected_context,
    )

    assert repaired["key_evidence"][0]["citation_ids"] == ["C1"]
    assert "C1" in repaired["executive_summary"]


def context_chunk(
    source_id: str,
    source_type: SourceFilter,
    text: str,
    citation_id: str,
    section: str = "Risk Factors",
) -> RetrievedChunk:
    return {
        "source_id": source_id,
        "chunk_id": f"{source_id}#chunk-001",
        "evidence_id": f"{source_id}#chunk-001",
        "source_type": source_type,
        "title": "Local source title",
        "url": f"https://example.com/{source_id}",
        "section": section,
        "text": text,
        "content_hash": f"{source_id}-hash",
        "score": 0.8,
        "rank": 1,
        "context_citation_id": citation_id,
        "context_rank": 1,
        "context_token_count": 8,
        "context_span_start_token": 0,
        "context_span_end_token": 8,
        "evidence_signal": "negative",
        "metadata": {
            "ticker": "NVDA",
            "source_type": source_type.value,
            "published_at": "2026-05-28",
            "document_title": "Local source title",
            "document_url": f"https://example.com/{source_id}",
            "context_citation_id": citation_id,
        },
    }


def valid_llm_payload() -> dict:
    return {
        "executive_summary": "OpenAI structured summary based on cited evidence [C1].",
        "key_evidence": [
            {
                "claim": "Risk factors discuss export controls. [C1]",
                "citation_ids": ["C1"],
            }
        ],
        "source_citations": [
            {
                "citation_id": "C1",
                "evidence_id": "sec-risk#chunk-001",
                "source_type": "SEC",
                "title": "Local source title",
                "url": "https://example.com/sec-risk",
                "section": "Risk Factors",
                "source_metadata": {"published_at": "2026-05-28"},
            }
        ],
        "methodology_and_limitations": ["Generated from selected cited RAG context only."],
    }


class MockStructuredReportClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def generate_structured_report(self, prompt: str) -> dict:
        assert "Return JSON matching the StructuredFinancialReport schema." in prompt
        return self.payload


class FailingStructuredReportClient:
    def generate_structured_report(self, prompt: str) -> dict:
        raise LlmProviderError("provider down")
