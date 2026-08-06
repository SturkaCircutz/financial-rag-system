import json
import logging
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from rag_service.document_store import LOCAL_STORE_ROOT, LocalDocumentStore
from rag_service.models import GenerateReportRequest, SourceFilter
from rag_service.retrieval import tokenize
from rag_service.source_memory import LocalSourceMemory


REQUEST_ID_HEADER = "X-Request-Id"
TRACE_ID_HEADER = "X-Trace-Id"
LOGGER = logging.getLogger("rag_service")

_request_id: ContextVar[str] = ContextVar("request_id", default="unknown")
_trace_id: ContextVar[str] = ContextVar("trace_id", default="unknown")


@dataclass(frozen=True)
class OperationSettings:
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 128
    rate_limit_per_minute: int = 120
    retention_days: int = 30

    @classmethod
    def from_env(cls) -> "OperationSettings":
        return cls(
            enable_cache=env_bool("RAG_OPS_ENABLE_CACHE", True),
            cache_ttl_seconds=env_int("RAG_OPS_CACHE_TTL_SECONDS", 300),
            cache_max_entries=env_int("RAG_OPS_CACHE_MAX_ENTRIES", 128),
            rate_limit_per_minute=env_int("RAG_OPS_RATE_LIMIT_PER_MINUTE", 120),
            retention_days=env_int("RAG_OPS_RETENTION_DAYS", 30),
        )


@dataclass(frozen=True)
class CacheEntry:
    value: Any
    expires_at: float


@dataclass(frozen=True)
class BackfillResult:
    tickers: tuple[str, ...]
    source_types: tuple[SourceFilter, ...]
    chunk_count: int
    manifest_path: str


@dataclass(frozen=True)
class RetentionResult:
    root: str
    retention_days: int
    deleted_paths: list[str]


@dataclass(frozen=True)
class SecretPolicyStatus:
    required_names: tuple[str, ...]
    configured_names: tuple[str, ...]
    missing_names: tuple[str, ...]


class MetricsRegistry:
    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, float] = {}
        self._observations: dict[str, list[float]] = {}

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = metric_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = metric_key(name, labels)
        with self._lock:
            self._observations.setdefault(key, []).append(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(sorted(self._counters.items()))
            observations = {
                key: observation_summary(values)
                for key, values in sorted(self._observations.items())
            }
        return {
            "counters": counters,
            "observations": observations,
            "generatedAt": current_timestamp(),
        }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._observations.clear()


class TtlCache:
    def __init__(self, ttl_seconds: int, max_entries: int):
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._lock = Lock()
        self._entries: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._entries) >= self._max_entries:
                oldest_key = next(iter(self._entries))
                self._entries.pop(oldest_key, None)
            self._entries[key] = CacheEntry(value=value, expires_at=time.time() + self._ttl_seconds)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self._limit = limit
        self._window_seconds = window_seconds
        self._lock = Lock()
        self._windows: dict[str, tuple[int, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            count, window_start = self._windows.get(key, (0, now))
            if now - window_start >= self._window_seconds:
                count = 0
                window_start = now
            if count >= self._limit:
                return False
            self._windows[key] = (count + 1, window_start)
            return True

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


@contextmanager
def request_context(request_id: str, trace_id: str | None = None) -> Iterator[None]:
    request_token = _request_id.set(request_id)
    trace_token = _trace_id.set(trace_id or request_id)
    try:
        yield
    finally:
        _trace_id.reset(trace_token)
        _request_id.reset(request_token)


def current_request_id() -> str:
    return _request_id.get()


def current_trace_id() -> str:
    return _trace_id.get()


def resolve_request_id(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    return str(uuid.uuid4())


def cache_key_for_request(request: GenerateReportRequest) -> str:
    return request.model_dump_json(by_alias=True)


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "requestId": current_request_id(),
        "traceId": current_trace_id(),
        "timestamp": current_timestamp(),
        **enum_safe(fields),
    }
    LOGGER.info(json.dumps(payload, sort_keys=True))


def record_graph_node(node: str, status: str, detail: str) -> None:
    METRICS.increment("rag.graph.node.total", node=node, status=status)
    log_event("rag.graph.node", node=node, status=status, detail=detail)


def reset_operation_state() -> None:
    METRICS.reset()
    REPORT_CACHE.reset()
    RATE_LIMITER.reset()


def rebuild_local_index(
    tickers: list[str],
    source_types: list[SourceFilter] | None = None,
    store: LocalDocumentStore | None = None,
) -> BackfillResult:
    normalized_tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    selected_source_types = source_types or SourceFilter.defaults()
    local_store = store or LocalDocumentStore()
    memory = LocalSourceMemory(store=local_store)
    total_chunks = 0
    manifest_path = local_store.manifest_path

    for source_type in selected_source_types:
        result = memory.collect(source_type, normalized_tickers)
        total_chunks += len(result.chunks)
        if result.store_write:
            manifest_path = result.store_write.manifest_path

    METRICS.increment("rag.index.rebuild.total")
    log_event(
        "rag.index.rebuild",
        tickers=normalized_tickers,
        sourceTypes=[source_type.value for source_type in selected_source_types],
        chunkCount=total_chunks,
        manifestPath=str(manifest_path),
    )
    return BackfillResult(
        tickers=tuple(normalized_tickers),
        source_types=tuple(selected_source_types),
        chunk_count=total_chunks,
        manifest_path=str(manifest_path),
    )


def clear_and_rebuild_local_index(
    tickers: list[str],
    source_types: list[SourceFilter] | None = None,
    root: Path = LOCAL_STORE_ROOT,
) -> BackfillResult:
    if root.exists():
        shutil.rmtree(root)
    return rebuild_local_index(tickers, source_types=source_types, store=LocalDocumentStore(root=root))


def purge_expired_processed_files(
    root: Path = LOCAL_STORE_ROOT,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> RetentionResult:
    retention_days = SETTINGS.retention_days if retention_days is None else retention_days
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    deleted_paths: list[str] = []
    if not root.exists():
        return RetentionResult(str(root), retention_days, deleted_paths)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified_at >= cutoff:
            continue
        path.unlink()
        deleted_paths.append(str(path))

    METRICS.increment("rag.retention.run.total")
    METRICS.increment("rag.retention.deleted_files.total", len(deleted_paths))
    log_event("rag.retention.purge", root=str(root), retentionDays=retention_days, deletedFiles=len(deleted_paths))
    return RetentionResult(str(root), retention_days, deleted_paths)


def secret_policy_status(required_names: tuple[str, ...] = ("OPENAI_API_KEY",)) -> SecretPolicyStatus:
    configured = tuple(name for name in required_names if os.environ.get(name))
    missing = tuple(name for name in required_names if name not in configured)
    return SecretPolicyStatus(required_names, configured, missing)


def observation_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0}
    sorted_values = sorted(values)
    return {
        "count": len(values),
        "min": sorted_values[0],
        "max": sorted_values[-1],
        "p50": percentile(sorted_values, 0.5),
        "p95": percentile(sorted_values, 0.95),
    }


def percentile(sorted_values: list[float], percentile_value: float) -> float:
    index = min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * percentile_value)))
    return round(sorted_values[index], 6)


def metric_key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    labels_text = ",".join(f"{key}={value}" for key, value in sorted(labels.items()))
    return f"{name}{{{labels_text}}}"


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def estimated_tokens(value: str) -> int:
    return len(tokenize(value)) if value else 0


def enum_safe(value: Any) -> Any:
    if isinstance(value, SourceFilter):
        return value.value
    if isinstance(value, dict):
        return {key: enum_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [enum_safe(item) for item in value]
    if isinstance(value, tuple):
        return [enum_safe(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return enum_safe(asdict(value))
    return value


SETTINGS = OperationSettings.from_env()
METRICS = MetricsRegistry()
REPORT_CACHE = TtlCache(SETTINGS.cache_ttl_seconds, SETTINGS.cache_max_entries)
RATE_LIMITER = FixedWindowRateLimiter(SETTINGS.rate_limit_per_minute)
