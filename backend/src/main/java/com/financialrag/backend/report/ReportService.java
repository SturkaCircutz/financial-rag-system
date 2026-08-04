package com.financialrag.backend.report;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import org.springframework.stereotype.Service;

@Service
public class ReportService {

    private final ConcurrentMap<String, ReportResponse> reports = new ConcurrentHashMap<>();

    public ReportResponse createReport(ReportRequest request) {
        List<String> tickers = normalizeTickers(request.tickers());
        String timeHorizon = normalizeTimeHorizon(request.timeHorizon());
        String reportId = buildReportId(tickers, request.question(), request.reportType(), timeHorizon);

        ReportResponse response = new ReportResponse(
                reportId,
                ReportStatus.COMPLETED,
                tickers,
                request.reportType(),
                request.question().trim(),
                timeHorizon,
                buildSummary(tickers, request.reportType()),
                List.of(
                        "Stub SEC evidence placeholder created for " + String.join(", ", tickers) + ".",
                        "Stub news evidence placeholder created for " + String.join(", ", tickers) + ".",
                        "Stub earnings evidence placeholder created for " + String.join(", ", tickers) + "."),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("stub", "not_connected", "not_started", "not_started"),
                Instant.now());

        reports.put(reportId, response);
        return response;
    }

    public ReportResponse getReport(String reportId) {
        ReportResponse response = reports.get(reportId);
        if (response == null) {
            throw new ReportNotFoundException(reportId);
        }
        return response;
    }

    private static List<String> normalizeTickers(List<String> tickers) {
        return tickers.stream()
                .map(ticker -> ticker.trim().toUpperCase(Locale.ROOT))
                .filter(ticker -> !ticker.isBlank())
                .collect(LinkedHashSet::new, LinkedHashSet::add, LinkedHashSet::addAll)
                .stream()
                .toList();
    }

    private static String normalizeTimeHorizon(String timeHorizon) {
        if (timeHorizon == null || timeHorizon.isBlank()) {
            return "30d";
        }
        return timeHorizon.trim();
    }

    private static String buildSummary(List<String> tickers, ReportType reportType) {
        return "Stub " + reportType.name().toLowerCase(Locale.ROOT).replace('_', ' ')
                + " generated for " + String.join(", ", tickers)
                + ". Real SEC, news, earnings, retrieval, reranking, and LLM generation are not connected yet.";
    }

    private static String buildReportId(
            List<String> tickers,
            String question,
            ReportType reportType,
            String timeHorizon) {
        String seed = String.join(",", tickers) + "|" + question.trim() + "|" + reportType + "|" + timeHorizon;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(seed.getBytes(StandardCharsets.UTF_8));
            return "stub-" + HexFormat.of().formatHex(hash).substring(0, 12);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available", exception);
        }
    }
}
