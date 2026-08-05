package com.financialrag.backend.rag;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

class StubRagClientTest {

    @Test
    void generateReportReturnsContractShapedStubResult() {
        StubRagClient client = new StubRagClient(new RagServiceProperties());

        RagServiceContract.GenerateReportResponse response = client.generateReport(
                new RagServiceContract.GenerateReportRequest(
                        List.of("NVDA"),
                        "What changed in the latest filing?",
                        "FILING_ANALYSIS",
                        "30d",
                        List.of("SEC", "NEWS", "EARNINGS")));

        assertThat(response.summary()).contains("filing analysis").contains("NVDA").contains("SEC");
        assertThat(response.keyFindings()).hasSize(3);
        assertThat(response.citations()).isEmpty();
        assertThat(response.sourceCoverage().secChunks()).isZero();
        assertThat(response.sourceCoverage().newsChunks()).isZero();
        assertThat(response.sourceCoverage().earningsChunks()).isZero();
        assertThat(response.diagnostics().mode()).isEqualTo("stub");
        assertThat(response.diagnostics().ragServiceStatus()).isEqualTo("stub_client");
    }

    @Test
    void generateReportUsesRequestedSourceFilters() {
        StubRagClient client = new StubRagClient(new RagServiceProperties());

        RagServiceContract.GenerateReportResponse response = client.generateReport(
                new RagServiceContract.GenerateReportRequest(
                        List.of("NVDA"),
                        "What changed in the latest filing?",
                        "FILING_ANALYSIS",
                        "30d",
                        List.of("SEC")));

        assertThat(response.summary()).contains("source filters SEC");
        assertThat(response.keyFindings()).containsExactly(
                "Stub SEC evidence placeholder created for NVDA.");
    }
}
