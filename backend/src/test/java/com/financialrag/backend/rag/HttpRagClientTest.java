package com.financialrag.backend.rag;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class HttpRagClientTest {

    @Test
    void generateReportPostsBackendContractToRagService() {
        RestClient.Builder restClientBuilder = RestClient.builder()
                .baseUrl("http://rag-service.local");
        MockRestServiceServer server = MockRestServiceServer.bindTo(restClientBuilder).build();
        HttpRagClient client = new HttpRagClient(restClientBuilder.build());

        server.expect(once(), requestTo("http://rag-service.local/v1/reports:generate"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(content().json("""
                        {
                          "tickers": ["NVDA"],
                          "question": "What changed in the latest filing?",
                          "reportType": "FILING_ANALYSIS",
                          "timeHorizon": "30d",
                          "sourceFilters": ["SEC", "NEWS"]
                        }
                        """))
                .andRespond(withSuccess("""
                        {
                          "summary": "Mock filing analysis generated for NVDA.",
                          "keyFindings": [
                            "Mock SEC evidence for NVDA.",
                            "Mock NEWS evidence for NVDA."
                          ],
                          "citations": [
                            {
                              "evidenceId": "sec-mock-001",
                              "sourceType": "SEC",
                              "title": "NVDA SEC mock evidence",
                              "url": "https://example.com/sec-mock-001",
                              "section": "Risk Factors",
                              "sourceMetadata": {
                                "cik": "0001045810",
                                "form_type": "10-Q"
                              }
                            }
                          ],
                          "sourceCoverage": {
                            "secChunks": 1,
                            "newsChunks": 1,
                            "earningsChunks": 0
                          },
                          "diagnostics": {
                            "mode": "mock",
                            "ragServiceStatus": "completed",
                            "retrievalStatus": "completed",
                            "generationStatus": "completed"
                          }
                        }
                        """, MediaType.APPLICATION_JSON));

        RagServiceContract.GenerateReportResponse response = client.generateReport(
                new RagServiceContract.GenerateReportRequest(
                        List.of("NVDA"),
                        "What changed in the latest filing?",
                        "FILING_ANALYSIS",
                        "30d",
                        List.of("SEC", "NEWS")));

        assertThat(response.summary()).contains("NVDA");
        assertThat(response.keyFindings()).hasSize(2);
        assertThat(response.citations()).hasSize(1);
        assertThat(response.citations().getFirst().section()).isEqualTo("Risk Factors");
        assertThat(response.citations().getFirst().sourceMetadata())
                .containsAllEntriesOf(Map.of("cik", "0001045810", "form_type", "10-Q"));
        assertThat(response.sourceCoverage().secChunks()).isEqualTo(1);
        assertThat(response.sourceCoverage().newsChunks()).isEqualTo(1);
        assertThat(response.sourceCoverage().earningsChunks()).isZero();
        assertThat(response.diagnostics().ragServiceStatus()).isEqualTo("completed");
        server.verify();
    }
}
