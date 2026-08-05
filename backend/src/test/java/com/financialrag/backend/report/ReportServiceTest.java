package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import com.financialrag.backend.rag.RagClient;
import org.junit.jupiter.api.Test;

class ReportServiceTest {

    @Test
    void createReportStoresFailedStatusWhenRagClientFails() {
        RagClient failingRagClient = request -> {
            throw new IllegalStateException("RAG service unavailable");
        };
        ReportRepository reportRepository = new InMemoryReportRepository();
        ReportService reportService = new ReportService(failingRagClient, reportRepository, Runnable::run);

        ReportResponse createdReport = reportService.createReport(new ReportRequest(
                List.of("nvda"),
                "What changed in the latest filing?",
                ReportType.FILING_ANALYSIS,
                "30d",
                null));

        ReportResponse storedReport = reportService.getReport(createdReport.reportId());

        assertThat(createdReport.status()).isEqualTo(ReportStatus.QUEUED);
        assertThat(storedReport.status()).isEqualTo(ReportStatus.FAILED);
        assertThat(storedReport.tickers()).containsExactly("NVDA");
        assertThat(storedReport.sourceFilters()).containsExactly(
                SourceFilter.SEC,
                SourceFilter.NEWS,
                SourceFilter.EARNINGS);
        assertThat(storedReport.summary()).contains("failed");
        assertThat(storedReport.diagnostics().generationStatus()).isEqualTo("failed");
    }
}
