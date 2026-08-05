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

    assert response.citations[0].evidence_id == "nvda-sec-risk-001"
    assert "export controls" in response.key_findings[0]
    assert response.diagnostics.mode == "local_retrieval"
