package com.financialrag.backend.rag;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.time.Duration;

import org.junit.jupiter.api.Test;

class RagServicePropertiesTest {

    @Test
    void defaultPropertiesPointToLocalStubService() {
        RagServiceProperties properties = new RagServiceProperties();

        assertThat(properties.getBaseUrl()).isEqualTo(URI.create("http://localhost:8001"));
        assertThat(properties.getMode()).isEqualTo("stub");
        assertThat(properties.getTimeout()).isEqualTo(Duration.ofSeconds(30));
    }
}
