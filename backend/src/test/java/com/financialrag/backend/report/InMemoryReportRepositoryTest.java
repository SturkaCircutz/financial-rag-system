package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;

class InMemoryReportRepositoryTest {

    @Test
    void saveStoresReportById() {
        InMemoryReportRepository reportRepository = new InMemoryReportRepository();
        ReportResponse report = new ReportResponse(
                "report-test",
                ReportStatus.QUEUED,
                List.of("NVDA"),
                ReportType.COMPANY_BRIEF,
                "What changed?",
                "30d",
                SourceFilter.defaultFilters(),
                "",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", "queued", "not_started", "not_started"),
                Instant.parse("2026-08-05T00:00:00Z"));

        ReportResponse savedReport = reportRepository.save(report);

        assertThat(savedReport).isSameAs(report);
        assertThat(reportRepository.findById("report-test")).contains(report);
    }

    @Test
    void findByIdReturnsEmptyWhenReportDoesNotExist() {
        InMemoryReportRepository reportRepository = new InMemoryReportRepository();

        assertThat(reportRepository.findById("missing-report")).isEmpty();
    }
}
