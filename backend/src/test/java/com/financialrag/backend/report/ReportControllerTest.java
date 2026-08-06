package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ReportControllerTest {

    private static final String REQUEST_ID_HEADER = "X-Request-Id";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReportRepository reportRepository;

    @Test
    void createReportReturnsQueuedReport() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "tickers": ["nvda"],
                                  "question": "What are the latest risk factors?",
                                  "reportType": "COMPANY_BRIEF",
                                  "timeHorizon": "30d",
                                  "sourceFilters": ["SEC", "NEWS"]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().exists(REQUEST_ID_HEADER))
                .andExpect(jsonPath("$.reportId", notNullValue()))
                .andExpect(jsonPath("$.status", equalTo("QUEUED")))
                .andExpect(jsonPath("$.tickers[0]", equalTo("NVDA")))
                .andExpect(jsonPath("$.reportType", equalTo("COMPANY_BRIEF")))
                .andExpect(jsonPath("$.question", equalTo("What are the latest risk factors?")))
                .andExpect(jsonPath("$.timeHorizon", equalTo("30d")))
                .andExpect(jsonPath("$.sourceFilters[0]", equalTo("SEC")))
                .andExpect(jsonPath("$.sourceFilters[1]", equalTo("NEWS")))
                .andExpect(jsonPath("$.summary", equalTo("")))
                .andExpect(jsonPath("$.keyFindings", hasSize(0)))
                .andExpect(jsonPath("$.citations", hasSize(0)))
                .andExpect(jsonPath("$.sourceCoverage.secChunks", equalTo(0)))
                .andExpect(jsonPath("$.sourceCoverage.newsChunks", equalTo(0)))
                .andExpect(jsonPath("$.sourceCoverage.earningsChunks", equalTo(0)))
                .andExpect(jsonPath("$.diagnostics.mode", equalTo("pending")))
                .andExpect(jsonPath("$.diagnostics.ragServiceStatus", equalTo("queued")))
                .andExpect(jsonPath("$.createdAt", notNullValue()));
    }

    @Test
    void getReportReturnsStoredStubReport() throws Exception {
        String responseBody = mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "tickers": ["msft", "aapl"],
                                  "question": "Compare current earnings signals.",
                                  "reportType": "COMPARATIVE"
                                }
                                """))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();

        JsonNode responseJson = objectMapper.readTree(responseBody);
        String reportId = responseJson.get("reportId").asText();

        JsonNode completedReport = waitForCompletedReport(reportId);

        assertThat(completedReport.path("reportId").asText()).isEqualTo(reportId);
        assertThat(completedReport.path("status").asText()).isEqualTo("COMPLETED");
        assertThat(completedReport.path("tickers").get(0).asText()).isEqualTo("MSFT");
        assertThat(completedReport.path("tickers").get(1).asText()).isEqualTo("AAPL");
        assertThat(completedReport.path("reportType").asText()).isEqualTo("COMPARATIVE");
        assertThat(completedReport.path("timeHorizon").asText()).isEqualTo("30d");
        assertThat(completedReport.path("sourceFilters")).hasSize(3);
        assertThat(completedReport.path("sourceFilters").get(0).asText()).isEqualTo("SEC");
        assertThat(completedReport.path("sourceFilters").get(1).asText()).isEqualTo("NEWS");
        assertThat(completedReport.path("sourceFilters").get(2).asText()).isEqualTo("EARNINGS");
        assertThat(completedReport.path("keyFindings")).hasSize(3);
        assertThat(completedReport.path("diagnostics").path("mode").asText()).isEqualTo("stub");
        assertThat(completedReport.path("diagnostics").path("ragServiceStatus").asText()).isEqualTo("stub_client");
    }

    @Test
    void listReportsFiltersHistoryByTickerAndDate() throws Exception {
        reportRepository.save(completedReport(
                "report-history-nvda",
                List.of("NVDA"),
                Instant.parse("2030-08-05T10:00:00Z")));
        reportRepository.save(completedReport(
                "report-history-amd",
                List.of("AMD"),
                Instant.parse("2030-08-05T11:00:00Z")));

        String responseBody = mockMvc.perform(get("/api/v1/reports")
                        .param("ticker", "nvda")
                        .param("createdAfter", "2030-08-05T00:00:00Z")
                        .param("createdBefore", "2030-08-06T00:00:00Z"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.count", equalTo(1)))
                .andExpect(jsonPath("$.reports[0].reportId", equalTo("report-history-nvda")))
                .andReturn()
                .getResponse()
                .getContentAsString();

        JsonNode responseJson = objectMapper.readTree(responseBody);
        assertThat(responseJson.path("reports").get(0).path("tickers").get(0).asText()).isEqualTo("NVDA");
    }

    @Test
    void getCitationDetailReturnsAuditableSourceChunk() throws Exception {
        reportRepository.save(completedReport(
                "report-citation-detail",
                List.of("NVDA"),
                Instant.parse("2026-08-05T10:00:00Z")));

        mockMvc.perform(get("/api/v1/reports/{reportId}/citations", "report-citation-detail")
                        .param("evidenceId", "nvda-sec-risk-001#chunk-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reportId", equalTo("report-citation-detail")))
                .andExpect(jsonPath("$.evidenceId", equalTo("nvda-sec-risk-001#chunk-001")))
                .andExpect(jsonPath("$.documentTitle", equalTo("NVDA sample filing risk factors")))
                .andExpect(jsonPath("$.documentUrl", equalTo("https://example.com/nvda-sec-risk-001")))
                .andExpect(jsonPath("$.publishedAt", equalTo("2026-05-28")))
                .andExpect(jsonPath("$.sourceChunk", containsString("export controls")));
    }

    @Test
    void getCitationDetailReturnsNotFoundForMissingEvidenceId() throws Exception {
        reportRepository.save(completedReport(
                "report-citation-missing",
                List.of("NVDA"),
                Instant.parse("2026-08-05T10:00:00Z")));

        mockMvc.perform(get("/api/v1/reports/{reportId}/citations", "report-citation-missing")
                        .param("evidenceId", "missing-citation"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error", equalTo("not_found")))
                .andExpect(jsonPath("$.message", equalTo(
                        "Citation not found for report report-citation-missing: missing-citation")));
    }

    @Test
    void exportReportSupportsMarkdownJsonAndPdf() throws Exception {
        reportRepository.save(completedReport(
                "report-export-test",
                List.of("NVDA"),
                Instant.parse("2026-08-05T10:00:00Z")));

        mockMvc.perform(get("/api/v1/reports/{reportId}/export", "report-export-test")
                        .param("format", "markdown"))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"report-export-test.md\""))
                .andExpect(content().string(containsString("# Financial RAG Report report-export-test")))
                .andExpect(content().string(containsString("NVDA sample filing risk factors")));

        mockMvc.perform(get("/api/v1/reports/{reportId}/export", "report-export-test")
                        .param("format", "json"))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"report-export-test.json\""))
                .andExpect(jsonPath("$.reportId", equalTo("report-export-test")));

        byte[] pdf = mockMvc.perform(get("/api/v1/reports/{reportId}/export", "report-export-test")
                        .param("format", "pdf"))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"report-export-test.pdf\""))
                .andReturn()
                .getResponse()
                .getContentAsByteArray();
        assertThat(new String(pdf, StandardCharsets.US_ASCII)).startsWith("%PDF-1.4");
    }

    @Test
    void exportReportRejectsUnsupportedFormat() throws Exception {
        reportRepository.save(completedReport(
                "report-export-invalid",
                List.of("NVDA"),
                Instant.parse("2026-08-05T10:00:00Z")));

        mockMvc.perform(get("/api/v1/reports/{reportId}/export", "report-export-invalid")
                        .param("format", "docx"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error", equalTo("invalid_request")))
                .andExpect(jsonPath("$.message", equalTo("Unsupported report export format: docx")));
    }

    @Test
    void getReportReturnsNotFoundForUnknownReport() throws Exception {
        mockMvc.perform(get("/api/v1/reports/{reportId}", "missing-report")
                        .header(REQUEST_ID_HEADER, "test-not-found-request"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(REQUEST_ID_HEADER, "test-not-found-request"))
                .andExpect(jsonPath("$.status", equalTo(404)))
                .andExpect(jsonPath("$.error", equalTo("not_found")))
                .andExpect(jsonPath("$.message", equalTo("Report not found: missing-report")))
                .andExpect(jsonPath("$.requestId", equalTo("test-not-found-request")))
                .andExpect(jsonPath("$.path", equalTo("/api/v1/reports/missing-report")))
                .andExpect(jsonPath("$.fieldErrors", hasSize(0)))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    @Test
    void createReportRejectsInvalidRequest() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(REQUEST_ID_HEADER, "test-validation-request")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "tickers": [],
                                  "question": "",
                                  "reportType": null
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(header().string(REQUEST_ID_HEADER, "test-validation-request"))
                .andExpect(jsonPath("$.status", equalTo(400)))
                .andExpect(jsonPath("$.error", equalTo("validation_failed")))
                .andExpect(jsonPath("$.message", equalTo("Request body validation failed.")))
                .andExpect(jsonPath("$.requestId", equalTo("test-validation-request")))
                .andExpect(jsonPath("$.path", equalTo("/api/v1/reports")))
                .andExpect(jsonPath("$.fieldErrors", hasSize(3)))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    @Test
    void createReportRejectsMalformedJson() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .header(REQUEST_ID_HEADER, "test-malformed-request")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{"))
                .andExpect(status().isBadRequest())
                .andExpect(header().string(REQUEST_ID_HEADER, "test-malformed-request"))
                .andExpect(jsonPath("$.status", equalTo(400)))
                .andExpect(jsonPath("$.error", equalTo("malformed_json")))
                .andExpect(jsonPath("$.message", equalTo("Request body is missing or malformed.")))
                .andExpect(jsonPath("$.requestId", equalTo("test-malformed-request")))
                .andExpect(jsonPath("$.path", equalTo("/api/v1/reports")))
                .andExpect(jsonPath("$.fieldErrors", hasSize(0)))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    private JsonNode waitForCompletedReport(String reportId) throws Exception {
        JsonNode latestReport = null;
        for (int attempt = 0; attempt < 40; attempt++) {
            String responseBody = mockMvc.perform(get("/api/v1/reports/{reportId}", reportId))
                    .andExpect(status().isOk())
                    .andReturn()
                    .getResponse()
                    .getContentAsString();
            latestReport = objectMapper.readTree(responseBody);
            if ("COMPLETED".equals(latestReport.path("status").asText())) {
                return latestReport;
            }
            Thread.sleep(50);
        }

        assertThat(latestReport).isNotNull();
        assertThat(latestReport.path("status").asText()).isEqualTo("COMPLETED");
        return latestReport;
    }

    private static ReportResponse completedReport(String reportId, List<String> tickers, Instant createdAt) {
        return new ReportResponse(
                reportId,
                ReportStatus.COMPLETED,
                tickers,
                ReportType.FILING_ANALYSIS,
                "Which filing discusses export controls?",
                "30d",
                List.of(SourceFilter.SEC),
                "Generated report summary for " + String.join(", ", tickers) + ".",
                List.of("SEC evidence mentions export controls."),
                List.of(new Citation(
                        "nvda-sec-risk-001#chunk-001",
                        "SEC",
                        "NVDA sample filing risk factors",
                        "https://example.com/nvda-sec-risk-001",
                        "Risk Factors",
                        Map.of(
                                "cik", "0001045810",
                                "form_type", "10-Q",
                                "filing_date", "2026-05-28",
                                "source_chunk", "Risk factors include export controls and supply constraints."))),
                new SourceCoverage(1, 0, 0),
                new ReportDiagnostics("local_retrieval", "completed", "completed", "completed"),
                createdAt);
    }
}
