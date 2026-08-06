import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders

from rag_service.graph import generate_report_state
from rag_service.models import GenerateReportRequest, GenerateReportResponse
from rag_service.operations import (
    METRICS,
    RATE_LIMITER,
    REPORT_CACHE,
    REQUEST_ID_HEADER,
    SETTINGS,
    TRACE_ID_HEADER,
    cache_key_for_request,
    current_timestamp,
    estimated_tokens,
    log_event,
    request_context,
    resolve_request_id,
    secret_policy_status,
)

class OperationsMiddleware:
    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = resolve_request_id(headers.get(REQUEST_ID_HEADER))
        trace_id = resolve_request_id(headers.get(TRACE_ID_HEADER) or request_id)
        method = scope["method"]
        path = scope["path"]
        client = scope.get("client")
        client_key = client[0] if client else "unknown"

        with request_context(request_id, trace_id):
            if not RATE_LIMITER.allow(client_key):
                METRICS.increment("rag.requests.rate_limited.total", path=path)
                log_event("rag.request.rate_limited", path=path, client=client_key)
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limited",
                        "message": "Too many requests.",
                        "requestId": request_id,
                        "timestamp": current_timestamp(),
                    },
                    headers={REQUEST_ID_HEADER: request_id, TRACE_ID_HEADER: trace_id},
                )
                await response(scope, receive, send)
                return

            start = time.perf_counter()
            status_code = 500
            log_event("rag.request.started", method=method, path=path)

            async def send_with_trace_headers(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    response_headers = MutableHeaders(scope=message)
                    response_headers[REQUEST_ID_HEADER] = request_id
                    response_headers[TRACE_ID_HEADER] = trace_id
                await send(message)

            try:
                await self._app(scope, receive, send_with_trace_headers)
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                METRICS.increment("rag.requests.total", method=method, path=path, status=str(status_code))
                METRICS.observe("rag.request.latency_ms", elapsed_ms, path=path)
                log_event("rag.request.completed", method=method, path=path, statusCode=status_code, latencyMs=elapsed_ms)


app = FastAPI(title="Financial RAG Service", version="0.1.0")
app.add_middleware(OperationsMiddleware)


@app.post("/v1/reports:generate", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
    return generate_report_response(request)


def generate_report_response(request: GenerateReportRequest) -> GenerateReportResponse:
    cache_key = cache_key_for_request(request)
    if SETTINGS.enable_cache:
        cached_response = REPORT_CACHE.get(cache_key)
        if cached_response is not None:
            METRICS.increment("rag.cache.hit.total", workflow="generate_report")
            log_event("rag.cache.hit", workflow="generate_report")
            return cached_response.model_copy(deep=True)

    METRICS.increment("rag.cache.miss.total", workflow="generate_report")
    start = time.perf_counter()
    try:
        final_state = generate_report_state(request)
    except Exception as exc:
        METRICS.increment("rag.provider.errors.total", provider="local_graph")
        log_event("rag.request.failed", workflow="generate_report", errorType=type(exc).__name__)
        raise HTTPException(status_code=503, detail="RAG generation provider failed gracefully.") from exc

    response = final_state["response"]
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    prompt_tokens = estimated_tokens(final_state.get("generation_prompt", ""))
    completion_tokens = estimated_tokens(response.summary + " " + " ".join(response.key_findings))
    METRICS.observe("rag.workflow.latency_ms", elapsed_ms, workflow="generate_report")
    METRICS.increment("rag.tokens.prompt.total", prompt_tokens, workflow="generate_report")
    METRICS.increment("rag.tokens.completion.total", completion_tokens, workflow="generate_report")
    log_event(
        "rag.workflow.completed",
        workflow="generate_report",
        latencyMs=elapsed_ms,
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        trace=final_state.get("trace", []),
    )

    if SETTINGS.enable_cache:
        REPORT_CACHE.set(cache_key, response.model_copy(deep=True))
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": current_timestamp()}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> dict:
    return METRICS.snapshot()


@app.get("/v1/ops/secrets")
async def secret_status() -> dict:
    return secret_policy_status().__dict__
