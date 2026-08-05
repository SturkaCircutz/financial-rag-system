package com.financialrag.backend.report;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;

import org.springframework.stereotype.Service;

@Service
public class ReportService {

    private final ReportRepository reportRepository;
    private final ReportJobQueue reportJobQueue;

    public ReportService(ReportRepository reportRepository, ReportJobQueue reportJobQueue) {
        this.reportRepository = reportRepository;
        this.reportJobQueue = reportJobQueue;
    }

    public ReportResponse createReport(ReportRequest request) {
        List<String> tickers = normalizeTickers(request.tickers());
        String timeHorizon = normalizeTimeHorizon(request.timeHorizon());
        List<SourceFilter> sourceFilters = normalizeSourceFilters(request.sourceFilters());
        String question = request.question().trim();
        String reportId = buildReportId();
        Instant createdAt = Instant.now();
        ReportResponse queuedResponse = pendingResponse(
                reportId,
                ReportStatus.QUEUED,
                tickers,
                request.reportType(),
                question,
                timeHorizon,
                sourceFilters,
                createdAt);

        reportRepository.save(queuedResponse);
        reportJobQueue.enqueue(new ReportJob(reportId));
        return queuedResponse;
    }

    public ReportResponse getReport(String reportId) {
        return reportRepository.findById(reportId)
                .orElseThrow(() -> new ReportNotFoundException(reportId));
    }

    private static List<String> normalizeTickers(List<String> tickers) {
        return tickers.stream()
                .map(ticker -> ticker.trim().toUpperCase(Locale.ROOT))
                .filter(ticker -> !ticker.isBlank())
                .distinct()
                .toList();
    }

    private static List<SourceFilter> normalizeSourceFilters(List<SourceFilter> sourceFilters) {
        if (sourceFilters == null || sourceFilters.isEmpty()) {
            return SourceFilter.defaultFilters();
        }

        List<SourceFilter> normalizedSourceFilters = sourceFilters.stream()
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        if (normalizedSourceFilters.isEmpty()) {
            return SourceFilter.defaultFilters();
        }
        return normalizedSourceFilters;
    }

    private static ReportResponse pendingResponse(
            String reportId,
            ReportStatus status,
            List<String> tickers,
            ReportType reportType,
            String question,
            String timeHorizon,
            List<SourceFilter> sourceFilters,
            Instant createdAt) {
        return new ReportResponse(
                reportId,
                status,
                tickers,
                reportType,
                question,
                timeHorizon,
                sourceFilters,
                "",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", status.name().toLowerCase(Locale.ROOT), "not_started", "not_started"),
                createdAt);
    }

    private static String normalizeTimeHorizon(String timeHorizon) {
        if (timeHorizon == null || timeHorizon.isBlank()) {
            return "30d";
        }
        return timeHorizon.trim();
    }

    private static String buildReportId() {
        return "report-" + UUID.randomUUID();
    }
}
