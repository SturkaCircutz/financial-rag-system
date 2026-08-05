package com.financialrag.backend.llm;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;

import org.junit.jupiter.api.Test;

class OpenAiPropertiesTest {

    @Test
    void defaultPropertiesDoNotContainSecrets() {
        OpenAiProperties properties = new OpenAiProperties();

        assertThat(properties.getApiKey()).isEmpty();
        assertThat(properties.getModel()).isEmpty();
        assertThat(properties.getTimeout()).isEqualTo(Duration.ofSeconds(30));
        assertThat(properties.isConfigured()).isFalse();
    }

    @Test
    void configuredWhenApiKeyIsPresent() {
        OpenAiProperties properties = new OpenAiProperties();

        properties.setApiKey("test-key");

        assertThat(properties.isConfigured()).isTrue();
    }
}
