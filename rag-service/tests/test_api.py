from rag_service.api import generate_report
from rag_service.models import GenerateReportRequest, ReportType, SourceFilter


def test_generate_report_endpoint_matches_backend_contract():
    response = generate_report(
        GenerateReportRequest(
            tickers=["NVDA"],
            question="What are the latest risk factors?",
            report_type=ReportType.COMPANY_BRIEF,
            time_horizon="30d",
            source_filters=[SourceFilter.SEC],
        )
    )

    body = response.model_dump(by_alias=True)
    assert body["summary"]
    assert len(body["keyFindings"]) >= 1
    assert body["sourceCoverage"]["secChunks"] >= 1
    assert body["sourceCoverage"]["newsChunks"] == 0
    assert body["sourceCoverage"]["earningsChunks"] == 0
    assert body["diagnostics"]["ragServiceStatus"] == "completed"
    assert body["diagnostics"]["mode"] == "local_retrieval"
    assert any(
        citation["section"] == "Risk Factors"
        and citation["sourceMetadata"].get("form_type") == "10-Q"
        for citation in body["citations"]
    )
