from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    words = value.split("_")
    return words[0] + "".join(word.capitalize() for word in words[1:])


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ReportType(StrEnum):
    COMPANY_BRIEF = "COMPANY_BRIEF"
    EARNINGS_BRIEF = "EARNINGS_BRIEF"
    FILING_ANALYSIS = "FILING_ANALYSIS"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    COMPARATIVE = "COMPARATIVE"


class SourceFilter(StrEnum):
    SEC = "SEC"
    NEWS = "NEWS"
    EARNINGS = "EARNINGS"

    @classmethod
    def defaults(cls) -> list["SourceFilter"]:
        return [cls.SEC, cls.NEWS, cls.EARNINGS]


class GenerateReportRequest(ContractModel):
    tickers: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    report_type: ReportType
    time_horizon: str = "30d"
    source_filters: list[SourceFilter] = Field(default_factory=SourceFilter.defaults)


class Citation(ContractModel):
    evidence_id: str
    source_type: SourceFilter
    title: str
    url: str


class SourceCoverage(ContractModel):
    sec_chunks: int = 0
    news_chunks: int = 0
    earnings_chunks: int = 0


class Diagnostics(ContractModel):
    mode: str
    rag_service_status: str
    retrieval_status: str
    generation_status: str


class GenerateReportResponse(ContractModel):
    summary: str
    key_findings: list[str]
    citations: list[Citation]
    source_coverage: SourceCoverage
    diagnostics: Diagnostics
