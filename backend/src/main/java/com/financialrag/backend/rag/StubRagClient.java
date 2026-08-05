
//behavior schema
package com.financialrag.backend.rag;

import java.util.List;
import java.util.Locale;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "rag.service", name = "mode", havingValue = "stub", matchIfMissing = true)
public class StubRagClient implements RagClient {

    private final RagServiceProperties properties;

    public StubRagClient(RagServiceProperties properties) {
        this.properties = properties;
    }

    @Override
    public RagServiceContract.GenerateReportResponse generateReport(
            RagServiceContract.GenerateReportRequest request) {
        String tickerList = String.join(", ", request.tickers());
        List<String> sourceFilters = normalizeSourceFilters(request.sourceFilters());
        return new RagServiceContract.GenerateReportResponse(
                buildSummary(request, tickerList, sourceFilters),
                buildKeyFindings(tickerList, sourceFilters),
                List.of(),
                new RagServiceContract.SourceCoverage(0, 0, 0),
                new RagServiceContract.Diagnostics(
                        properties.getMode(),
                        "stub_client",
                        "not_started",
                        "not_started"));
    }

    private static String buildSummary(
            RagServiceContract.GenerateReportRequest request,
            String tickerList,
            List<String> sourceFilters) {
        return "Stub " + request.reportType().toLowerCase(Locale.ROOT).replace('_', ' ')
                + " generated for " + tickerList
                + " using source filters " + String.join(", ", sourceFilters)
                + ". Real SEC, news, earnings, retrieval, reranking, and LLM generation are not connected yet.";
    }

    private static List<String> buildKeyFindings(String tickerList, List<String> sourceFilters) {
        return sourceFilters.stream()
                .map(sourceFilter -> "Stub " + sourceLabel(sourceFilter)
                        + " evidence placeholder created for " + tickerList + ".")
                .toList();
    }

    private static List<String> normalizeSourceFilters(List<String> sourceFilters) {
        if (sourceFilters == null || sourceFilters.isEmpty()) {
            return List.of("SEC", "NEWS", "EARNINGS");
        }

        List<String> normalizedSourceFilters = sourceFilters.stream()
                .filter(sourceFilter -> sourceFilter != null && !sourceFilter.isBlank())
                .map(sourceFilter -> sourceFilter.trim().toUpperCase(Locale.ROOT))
                .distinct()
                .toList();
        if (normalizedSourceFilters.isEmpty()) {
            return List.of("SEC", "NEWS", "EARNINGS");
        }
        return normalizedSourceFilters;
    }

    private static String sourceLabel(String sourceFilter) {
        return switch (sourceFilter) {
            case "SEC" -> "SEC";
            case "NEWS" -> "news";
            case "EARNINGS" -> "earnings";
            default -> sourceFilter.toLowerCase(Locale.ROOT);
        };
    }
}
