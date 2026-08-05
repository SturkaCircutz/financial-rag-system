package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemResponse;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemResponse;

class DynamoDbReportRepositoryTest {

    @Test
    void saveWritesReportItemToConfiguredTable() {
        DynamoDbClient dynamoDbClient = org.mockito.Mockito.mock(DynamoDbClient.class);
        when(dynamoDbClient.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());
        DynamoDbReportRepository repository = new DynamoDbReportRepository(dynamoDbClient, properties());

        ReportResponse savedReport = repository.save(DynamoDbReportItemMapperTest.report());

        ArgumentCaptor<PutItemRequest> putItemRequest = ArgumentCaptor.forClass(PutItemRequest.class);
        verify(dynamoDbClient).putItem(putItemRequest.capture());
        assertThat(savedReport.reportId()).isEqualTo("report-test");
        assertThat(putItemRequest.getValue().tableName()).isEqualTo("financial-rag-test");
        assertThat(putItemRequest.getValue().item().get("PK").s()).isEqualTo("REPORT#report-test");
    }

    @Test
    void findByIdReadsReportItemFromConfiguredTable() {
        DynamoDbClient dynamoDbClient = org.mockito.Mockito.mock(DynamoDbClient.class);
        when(dynamoDbClient.getItem(any(GetItemRequest.class))).thenReturn(GetItemResponse.builder()
                .item(DynamoDbReportItemMapper.toItem(DynamoDbReportItemMapperTest.report()))
                .build());
        DynamoDbReportRepository repository = new DynamoDbReportRepository(dynamoDbClient, properties());

        var report = repository.findById("report-test");

        ArgumentCaptor<GetItemRequest> getItemRequest = ArgumentCaptor.forClass(GetItemRequest.class);
        verify(dynamoDbClient).getItem(getItemRequest.capture());
        assertThat(report).contains(DynamoDbReportItemMapperTest.report());
        assertThat(getItemRequest.getValue().tableName()).isEqualTo("financial-rag-test");
        assertThat(getItemRequest.getValue().key().get("PK").s()).isEqualTo("REPORT#report-test");
        assertThat(getItemRequest.getValue().consistentRead()).isTrue();
    }

    @Test
    void findByIdReturnsEmptyWhenItemDoesNotExist() {
        DynamoDbClient dynamoDbClient = org.mockito.Mockito.mock(DynamoDbClient.class);
        when(dynamoDbClient.getItem(any(GetItemRequest.class))).thenReturn(GetItemResponse.builder().build());
        DynamoDbReportRepository repository = new DynamoDbReportRepository(dynamoDbClient, properties());

        assertThat(repository.findById("missing-report")).isEmpty();
    }

    private static DynamoDbReportRepositoryProperties properties() {
        DynamoDbReportRepositoryProperties properties = new DynamoDbReportRepositoryProperties();
        properties.setTableName("financial-rag-test");
        return properties;
    }
}
