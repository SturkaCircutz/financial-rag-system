from datetime import datetime, timedelta, timezone

from rag_service.models import SourceFilter
from rag_service.operations import (
    FixedWindowRateLimiter,
    MetricsRegistry,
    TtlCache,
    clear_and_rebuild_local_index,
    enum_safe,
    purge_expired_processed_files,
    request_context,
    resolve_request_id,
    secret_policy_status,
)


def test_request_context_and_request_id_resolution_are_traceable():
    generated = resolve_request_id(None)

    assert generated

    with request_context("request-123", "trace-abc"):
        from rag_service.operations import current_request_id, current_trace_id

        assert current_request_id() == "request-123"
        assert current_trace_id() == "trace-abc"


def test_metrics_registry_records_counters_and_latency_summaries():
    registry = MetricsRegistry()

    registry.increment("rag.requests.total", path="/v1/reports:generate", status="200")
    registry.observe("rag.request.latency_ms", 10, path="/v1/reports:generate")
    registry.observe("rag.request.latency_ms", 30, path="/v1/reports:generate")

    snapshot = registry.snapshot()

    assert snapshot["counters"]["rag.requests.total{path=/v1/reports:generate,status=200}"] == 1
    assert snapshot["observations"]["rag.request.latency_ms{path=/v1/reports:generate}"]["count"] == 2
    assert snapshot["observations"]["rag.request.latency_ms{path=/v1/reports:generate}"]["max"] == 30


def test_ttl_cache_expires_entries(monkeypatch):
    cache = TtlCache(ttl_seconds=10, max_entries=2)
    times = iter([100.0, 101.0, 111.0])
    monkeypatch.setattr("rag_service.operations.time.time", lambda: next(times))

    cache.set("key", "value")

    assert cache.get("key") == "value"
    assert cache.get("key") is None


def test_fixed_window_rate_limiter_blocks_after_limit():
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("client") is True
    assert limiter.allow("client") is True
    assert limiter.allow("client") is False


def test_retention_purges_only_expired_processed_files(tmp_path):
    old_file = tmp_path / "old.json"
    fresh_file = tmp_path / "fresh.json"
    old_file.write_text("old", encoding="utf-8")
    fresh_file.write_text("fresh", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    fresh_time = datetime.now(timezone.utc).timestamp()
    old_file.touch()
    fresh_file.touch()
    import os

    os.utime(old_file, (old_time, old_time))
    os.utime(fresh_file, (fresh_time, fresh_time))

    result = purge_expired_processed_files(tmp_path, retention_days=3)

    assert str(old_file) in result.deleted_paths
    assert fresh_file.exists()


def test_clear_and_rebuild_local_index_is_repeatable_for_local_sources(tmp_path):
    first = clear_and_rebuild_local_index(["NVDA"], source_types=[SourceFilter.SEC], root=tmp_path)
    second = clear_and_rebuild_local_index(["NVDA"], source_types=[SourceFilter.SEC], root=tmp_path)

    assert first.chunk_count == second.chunk_count
    assert first.chunk_count >= 1
    assert (tmp_path / "manifests" / "ingestion_manifest.json").exists()


def test_secret_policy_status_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")

    status = secret_policy_status()

    assert status.configured_names == ("OPENAI_API_KEY",)
    assert "secret-value" not in str(enum_safe(status))
