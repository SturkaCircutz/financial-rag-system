package com.financialrag.backend.report;

import java.util.Optional;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;

@Repository
@ConditionalOnProperty(prefix = "reports.repository", name = "mode", havingValue = "dynamodb")
public class DynamoDbReportRepository implements ReportRepository {

    private final DynamoDbClient dynamoDbClient;
    private final DynamoDbReportRepositoryProperties properties;

    public DynamoDbReportRepository(
            DynamoDbClient dynamoDbClient,
            DynamoDbReportRepositoryProperties properties) {
        this.dynamoDbClient = dynamoDbClient;
        this.properties = properties;
    }

    @Override
    public ReportResponse save(ReportResponse report) {
        dynamoDbClient.putItem(PutItemRequest.builder()
                .tableName(properties.getTableName())
                .item(DynamoDbReportItemMapper.toItem(report))
                .build());
        return report;
    }

    @Override
    public Optional<ReportResponse> findById(String reportId) {
        var response = dynamoDbClient.getItem(GetItemRequest.builder()
                .tableName(properties.getTableName())
                .key(DynamoDbReportItemMapper.key(reportId))
                .consistentRead(true)
                .build());

        if (!response.hasItem()) {
            return Optional.empty();
        }
        return Optional.of(DynamoDbReportItemMapper.fromItem(response.item()));
    }
}
