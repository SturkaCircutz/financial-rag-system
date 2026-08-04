package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

    @Test
    void createReportReturnsQueuedReport() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "tickers": ["nvda"],
                                  "question": "What are the latest risk factors?",
                                  "reportType": "COMPANY_BRIEF",
                                  "timeHorizon": "30d"
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
        assertThat(completedReport.path("keyFindings")).hasSize(3);
        assertThat(completedReport.path("diagnostics").path("mode").asText()).isEqualTo("stub");
        assertThat(completedReport.path("diagnostics").path("ragServiceStatus").asText()).isEqualTo("stub_client");
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
}
