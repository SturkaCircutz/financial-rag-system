package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class DynamoDbReportRepositoryConfigTest {

    @Test
    void buildsClientForLocalEndpoint() {
        DynamoDbReportRepositoryProperties properties = new DynamoDbReportRepositoryProperties();
        properties.setEndpointUrl("http://localhost:8000");

        try (var client = new DynamoDbReportRepositoryConfig().reportDynamoDbClient(properties)) {
            assertThat(client).isNotNull();
        }
    }

    @Test
    void rejectsBlankEndpoint() {
        DynamoDbReportRepositoryProperties properties = new DynamoDbReportRepositoryProperties();
        properties.setEndpointUrl(" ");

        assertThatThrownBy(() -> new DynamoDbReportRepositoryConfig().reportDynamoDbClient(properties))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("DynamoDB Local");
    }

    @Test
    void rejectsRemoteEndpoint() {
        DynamoDbReportRepositoryProperties properties = new DynamoDbReportRepositoryProperties();
        properties.setEndpointUrl("https://dynamodb.us-east-1.amazonaws.com");

        assertThatThrownBy(() -> new DynamoDbReportRepositoryConfig().reportDynamoDbClient(properties))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("local-only");
    }
}
