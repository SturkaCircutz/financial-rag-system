from rag_service.models import SourceFilter
from rag_service.news_ingestion import NEWS_DATA_ROOT, LocalNewsIngestor, load_local_news_articles


def test_load_local_news_articles_reads_manifest():
    articles = load_local_news_articles(NEWS_DATA_ROOT / "manifest.json")

    assert {article.ticker for article in articles} == {"NVDA", "MSFT"}
    assert {article.article_type for article in articles} == {"breaking news", "analysis"}
    assert "NVDA/export-control-update.txt" in {article.file_path for article in articles}


def test_local_news_ingestor_deduplicates_syndicated_articles():
    documents = LocalNewsIngestor().ingest(["NVDA"])

    canonical_urls = {document.metadata["canonical_url"] for document in documents}
    assert len(documents) == len(canonical_urls)
    export_document = next(
        document
        for document in documents
        if document.metadata["canonical_url"] == "https://example.com/news/nvda/export-control-update"
    )
    assert export_document.source_type == SourceFilter.NEWS
    assert export_document.metadata["publisher"] == "Local Market Wire"
    assert export_document.metadata["article_type"] == "breaking news"
    assert export_document.metadata["source_reliability"] == "high"
    assert "export-control rule changes" in export_document.text


def test_local_news_ingestor_filters_by_time_window():
    documents = LocalNewsIngestor().ingest(
        ["NVDA"],
        published_after="2026-07-30T00:00:00Z",
        published_before="2026-08-02T00:00:00Z",
    )

    assert {document.metadata["canonical_url"] for document in documents} == {
        "https://example.com/news/nvda/export-control-update"
    }
