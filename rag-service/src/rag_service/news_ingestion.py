import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rag_service.models import SourceFilter
from rag_service.paths import data_root
from rag_service.sec_ingestion import slugify


@dataclass(frozen=True)
class LocalNewsArticle:
    article_id: str
    ticker: str
    title: str
    publisher: str
    author: str
    published_at: str
    url: str
    canonical_url: str
    article_type: str
    topics: tuple[str, ...]
    source_reliability: str
    file_path: str


@dataclass(frozen=True)
class IngestedNewsDocument:
    source_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    metadata: dict[str, str]


NEWS_DATA_ROOT = data_root() / "news"


class LocalNewsIngestor:
    def __init__(
        self,
        articles: tuple[LocalNewsArticle, ...] | None = None,
        data_root: Path = NEWS_DATA_ROOT,
        manifest_path: Path | None = None,
    ):
        self._data_root = data_root
        self._articles = articles if articles is not None else load_local_news_articles(manifest_path or data_root / "manifest.json")

    def ingest(
        self,
        tickers: list[str],
        published_after: str | None = None,
        published_before: str | None = None,
    ) -> list[IngestedNewsDocument]:
        ticker_set = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
        after = parse_timestamp(published_after) if published_after else None
        before = parse_timestamp(published_before) if published_before else None
        candidates = [
            article
            for article in self._articles
            if article.ticker in ticker_set and is_in_time_window(article, after, before)
        ]
        return [self._document_for_article(article) for article in deduplicate_articles(candidates, self._read_article_text)]

    def _document_for_article(self, article: LocalNewsArticle) -> IngestedNewsDocument:
        text = self._read_article_text(article)
        return IngestedNewsDocument(
            source_id=f"news-{article.ticker.lower()}-{article.article_id}",
            ticker=article.ticker,
            source_type=SourceFilter.NEWS,
            title=article.title,
            url=article.canonical_url,
            section=article.article_type,
            text=text,
            metadata={
                "publisher": article.publisher,
                "author": article.author,
                "published_at": article.published_at,
                "canonical_url": article.canonical_url,
                "article_type": article.article_type,
                "topics": ",".join(article.topics),
                "source_reliability": article.source_reliability,
                "source_path": article.file_path,
            },
        )

    def _read_article_text(self, article: LocalNewsArticle) -> str:
        path = self._data_root / article.file_path
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Local news article file not found: {path}") from exc


def load_local_news_articles(manifest_path: Path) -> tuple[LocalNewsArticle, ...]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    articles = manifest.get("articles", [])
    return tuple(local_news_article_from_manifest(item) for item in articles)


def local_news_article_from_manifest(item: dict) -> LocalNewsArticle:
    return LocalNewsArticle(
        article_id=item.get("article_id", slugify(item["title"])),
        ticker=item["ticker"].strip().upper(),
        title=item["title"],
        publisher=item["publisher"],
        author=item["author"],
        published_at=item["published_at"],
        url=item["url"],
        canonical_url=item.get("canonical_url", item["url"]),
        article_type=item["article_type"],
        topics=tuple(item.get("topics", [])),
        source_reliability=item["source_reliability"],
        file_path=item["file_path"],
    )


def deduplicate_articles(
    articles: list[LocalNewsArticle],
    read_article_text,
) -> list[LocalNewsArticle]:
    seen: set[str] = set()
    unique_articles: list[LocalNewsArticle] = []
    for article in articles:
        text = read_article_text(article)
        dedupe_key = article.canonical_url or content_hash(text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique_articles.append(article)
    return unique_articles


def is_in_time_window(
    article: LocalNewsArticle,
    after: datetime | None,
    before: datetime | None,
) -> bool:
    published_at = parse_timestamp(article.published_at)
    if after and published_at < after:
        return False
    if before and published_at > before:
        return False
    return True


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
