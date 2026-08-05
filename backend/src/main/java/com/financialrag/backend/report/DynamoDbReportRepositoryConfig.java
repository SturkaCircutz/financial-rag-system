package com.financialrag.backend.report;

import java.net.URI;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;

@Configuration
@ConditionalOnProperty(prefix = "reports.repository", name = "mode", havingValue = "dynamodb")
public class DynamoDbReportRepositoryConfig {

    @Bean
    public DynamoDbClient reportDynamoDbClient(DynamoDbReportRepositoryProperties properties) {
        URI endpoint = localEndpoint(properties.getEndpointUrl());

        return DynamoDbClient.builder()
                .region(Region.of(properties.getRegion()))
                .endpointOverride(endpoint)
                .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create("local", "local")))
                .build();
    }

    private static URI localEndpoint(String endpointUrl) {
        if (endpointUrl == null || endpointUrl.isBlank()) {
            throw new IllegalStateException(
                    "reports.dynamodb.endpoint-url is required. Use DynamoDB Local at http://localhost:8000.");
        }

        URI endpoint = URI.create(endpointUrl.trim());
        String host = endpoint.getHost();
        if (!isLocalHost(host)) {
            throw new IllegalStateException(
                    "DynamoDB repository is local-only right now. Use localhost or 127.0.0.1 as the endpoint.");
        }
        return endpoint;
    }

    private static boolean isLocalHost(String host) {
        return "localhost".equalsIgnoreCase(host) || "127.0.0.1".equals(host) || "::1".equals(host);
    }
}
