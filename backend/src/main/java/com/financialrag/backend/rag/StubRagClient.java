
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
        return new RagServiceContract.GenerateReportResponse(
                buildSummary(request, tickerList),
                List.of(
                        "Stub SEC evidence placeholder created for " + tickerList + ".",
                        "Stub news evidence placeholder created for " + tickerList + ".",
                        "Stub earnings evidence placeholder created for " + tickerList + "."),
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
            String tickerList) {
        return "Stub " + request.reportType().toLowerCase(Locale.ROOT).replace('_', ' ')
                + " generated for " + tickerList
                + ". Real SEC, news, earnings, retrieval, reranking, and LLM generation are not connected yet.";
    }
}
