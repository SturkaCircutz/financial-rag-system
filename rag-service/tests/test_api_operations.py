from fastapi.testclient import TestClient

from rag_service import api
from rag_service.api import app
from rag_service.models import GenerateReportRequest, ReportType, SourceFilter
from rag_service.operations import METRICS, reset_operation_state


def test_http_generate_report_adds_trace_headers_and_metrics():
    reset_operation_state()
    client = TestClient(app)

    response = client.post(
        "/v1/reports:generate",
        headers={"X-Request-Id": "request-test", "X-Trace-Id": "trace-test"},
        json={
            "tickers": ["NVDA"],
            "question": "Which filing discusses export controls?",
            "reportType": "FILING_ANALYSIS",
            "sourceFilters": ["SEC"],
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "request-test"
    assert response.headers["X-Trace-Id"] == "trace-test"
    assert response.json()["diagnostics"]["ragServiceStatus"] == "completed"
    assert "rag.requests.total{method=POST,path=/v1/reports:generate,status=200}" in METRICS.snapshot()["counters"]


def test_generate_report_uses_local_cache_for_same_request():
    reset_operation_state()
    request = GenerateReportRequest(
        tickers=["NVDA"],
        question="Which filing discusses export controls?",
        report_type=ReportType.FILING_ANALYSIS,
        source_filters=[SourceFilter.SEC],
    )

    first = api.generate_report(request)
    second = api.generate_report(request)

    assert first.summary == second.summary
    counters = METRICS.snapshot()["counters"]
    assert counters["rag.cache.miss.total{workflow=generate_report}"] == 1
    assert counters["rag.cache.hit.total{workflow=generate_report}"] == 1


def test_rate_limit_returns_429(monkeypatch):
    reset_operation_state()
    client = TestClient(app)
    monkeypatch.setattr(api.RATE_LIMITER, "allow", lambda key: False)

    response = client.get("/health", headers={"X-Request-Id": "rate-limit-test"})

    assert response.status_code == 429
    assert response.headers["X-Request-Id"] == "rate-limit-test"
    assert response.json()["error"] == "rate_limited"


def test_provider_failure_returns_clean_503(monkeypatch):
    reset_operation_state()
    client = TestClient(app)

    def fail_generation(request):
        raise RuntimeError("provider down")

    monkeypatch.setattr(api, "generate_report_state", fail_generation)

    response = client.post(
        "/v1/reports:generate",
        headers={"X-Request-Id": "provider-failure-test"},
        json={
            "tickers": ["NVDA"],
            "question": "What changed?",
            "reportType": "COMPANY_BRIEF",
            "sourceFilters": ["SEC"],
        },
    )

    assert response.status_code == 503
    assert response.headers["X-Request-Id"] == "provider-failure-test"
    assert response.json()["detail"] == "RAG generation provider failed gracefully."
    assert METRICS.snapshot()["counters"]["rag.provider.errors.total{provider=local_graph}"] == 1


def test_metrics_and_secret_status_endpoints_are_local_only():
    reset_operation_state()
    client = TestClient(app)

    metrics_response = client.get("/metrics")
    secrets_response = client.get("/v1/ops/secrets")

    assert metrics_response.status_code == 200
    assert "counters" in metrics_response.json()
    assert secrets_response.status_code == 200
    assert "OPENAI_API_KEY" in secrets_response.json()["required_names"]
