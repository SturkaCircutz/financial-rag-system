from fastapi.testclient import TestClient

from rag_service.api import app


def test_generate_report_endpoint_matches_backend_contract():
    client = TestClient(app)

    response = client.post(
        "/v1/reports:generate",
        json={
            "tickers": ["NVDA"],
            "question": "What are the latest risk factors?",
            "reportType": "COMPANY_BRIEF",
            "timeHorizon": "30d",
            "sourceFilters": ["SEC"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]
    assert len(body["keyFindings"]) == 1
    assert body["sourceCoverage"]["secChunks"] == 1
    assert body["sourceCoverage"]["newsChunks"] == 0
    assert body["sourceCoverage"]["earningsChunks"] == 0
    assert body["diagnostics"]["ragServiceStatus"] == "completed"
