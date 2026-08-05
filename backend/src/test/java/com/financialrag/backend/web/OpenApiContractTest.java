package com.financialrag.backend.web;

import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class OpenApiContractTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void openApiContractDocumentsReportEndpointsAndErrors() throws Exception {
        mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.info.title").value("Financial RAG Backend API"))
                .andExpect(jsonPath("$['paths']['/api/v1/reports']['post']").exists())
                .andExpect(jsonPath("$['paths']['/api/v1/reports/{reportId}']['get']").exists())
                .andExpect(jsonPath("$['paths']['/api/v1/health']['get']").exists())
                .andExpect(jsonPath("$['paths']['/api/v1/ready']['get']").exists())
                .andExpect(jsonPath("$['components']['schemas']['ApiError']", notNullValue()))
                .andExpect(jsonPath("$['components']['schemas']['ReportRequest']", notNullValue()))
                .andExpect(jsonPath("$['components']['schemas']['ReportResponse']", notNullValue()));
    }
}
