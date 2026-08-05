package com.financialrag.backend.report;

import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.Executor;

import com.financialrag.backend.rag.RagClient;
import com.financialrag.backend.rag.RagServiceContract;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

@Service
public class ReportService {

    private final ConcurrentMap<String, ReportResponse> reports = new ConcurrentHashMap<>();
    private final RagClient ragClient;
    private final Executor reportExecutor;

    public ReportService(RagClient ragClient, @Qualifier("reportExecutor") Executor reportExecutor) {
        this.ragClient = ragClient;
        this.reportExecutor = reportExecutor;
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

        reports.put(reportId, queuedResponse);
        reportExecutor.execute(
                () -> generateReport(
                        reportId,
                        tickers,
                        request.reportType(),
                        question,
                        timeHorizon,
                        sourceFilters,
                        createdAt));
        return queuedResponse;
    }

    public ReportResponse getReport(String reportId) {
        ReportResponse response = reports.get(reportId);
        if (response == null) {
            throw new ReportNotFoundException(reportId);
        }
        return response;
    }

    private void generateReport(
            String reportId,
            List<String> tickers,
            ReportType reportType,
            String question,
            String timeHorizon,
            List<SourceFilter> sourceFilters,
            Instant createdAt) {
        reports.put(
                reportId,
                pendingResponse(
                        reportId,
                        ReportStatus.RUNNING,
                        tickers,
                        reportType,
                        question,
                        timeHorizon,
                        sourceFilters,
                        createdAt));

        try {
            RagServiceContract.GenerateReportResponse ragResponse = ragClient.generateReport(
                    new RagServiceContract.GenerateReportRequest(
                            tickers,
                            question,
                            reportType.name(),
                            timeHorizon,
                            mapSourceFilters(sourceFilters)));

            reports.put(
                    reportId,
                    completedResponse(
                            reportId,
                            tickers,
                            reportType,
                            question,
                            timeHorizon,
                            sourceFilters,
                            createdAt,
                            ragResponse));
        } catch (RuntimeException exception) {
            reports.put(
                    reportId,
                    failedResponse(reportId, tickers, reportType, question, timeHorizon, sourceFilters, createdAt));
        }
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

    private static List<String> mapSourceFilters(List<SourceFilter> sourceFilters) {
        return sourceFilters.stream()
                .map(SourceFilter::name)
                .toList();
    }

    private static List<Citation> mapCitations(List<RagServiceContract.Citation> citations) {
        return citations.stream()
                .map(citation -> new Citation(
                        citation.evidenceId(),
                        citation.sourceType(),
                        citation.title(),
                        citation.url()))
                .toList();
    }

    private static SourceCoverage mapSourceCoverage(RagServiceContract.SourceCoverage sourceCoverage) {
        return new SourceCoverage(
                sourceCoverage.secChunks(),
                sourceCoverage.newsChunks(),
                sourceCoverage.earningsChunks());
    }

    private static ReportDiagnostics mapDiagnostics(RagServiceContract.Diagnostics diagnostics) {
        return new ReportDiagnostics(
                diagnostics.mode(),
                diagnostics.ragServiceStatus(),
                diagnostics.retrievalStatus(),
                diagnostics.generationStatus());
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

    private static ReportResponse completedResponse(
            String reportId,
            List<String> tickers,
            ReportType reportType,
            String question,
            String timeHorizon,
            List<SourceFilter> sourceFilters,
            Instant createdAt,
            RagServiceContract.GenerateReportResponse ragResponse) {
        return new ReportResponse(
                reportId,
                ReportStatus.COMPLETED,
                tickers,
                reportType,
                question,
                timeHorizon,
                sourceFilters,
                ragResponse.summary(),
                ragResponse.keyFindings(),
                mapCitations(ragResponse.citations()),
                mapSourceCoverage(ragResponse.sourceCoverage()),
                mapDiagnostics(ragResponse.diagnostics()),
                createdAt);
    }

    private static ReportResponse failedResponse(
            String reportId,
            List<String> tickers,
            ReportType reportType,
            String question,
            String timeHorizon,
            List<SourceFilter> sourceFilters,
            Instant createdAt) {
        return new ReportResponse(
                reportId,
                ReportStatus.FAILED,
                tickers,
                reportType,
                question,
                timeHorizon,
                sourceFilters,
                "Report generation failed before completion.",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", "failed", "not_started", "failed"),
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
