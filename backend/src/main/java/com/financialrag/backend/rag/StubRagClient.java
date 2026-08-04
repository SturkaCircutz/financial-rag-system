package com.financialrag.backend.rag;

import java.util.List;
import java.util.Locale;

import com.financialrag.backend.report.ReportDiagnostics;
import com.financialrag.backend.report.SourceCoverage;
import org.springframework.stereotype.Component;

@Component
public class StubRagClient implements RagClient {

    @Override
    public RagReportDraft generateReport(RagReportQuery query) {
        String tickerList = String.join(", ", query.tickers());
        return new RagReportDraft(
                buildSummary(query, tickerList),
                List.of(
                        "Stub SEC evidence placeholder created for " + tickerList + ".",
                        "Stub news evidence placeholder created for " + tickerList + ".",
                        "Stub earnings evidence placeholder created for " + tickerList + "."),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("stub", "stub_client", "not_started", "not_started"));
    }

    private static String buildSummary(RagReportQuery query, String tickerList) {
        return "Stub " + query.reportType().name().toLowerCase(Locale.ROOT).replace('_', ' ')
                + " generated for " + tickerList
                + ". Real SEC, news, earnings, retrieval, reranking, and LLM generation are not connected yet.";
    }
}
