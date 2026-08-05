package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import com.financialrag.backend.rag.RagClient;
import com.financialrag.backend.rag.RagServiceContract;
import org.junit.jupiter.api.Test;

class ReportJobProcessorTest {

    @Test
    void processStoresCompletedReportWhenRagClientSucceeds() {
        ReportRepository reportRepository = new InMemoryReportRepository();
        ReportResponse queuedReport = queuedReport(List.of(SourceFilter.SEC, SourceFilter.NEWS));
        reportRepository.save(queuedReport);
        AtomicReference<RagServiceContract.GenerateReportRequest> capturedRequest = new AtomicReference<>();
        RagClient ragClient = request -> {
            capturedRequest.set(request);
            return new RagServiceContract.GenerateReportResponse(
                    "Generated report summary.",
                    List.of("SEC finding.", "News finding."),
                    List.of(new RagServiceContract.Citation(
                            "sec-001",
                            "SEC",
                            "SEC evidence",
                            "https://example.com/sec-001")),
                    new RagServiceContract.SourceCoverage(1, 1, 0),
                    new RagServiceContract.Diagnostics("mock", "completed", "completed", "completed"));
        };
        ReportJobProcessor reportJobProcessor = new ReportJobProcessor(reportRepository, ragClient);

        reportJobProcessor.process(new ReportJob(queuedReport.reportId()));

        ReportResponse storedReport = reportRepository.findById(queuedReport.reportId()).orElseThrow();
        assertThat(capturedRequest.get().tickers()).containsExactly("NVDA");
        assertThat(capturedRequest.get().reportType()).isEqualTo("FILING_ANALYSIS");
        assertThat(capturedRequest.get().sourceFilters()).containsExactly("SEC", "NEWS");
        assertThat(storedReport.status()).isEqualTo(ReportStatus.COMPLETED);
        assertThat(storedReport.summary()).isEqualTo("Generated report summary.");
        assertThat(storedReport.keyFindings()).containsExactly("SEC finding.", "News finding.");
        assertThat(storedReport.citations()).hasSize(1);
        assertThat(storedReport.sourceCoverage().secChunks()).isEqualTo(1);
        assertThat(storedReport.sourceCoverage().newsChunks()).isEqualTo(1);
        assertThat(storedReport.sourceCoverage().earningsChunks()).isZero();
        assertThat(storedReport.diagnostics().ragServiceStatus()).isEqualTo("completed");
    }

    @Test
    void processStoresFailedReportWhenRagClientFails() {
        ReportRepository reportRepository = new InMemoryReportRepository();
        ReportResponse queuedReport = queuedReport(SourceFilter.defaultFilters());
        reportRepository.save(queuedReport);
        RagClient failingRagClient = request -> {
            throw new IllegalStateException("RAG service unavailable");
        };
        ReportJobProcessor reportJobProcessor = new ReportJobProcessor(reportRepository, failingRagClient);

        reportJobProcessor.process(new ReportJob(queuedReport.reportId()));

        ReportResponse storedReport = reportRepository.findById(queuedReport.reportId()).orElseThrow();
        assertThat(storedReport.status()).isEqualTo(ReportStatus.FAILED);
        assertThat(storedReport.summary()).contains("failed");
        assertThat(storedReport.diagnostics().generationStatus()).isEqualTo("failed");
    }

    private static ReportResponse queuedReport(List<SourceFilter> sourceFilters) {
        return new ReportResponse(
                "report-test",
                ReportStatus.QUEUED,
                List.of("NVDA"),
                ReportType.FILING_ANALYSIS,
                "What changed in the latest filing?",
                "30d",
                sourceFilters,
                "",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", "queued", "not_started", "not_started"),
                Instant.parse("2026-08-05T00:00:00Z"));
    }
}
