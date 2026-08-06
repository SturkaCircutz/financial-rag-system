from rag_service.graph import build_graph, generate_report_from_graph
from rag_service.models import GenerateReportRequest, ReportType, SourceFilter


def test_graph_generates_report_with_selected_sources():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["nvda"],
            question="What changed in the latest filing?",
            report_type=ReportType.FILING_ANALYSIS,
            time_horizon="30d",
            source_filters=[SourceFilter.SEC, SourceFilter.NEWS],
        )
    )

    assert "filing analysis" in response.summary
    assert len(response.key_findings) >= 2
    assert response.source_coverage.sec_chunks >= 1
    assert response.source_coverage.news_chunks >= 1
    assert response.source_coverage.earnings_chunks == 0
    assert {citation.source_type for citation in response.citations} == {
        SourceFilter.SEC,
        SourceFilter.NEWS,
    }
    assert response.diagnostics.rag_service_status == "completed"


def test_graph_defaults_to_all_sources_and_records_trace():
    graph = build_graph()
    final_state = graph.invoke(
        {
            "request": GenerateReportRequest(
                tickers=["msft"],
                question="Summarize recent signals.",
                report_type=ReportType.COMPANY_BRIEF,
            )
        }
    )

    response = final_state["response"]

    assert len(response.key_findings) >= 3
    assert response.source_coverage.sec_chunks >= 1
    assert response.source_coverage.news_chunks >= 1
    assert response.source_coverage.earnings_chunks >= 1
    assert final_state["diagnostics"]["rerankerStatus"] == "completed"
    assert int(final_state["diagnostics"]["contextTokenCount"]) <= int(final_state["diagnostics"]["contextTokenBudget"])
    assert final_state["rerank_diagnostics"]
    assert final_state["context_citation_map"]
    assert final_state["structured_report"]
    assert final_state["diagnostics"]["reportValidationStatus"] in {"validated", "repaired"}
    assert final_state["diagnostics"]["hallucinationWarningCount"] == "0"
    assert all("reranker_score" in chunk for chunk in final_state["selected_context"])
    assert all("context_citation_id" in chunk["metadata"] for chunk in final_state["selected_context"])
    assert all("[C" in finding for finding in response.key_findings)
    assert [event["node"] for event in final_state["trace"]] == [
        "plan_request",
        "sec_agent",
        "news_agent",
        "earnings_agent",
        "hybrid_retriever",
        "reranker",
        "context_builder",
        "llm_generation",
        "report_validation",
    ]


def test_graph_ranks_question_relevant_evidence_first():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["nvda"],
            question="Which export controls and risk factors changed?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        )
    )

    assert response.citations[0].section == "Risk Factors"
    assert "export" in response.key_findings[0]
    assert response.diagnostics.mode == "local_retrieval"


def test_graph_renders_sec_metadata_in_citations():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["nvda"],
            question="Which filing discusses export licensing uncertainty?",
            report_type=ReportType.FILING_ANALYSIS,
            source_filters=[SourceFilter.SEC],
        )
    )

    sec_citation = next(
        citation
        for citation in response.citations
        if citation.source_metadata.get("accession_number") == "local-nvda-2026q1-10q"
    )

    assert sec_citation.section == "Risk Factors"
    assert sec_citation.source_metadata["cik"] == "0001045810"
    assert sec_citation.source_metadata["form_type"] == "10-Q"


def test_graph_renders_news_metadata_in_citations():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["nvda"],
            question="Which news discussed export-control rule changes and China demand?",
            report_type=ReportType.EVENT_DRIVEN,
            source_filters=[SourceFilter.NEWS],
        )
    )

    news_citation = next(
        citation
        for citation in response.citations
        if citation.source_metadata.get("canonical_url") == "https://example.com/news/nvda/export-control-update"
    )

    assert news_citation.section == "breaking news"
    assert news_citation.source_metadata["publisher"] == "Local Market Wire"
    assert news_citation.source_metadata["published_at"] == "2026-08-01T13:30:00Z"


def test_graph_renders_earnings_metadata_in_citations():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["msft"],
            question="Which speaker discussed capital expenditure priorities?",
            report_type=ReportType.EARNINGS_BRIEF,
            source_filters=[SourceFilter.EARNINGS],
        )
    )

    earnings_citation = next(
        citation
        for citation in response.citations
        if citation.source_metadata.get("topic") == "Capital Expenditure"
    )

    assert earnings_citation.section == "Q&A"
    assert earnings_citation.source_metadata["speaker"] == "Amy Hood"
    assert earnings_citation.source_metadata["fiscal_quarter"] == "Q4"


def test_graph_reports_missing_data_without_fabricating_evidence():
    response = generate_report_from_graph(
        GenerateReportRequest(
            tickers=["unknown"],
            question="Summarize all available sources.",
            report_type=ReportType.COMPANY_BRIEF,
            source_filters=[SourceFilter.SEC, SourceFilter.NEWS, SourceFilter.EARNINGS],
        )
    )

    assert "could not find cited evidence" in response.summary
    assert response.citations == []
    assert any("No SEC filing evidence" in finding for finding in response.key_findings)
    assert any("No recent news evidence" in finding for finding in response.key_findings)
    assert any("No earnings or guidance evidence" in finding for finding in response.key_findings)
