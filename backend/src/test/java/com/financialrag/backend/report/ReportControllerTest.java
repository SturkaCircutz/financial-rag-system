package com.financialrag.backend.report;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void createReportReturnsCompletedStubReport() throws Exception {
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
                .andExpect(jsonPath("$.reportId", notNullValue()))
                .andExpect(jsonPath("$.status", equalTo("COMPLETED")))
                .andExpect(jsonPath("$.tickers[0]", equalTo("NVDA")))
                .andExpect(jsonPath("$.reportType", equalTo("COMPANY_BRIEF")))
                .andExpect(jsonPath("$.question", equalTo("What are the latest risk factors?")))
                .andExpect(jsonPath("$.timeHorizon", equalTo("30d")))
                .andExpect(jsonPath("$.summary", notNullValue()))
                .andExpect(jsonPath("$.keyFindings", hasSize(3)))
                .andExpect(jsonPath("$.citations", hasSize(0)))
                .andExpect(jsonPath("$.sourceCoverage.secChunks", equalTo(0)))
                .andExpect(jsonPath("$.sourceCoverage.newsChunks", equalTo(0)))
                .andExpect(jsonPath("$.sourceCoverage.earningsChunks", equalTo(0)))
                .andExpect(jsonPath("$.diagnostics.mode", equalTo("stub")))
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

        mockMvc.perform(get("/api/v1/reports/{reportId}", reportId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reportId", equalTo(reportId)))
                .andExpect(jsonPath("$.status", equalTo("COMPLETED")))
                .andExpect(jsonPath("$.tickers[0]", equalTo("MSFT")))
                .andExpect(jsonPath("$.tickers[1]", equalTo("AAPL")))
                .andExpect(jsonPath("$.reportType", equalTo("COMPARATIVE")))
                .andExpect(jsonPath("$.timeHorizon", equalTo("30d")));
    }

    @Test
    void getReportReturnsNotFoundForUnknownReport() throws Exception {
        mockMvc.perform(get("/api/v1/reports/{reportId}", "missing-report"))
                .andExpect(status().isNotFound());
    }

    @Test
    void createReportRejectsInvalidRequest() throws Exception {
        mockMvc.perform(post("/api/v1/reports")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "tickers": [],
                                  "question": "",
                                  "reportType": null
                                }
                                """))
                .andExpect(status().isBadRequest());
    }
}
