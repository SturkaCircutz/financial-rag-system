package com.financialrag.backend.health;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(HealthController.class)
class HealthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void healthReturnsStatusAndEnvironment() throws Exception {
        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("ok")))
                .andExpect(jsonPath("$.environment", equalTo("local")))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    @Test
    void readyReturnsReadyStatus() throws Exception {
        mockMvc.perform(get("/api/v1/ready"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status", equalTo("ready")));
    }
}
