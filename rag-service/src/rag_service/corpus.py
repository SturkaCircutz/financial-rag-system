from dataclasses import dataclass

from rag_service.models import SourceFilter


@dataclass(frozen=True)
class EvidenceDocument:
    evidence_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    text: str


LOCAL_CORPUS = (
    EvidenceDocument(
        evidence_id="nvda-sec-risk-001",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA sample filing risk factors",
        url="https://example.com/nvda-sec-risk-001",
        text=(
            "Sample SEC evidence says NVDA risk factors include export controls, "
            "supply constraints, customer concentration, and fast changes in AI accelerator demand."
        ),
    ),
    EvidenceDocument(
        evidence_id="nvda-sec-inventory-002",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA sample filing inventory discussion",
        url="https://example.com/nvda-sec-inventory-002",
        text=(
            "Sample SEC evidence says NVDA discusses inventory purchase obligations, "
            "supplier capacity, and demand planning for new data center products."
        ),
    ),
    EvidenceDocument(
        evidence_id="nvda-news-export-001",
        ticker="NVDA",
        source_type=SourceFilter.NEWS,
        title="NVDA sample news export-control update",
        url="https://example.com/nvda-news-export-001",
        text=(
            "Sample news evidence says investors are watching export-control changes, "
            "China demand, and the pace of data center GPU shipments."
        ),
    ),
    EvidenceDocument(
        evidence_id="nvda-news-product-002",
        ticker="NVDA",
        source_type=SourceFilter.NEWS,
        title="NVDA sample news product-cycle update",
        url="https://example.com/nvda-news-product-002",
        text=(
            "Sample news evidence says the market focus is on Blackwell product timing, "
            "cloud customer demand, and competitive AI accelerator supply."
        ),
    ),
    EvidenceDocument(
        evidence_id="nvda-earnings-datacenter-001",
        ticker="NVDA",
        source_type=SourceFilter.EARNINGS,
        title="NVDA sample earnings data center commentary",
        url="https://example.com/nvda-earnings-datacenter-001",
        text=(
            "Sample earnings evidence says data center revenue, gross margin, "
            "and supply availability are the main signals to compare against expectations."
        ),
    ),
    EvidenceDocument(
        evidence_id="msft-sec-cloud-001",
        ticker="MSFT",
        source_type=SourceFilter.SEC,
        title="MSFT sample filing cloud risk discussion",
        url="https://example.com/msft-sec-cloud-001",
        text=(
            "Sample SEC evidence says MSFT highlights cloud infrastructure investment, "
            "AI product demand, cybersecurity risk, and regulatory uncertainty."
        ),
    ),
    EvidenceDocument(
        evidence_id="msft-news-ai-001",
        ticker="MSFT",
        source_type=SourceFilter.NEWS,
        title="MSFT sample news AI demand update",
        url="https://example.com/msft-news-ai-001",
        text=(
            "Sample news evidence says MSFT investor attention is on Azure growth, "
            "AI monetization, cloud capacity, and enterprise software demand."
        ),
    ),
    EvidenceDocument(
        evidence_id="msft-earnings-azure-001",
        ticker="MSFT",
        source_type=SourceFilter.EARNINGS,
        title="MSFT sample earnings Azure commentary",
        url="https://example.com/msft-earnings-azure-001",
        text=(
            "Sample earnings evidence says Azure growth, AI infrastructure spend, "
            "operating margin, and commercial bookings are core earnings signals."
        ),
    ),
    EvidenceDocument(
        evidence_id="generic-sec-risk-001",
        ticker="*",
        source_type=SourceFilter.SEC,
        title="Generic sample filing risk evidence",
        url="https://example.com/generic-sec-risk-001",
        text=(
            "Sample SEC evidence says filings should be checked for risk factors, "
            "liquidity, segment performance, legal issues, and material changes."
        ),
    ),
    EvidenceDocument(
        evidence_id="generic-news-market-001",
        ticker="*",
        source_type=SourceFilter.NEWS,
        title="Generic sample market news evidence",
        url="https://example.com/generic-news-market-001",
        text=(
            "Sample news evidence says recent market moves should be compared with "
            "company-specific catalysts, sector trends, and macro rate expectations."
        ),
    ),
    EvidenceDocument(
        evidence_id="generic-earnings-signals-001",
        ticker="*",
        source_type=SourceFilter.EARNINGS,
        title="Generic sample earnings evidence",
        url="https://example.com/generic-earnings-signals-001",
        text=(
            "Sample earnings evidence says revenue growth, guidance, margins, cash flow, "
            "and management tone are useful signals for a report."
        ),
    ),
)


def documents_for(source_type: SourceFilter, tickers: list[str]) -> list[EvidenceDocument]:
    ticker_set = {ticker.upper() for ticker in tickers}
    return [
        document
        for document in LOCAL_CORPUS
        if document.source_type == source_type and (document.ticker in ticker_set or document.ticker == "*")
    ]
