package com.financialrag.backend.report;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

import org.slf4j.MDC;
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
        reportJobQueue.enqueue(new ReportJob(reportId, currentRequestId()));
        return queuedResponse;
    }

    public ReportResponse getReport(String reportId) {
        return reportRepository.findById(reportId)
                .orElseThrow(() -> new ReportNotFoundException(reportId));
    }

    public ReportHistoryResponse listReports(String ticker, Instant createdAfter, Instant createdBefore) {
        List<ReportResponse> reports = reportRepository.findAll().stream()
                .filter(report -> matchesTicker(report, ticker))
                .filter(report -> matchesCreatedAfter(report, createdAfter))
                .filter(report -> matchesCreatedBefore(report, createdBefore))
                .toList();

        return new ReportHistoryResponse(reports, reports.size());
    }

    public CitationDetail getCitationDetail(String reportId, String evidenceId) {
        ReportResponse report = getReport(reportId);
        Citation citation = report.citations().stream()
                .filter(candidate -> candidate.evidenceId().equals(evidenceId))
                .findFirst()
                .orElseThrow(() -> new CitationNotFoundException(reportId, evidenceId));

        Map<String, String> metadata = citation.sourceMetadata() == null ? Map.of() : citation.sourceMetadata();
        return new CitationDetail(
                report.reportId(),
                citation.evidenceId(),
                citation.sourceType(),
                citation.title(),
                citation.url(),
                citation.section(),
                firstPresent(metadata, "published_at", "filing_date", "call_date", "created_at"),
                firstPresent(metadata, "source_chunk", "chunk_text", "text", "excerpt"),
                metadata);
    }

    private static boolean matchesTicker(ReportResponse report, String ticker) {
        if (ticker == null || ticker.isBlank()) {
            return true;
        }
        String normalizedTicker = ticker.trim().toUpperCase(Locale.ROOT);
        return report.tickers().contains(normalizedTicker);
    }

    private static boolean matchesCreatedAfter(ReportResponse report, Instant createdAfter) {
        return createdAfter == null || !report.createdAt().isBefore(createdAfter);
    }

    private static boolean matchesCreatedBefore(ReportResponse report, Instant createdBefore) {
        return createdBefore == null || !report.createdAt().isAfter(createdBefore);
    }

    private static String firstPresent(Map<String, String> metadata, String... keys) {
        for (String key : keys) {
            String value = metadata.get(key);
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
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

    private static String currentRequestId() {
        String requestId = MDC.get("requestId");
        if (requestId == null || requestId.isBlank()) {
            return "unknown";
        }
        return requestId;
    }
}
