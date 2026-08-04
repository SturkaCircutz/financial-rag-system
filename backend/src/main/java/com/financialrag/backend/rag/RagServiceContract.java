//schema for the data passed in/out
package com.financialrag.backend.rag;

import java.util.List;

public final class RagServiceContract {

    private RagServiceContract() {
    }

    public record GenerateReportRequest(
            List<String> tickers,
            String question,
            String reportType,
            String timeHorizon) {
    }

    public record GenerateReportResponse(
            String summary,
            List<String> keyFindings,
            List<Citation> citations,
            SourceCoverage sourceCoverage,
            Diagnostics diagnostics) {
    }

    public record Citation(
            String evidenceId,
            String sourceType,
            String title,
            String url) {
    }

    public record SourceCoverage(
            int secChunks,
            int newsChunks,
            int earningsChunks) {
    }

    public record Diagnostics(
            String mode,
            String ragServiceStatus,
            String retrievalStatus,
            String generationStatus) {
    }
}
