package com.financialrag.backend.rag;

import java.util.List;

import com.financialrag.backend.report.Citation;
import com.financialrag.backend.report.ReportDiagnostics;
import com.financialrag.backend.report.ReportType;
import com.financialrag.backend.report.SourceCoverage;

public interface RagClient {

    RagReportDraft generateReport(RagReportQuery query);

    record RagReportQuery(
            List<String> tickers,
            String question,
            ReportType reportType,
            String timeHorizon) {
    }

    record RagReportDraft(
            String summary,
            List<String> keyFindings,
            List<Citation> citations,
            SourceCoverage sourceCoverage,
            ReportDiagnostics diagnostics) {
    }
}
