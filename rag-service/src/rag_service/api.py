import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

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

app = FastAPI(title="Financial RAG Service", version="0.1.0")


@app.middleware("http")
async def operations_middleware(request: Request, call_next):
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    trace_id = resolve_request_id(request.headers.get(TRACE_ID_HEADER) or request_id)
    client_key = request.client.host if request.client else "unknown"
    with request_context(request_id, trace_id):
        if not RATE_LIMITER.allow(client_key):
            METRICS.increment("rag.requests.rate_limited.total", path=request.url.path)
            log_event("rag.request.rate_limited", path=request.url.path, client=client_key)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Too many requests.",
                    "requestId": request_id,
                    "timestamp": current_timestamp(),
                },
                headers={REQUEST_ID_HEADER: request_id, TRACE_ID_HEADER: trace_id},
            )

        start = time.perf_counter()
        log_event("rag.request.started", method=request.method, path=request.url.path)
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        METRICS.increment("rag.requests.total", method=request.method, path=request.url.path, status=str(response.status_code))
        METRICS.observe("rag.request.latency_ms", elapsed_ms, path=request.url.path)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        log_event("rag.request.completed", method=request.method, path=request.url.path, statusCode=response.status_code, latencyMs=elapsed_ms)
        return response


@app.post("/v1/reports:generate", response_model=GenerateReportResponse)
def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
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
def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": current_timestamp()}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> dict:
    return METRICS.snapshot()


@app.get("/v1/ops/secrets")
def secret_status() -> dict:
    return secret_policy_status().__dict__
