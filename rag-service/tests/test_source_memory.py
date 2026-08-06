from rag_service.models import SourceFilter
from rag_service.source_memory import LocalSourceMemory


def test_local_source_memory_returns_manifests_pointers_and_chunks():
    source_memory = LocalSourceMemory()

    result = source_memory.collect(SourceFilter.SEC, ["NVDA"])

    assert {manifest.source_id for manifest in result.manifests} >= {
        "nvda-sec-risk-001",
        "generic-sec-risk-001",
    }
    assert result.chunk_pointers
    assert result.chunks
    assert result.chunk_pointers[0].chunk_id == result.chunks[0]["chunk_id"]
    assert result.chunk_pointers[0].source_id == result.chunks[0]["source_id"]
    assert result.chunk_pointers[0].content_hash == result.chunks[0]["content_hash"]
    assert not hasattr(result.chunk_pointers[0], "text")

    sec_pointer = next(pointer for pointer in result.chunk_pointers if pointer.source_id.startswith("sec-nvda-10q"))
    assert sec_pointer.metadata["cik"] == "0001045810"
    assert sec_pointer.metadata["form_type"] == "10-Q"


def test_local_source_memory_keeps_source_filters_separate():
    source_memory = LocalSourceMemory()

    result = source_memory.collect(SourceFilter.NEWS, ["NVDA"])

    assert result.manifests
    assert {manifest.source_type for manifest in result.manifests} == {SourceFilter.NEWS}
    assert {chunk["source_type"] for chunk in result.chunks} == {SourceFilter.NEWS}
