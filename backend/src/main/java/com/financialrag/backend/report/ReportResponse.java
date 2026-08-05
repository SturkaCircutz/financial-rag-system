package com.financialrag.backend.report;

import java.time.Instant;
import java.util.List;

public record ReportResponse(
        String reportId,
        ReportStatus status,
        List<String> tickers,
        ReportType reportType,
        String question,
        String timeHorizon,
        List<SourceFilter> sourceFilters,
        String summary,
        List<String> keyFindings,
        List<Citation> citations,
        SourceCoverage sourceCoverage,
        ReportDiagnostics diagnostics,
        Instant createdAt) {
}
