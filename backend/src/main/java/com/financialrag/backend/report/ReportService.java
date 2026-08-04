package com.financialrag.backend.report;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import com.financialrag.backend.rag.RagClient;
import com.financialrag.backend.rag.RagClient.RagReportDraft;
import com.financialrag.backend.rag.RagClient.RagReportQuery;
import org.springframework.stereotype.Service;

@Service
public class ReportService {

    private final ConcurrentMap<String, ReportResponse> reports = new ConcurrentHashMap<>();
    private final RagClient ragClient;

    public ReportService(RagClient ragClient) {
        this.ragClient = ragClient;
    }

    public ReportResponse createReport(ReportRequest request) {
        List<String> tickers = normalizeTickers(request.tickers());
        String timeHorizon = normalizeTimeHorizon(request.timeHorizon());
        String reportId = buildReportId(tickers, request.question(), request.reportType(), timeHorizon);
        RagReportDraft reportDraft = ragClient.generateReport(
                new RagReportQuery(tickers, request.question().trim(), request.reportType(), timeHorizon));

        ReportResponse response = new ReportResponse(
                reportId,
                ReportStatus.COMPLETED,
                tickers,
                request.reportType(),
                request.question().trim(),
                timeHorizon,
                reportDraft.summary(),
                reportDraft.keyFindings(),
                reportDraft.citations(),
                reportDraft.sourceCoverage(),
                reportDraft.diagnostics(),
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
                .distinct()
                .toList();
    }

    private static String normalizeTimeHorizon(String timeHorizon) {
        if (timeHorizon == null || timeHorizon.isBlank()) {
            return "30d";
        }
        return timeHorizon.trim();
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
