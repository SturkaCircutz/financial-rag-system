import asyncio
import json
from dataclasses import dataclass

from rag_service import api
from rag_service.api import app
from rag_service.models import GenerateReportRequest, ReportType, SourceFilter
from rag_service.operations import METRICS, reset_operation_state


@dataclass(frozen=True)
class AsgiResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def header(self, name: str) -> str:
        return self.headers[name.lower()]


def request_app(method: str, path: str, *, headers: dict[str, str] | None = None, json_body=None) -> AsgiResponse:
    body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
    request_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in (headers or {}).items()
    ]
    if json_body is not None:
        request_headers.extend(
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ]
        )

    async def run_request() -> AsgiResponse:
        sent = []
        received_body = False

        async def receive():
            nonlocal received_body
            if not received_body:
                received_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(0)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": request_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        await app(scope, receive, send)

        status_code = next(message["status"] for message in sent if message["type"] == "http.response.start")
        response_headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for message in sent
            if message["type"] == "http.response.start"
            for key, value in message["headers"]
        }
        response_body = b"".join(
            message.get("body", b"") for message in sent if message["type"] == "http.response.body"
        )
        return AsgiResponse(status_code, response_headers, response_body)

    return asyncio.run(run_request())


def test_http_generate_report_adds_trace_headers_and_metrics():
    reset_operation_state()

    response = request_app(
        "POST",
        "/v1/reports:generate",
        headers={"X-Request-Id": "request-test", "X-Trace-Id": "trace-test"},
        json_body={
            "tickers": ["NVDA"],
            "question": "Which filing discusses export controls?",
            "reportType": "FILING_ANALYSIS",
            "sourceFilters": ["SEC"],
        },
    )

    assert response.status_code == 200
    assert response.header("X-Request-Id") == "request-test"
    assert response.header("X-Trace-Id") == "trace-test"
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

    first = api.generate_report_response(request)
    second = api.generate_report_response(request)

    assert first.summary == second.summary
    counters = METRICS.snapshot()["counters"]
    assert counters["rag.cache.miss.total{workflow=generate_report}"] == 1
    assert counters["rag.cache.hit.total{workflow=generate_report}"] == 1


def test_rate_limit_returns_429(monkeypatch):
    reset_operation_state()
    monkeypatch.setattr(api.RATE_LIMITER, "allow", lambda key: False)

    response = request_app("GET", "/health", headers={"X-Request-Id": "rate-limit-test"})

    assert response.status_code == 429
    assert response.header("X-Request-Id") == "rate-limit-test"
    assert response.json()["error"] == "rate_limited"


def test_provider_failure_returns_clean_503(monkeypatch):
    reset_operation_state()

    def fail_generation(request):
        raise RuntimeError("provider down")

    monkeypatch.setattr(api, "generate_report_state", fail_generation)

    response = request_app(
        "POST",
        "/v1/reports:generate",
        headers={"X-Request-Id": "provider-failure-test"},
        json_body={
            "tickers": ["NVDA"],
            "question": "What changed?",
            "reportType": "COMPANY_BRIEF",
            "sourceFilters": ["SEC"],
        },
    )

    assert response.status_code == 503
    assert response.header("X-Request-Id") == "provider-failure-test"
    assert response.json()["detail"] == "RAG generation provider failed gracefully."
    assert METRICS.snapshot()["counters"]["rag.provider.errors.total{provider=local_graph}"] == 1


def test_metrics_and_secret_status_endpoints_are_local_only():
    reset_operation_state()

    metrics_response = request_app("GET", "/metrics")
    secrets_response = request_app("GET", "/v1/ops/secrets")

    assert metrics_response.status_code == 200
    assert "counters" in metrics_response.json()
    assert secrets_response.status_code == 200
    assert "OPENAI_API_KEY" in secrets_response.json()["required_names"]
