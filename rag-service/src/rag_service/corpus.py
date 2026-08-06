from dataclasses import dataclass, field

from rag_service.documents import Document
from rag_service.earnings_ingestion import IngestedEarningsDocument, LocalEarningsIngestor
from rag_service.models import SourceFilter
from rag_service.news_ingestion import IngestedNewsDocument, LocalNewsIngestor
from rag_service.sec_ingestion import IngestedSecDocument, LocalSecFilingIngestor


@dataclass(frozen=True)
class EvidenceDocument(Document):
    metadata: dict[str, str] = field(default_factory=dict)


SEC_INGESTOR = LocalSecFilingIngestor()
NEWS_INGESTOR = LocalNewsIngestor()
EARNINGS_INGESTOR = LocalEarningsIngestor()


LOCAL_CORPUS = (
    EvidenceDocument(
        source_id="nvda-sec-risk-001",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA sample filing risk factors",
        url="https://example.com/nvda-sec-risk-001",
        section="Risk Factors",
        text=(
            "Sample SEC evidence says NVDA risk factors include export controls, "
            "supply constraints, customer concentration, and fast changes in AI accelerator demand."
        ),
    ),
    EvidenceDocument(
        source_id="nvda-sec-inventory-002",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA sample filing inventory discussion",
        url="https://example.com/nvda-sec-inventory-002",
        section="Management Discussion",
        text=(
            "Sample SEC evidence says NVDA discusses inventory purchase obligations, "
            "supplier capacity, and demand planning for new data center products."
        ),
    ),
    EvidenceDocument(
        source_id="nvda-news-export-001",
        ticker="NVDA",
        source_type=SourceFilter.NEWS,
        title="NVDA sample news export-control update",
        url="https://example.com/nvda-news-export-001",
        section="Market News",
        text=(
            "Sample news evidence says investors are watching export-control changes, "
            "China demand, and the pace of data center GPU shipments."
        ),
    ),
    EvidenceDocument(
        source_id="nvda-news-product-002",
        ticker="NVDA",
        source_type=SourceFilter.NEWS,
        title="NVDA sample news product-cycle update",
        url="https://example.com/nvda-news-product-002",
        section="Product Cycle",
        text=(
            "Sample news evidence says the market focus is on Blackwell product timing, "
            "cloud customer demand, and competitive AI accelerator supply."
        ),
    ),
    EvidenceDocument(
        source_id="nvda-earnings-datacenter-001",
        ticker="NVDA",
        source_type=SourceFilter.EARNINGS,
        title="NVDA sample earnings data center commentary",
        url="https://example.com/nvda-earnings-datacenter-001",
        section="Earnings Call",
        text=(
            "Sample earnings evidence says data center revenue, gross margin, "
            "and supply availability are the main signals to compare against expectations."
        ),
    ),
    EvidenceDocument(
        source_id="msft-sec-cloud-001",
        ticker="MSFT",
        source_type=SourceFilter.SEC,
        title="MSFT sample filing cloud risk discussion",
        url="https://example.com/msft-sec-cloud-001",
        section="Risk Factors",
        text=(
            "Sample SEC evidence says MSFT highlights cloud infrastructure investment, "
            "AI product demand, cybersecurity risk, and regulatory uncertainty."
        ),
    ),
    EvidenceDocument(
        source_id="msft-news-ai-001",
        ticker="MSFT",
        source_type=SourceFilter.NEWS,
        title="MSFT sample news AI demand update",
        url="https://example.com/msft-news-ai-001",
        section="Market News",
        text=(
            "Sample news evidence says MSFT investor attention is on Azure growth, "
            "AI monetization, cloud capacity, and enterprise software demand."
        ),
    ),
    EvidenceDocument(
        source_id="msft-earnings-azure-001",
        ticker="MSFT",
        source_type=SourceFilter.EARNINGS,
        title="MSFT sample earnings Azure commentary",
        url="https://example.com/msft-earnings-azure-001",
        section="Earnings Call",
        text=(
            "Sample earnings evidence says Azure growth, AI infrastructure spend, "
            "operating margin, and commercial bookings are core earnings signals."
        ),
    ),
    EvidenceDocument(
        source_id="generic-sec-risk-001",
        ticker="*",
        source_type=SourceFilter.SEC,
        title="Generic sample filing risk evidence",
        url="https://example.com/generic-sec-risk-001",
        section="Filing Checklist",
        text=(
            "Sample SEC evidence says filings should be checked for risk factors, "
            "liquidity, segment performance, legal issues, and material changes."
        ),
    ),
    EvidenceDocument(
        source_id="generic-news-market-001",
        ticker="*",
        source_type=SourceFilter.NEWS,
        title="Generic sample market news evidence",
        url="https://example.com/generic-news-market-001",
        section="Market Context",
        text=(
            "Sample news evidence says recent market moves should be compared with "
            "company-specific catalysts, sector trends, and macro rate expectations."
        ),
    ),
    EvidenceDocument(
        source_id="generic-earnings-signals-001",
        ticker="*",
        source_type=SourceFilter.EARNINGS,
        title="Generic sample earnings evidence",
        url="https://example.com/generic-earnings-signals-001",
        section="Earnings Checklist",
        text=(
            "Sample earnings evidence says revenue growth, guidance, margins, cash flow, "
            "and management tone are useful signals for a report."
        ),
    ),
)


def documents_for(source_type: SourceFilter, tickers: list[str]) -> list[EvidenceDocument]:
    ticker_set = {ticker.upper() for ticker in tickers}
    documents = [
        document
        for document in LOCAL_CORPUS
        if document.source_type == source_type and (document.ticker in ticker_set or document.ticker == "*")
    ]
    if source_type == SourceFilter.SEC:
        documents.extend(evidence_document_for_sec_filing(document) for document in SEC_INGESTOR.ingest(tickers))
    if source_type == SourceFilter.NEWS:
        documents.extend(evidence_document_for_news_article(document) for document in NEWS_INGESTOR.ingest(tickers))
    if source_type == SourceFilter.EARNINGS:
        documents.extend(
            evidence_document_for_earnings_segment(document)
            for document in EARNINGS_INGESTOR.ingest(tickers, latest_only=True)
        )
    return documents


def evidence_document_for_sec_filing(document: IngestedSecDocument) -> EvidenceDocument:
    return EvidenceDocument(
        source_id=document.source_id,
        ticker=document.ticker,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        section=document.section,
        text=document.text,
        metadata=document.metadata,
        company_name=document.metadata.get("company_name", ""),
        published_at=document.metadata.get("filing_date", ""),
        period=document.metadata.get("report_period", ""),
        provider="local-sec",
    )


def evidence_document_for_news_article(document: IngestedNewsDocument) -> EvidenceDocument:
    return EvidenceDocument(
        source_id=document.source_id,
        ticker=document.ticker,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        section=document.section,
        text=document.text,
        metadata=document.metadata,
        published_at=document.metadata.get("published_at", ""),
        provider=document.metadata.get("publisher", "local-news"),
    )


def evidence_document_for_earnings_segment(document: IngestedEarningsDocument) -> EvidenceDocument:
    return EvidenceDocument(
        source_id=document.source_id,
        ticker=document.ticker,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        section=document.section,
        text=document.text,
        metadata=document.metadata,
        published_at=document.metadata.get("call_date", ""),
        period=" ".join(
            value
            for value in (
                document.metadata.get("fiscal_year", ""),
                document.metadata.get("fiscal_quarter", ""),
            )
            if value
        ),
        provider="local-earnings",
    )
