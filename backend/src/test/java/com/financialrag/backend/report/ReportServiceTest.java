package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;

class ReportServiceTest {

    @Test
    void createReportStoresQueuedStatusAndEnqueuesReportJob() {
        ReportRepository reportRepository = new InMemoryReportRepository();
        RecordingReportJobQueue reportJobQueue = new RecordingReportJobQueue();
        ReportService reportService = new ReportService(reportRepository, reportJobQueue);
        MDC.put("requestId", "request-service-test");

        ReportResponse createdReport;
        try {
            createdReport = reportService.createReport(new ReportRequest(
                    List.of("nvda"),
                    "What changed in the latest filing?",
                    ReportType.FILING_ANALYSIS,
                    "30d",
                    null));
        } finally {
            MDC.remove("requestId");
        }

        ReportResponse storedReport = reportService.getReport(createdReport.reportId());

        assertThat(createdReport.status()).isEqualTo(ReportStatus.QUEUED);
        assertThat(storedReport.status()).isEqualTo(ReportStatus.QUEUED);
        assertThat(storedReport.tickers()).containsExactly("NVDA");
        assertThat(storedReport.sourceFilters()).containsExactly(
                SourceFilter.SEC,
                SourceFilter.NEWS,
                SourceFilter.EARNINGS);
        assertThat(reportJobQueue.jobs()).extracting(ReportJob::reportId).containsExactly(createdReport.reportId());
        assertThat(reportJobQueue.jobs()).extracting(ReportJob::requestId).containsExactly("request-service-test");
    }

    private static final class RecordingReportJobQueue implements ReportJobQueue {

        private final List<ReportJob> jobs = new ArrayList<>();

        @Override
        public void enqueue(ReportJob job) {
            jobs.add(job);
        }

        private List<ReportJob> jobs() {
            return jobs;
        }
    }
}
