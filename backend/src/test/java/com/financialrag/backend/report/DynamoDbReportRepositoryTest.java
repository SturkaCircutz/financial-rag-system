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
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;

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

    @Test
    void findAllScansReportItemsFromConfiguredTable() {
        DynamoDbClient dynamoDbClient = org.mockito.Mockito.mock(DynamoDbClient.class);
        ReportResponse olderReport = report("report-older", java.time.Instant.parse("2026-08-05T00:00:00Z"));
        ReportResponse newerReport = report("report-newer", java.time.Instant.parse("2026-08-06T00:00:00Z"));
        when(dynamoDbClient.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder()
                .items(
                        DynamoDbReportItemMapper.toItem(olderReport),
                        DynamoDbReportItemMapper.toItem(newerReport))
                .build());
        DynamoDbReportRepository repository = new DynamoDbReportRepository(dynamoDbClient, properties());

        var reports = repository.findAll();

        ArgumentCaptor<ScanRequest> scanRequest = ArgumentCaptor.forClass(ScanRequest.class);
        verify(dynamoDbClient).scan(scanRequest.capture());
        assertThat(scanRequest.getValue().tableName()).isEqualTo("financial-rag-test");
        assertThat(reports).containsExactly(newerReport, olderReport);
    }

    private static DynamoDbReportRepositoryProperties properties() {
        DynamoDbReportRepositoryProperties properties = new DynamoDbReportRepositoryProperties();
        properties.setTableName("financial-rag-test");
        return properties;
    }

    private static ReportResponse report(String reportId, java.time.Instant createdAt) {
        return new ReportResponse(
                reportId,
                ReportStatus.COMPLETED,
                java.util.List.of("NVDA"),
                ReportType.FILING_ANALYSIS,
                "What changed in the latest filing?",
                "30d",
                java.util.List.of(SourceFilter.SEC, SourceFilter.NEWS),
                "Generated report summary.",
                java.util.List.of("SEC finding.", "News finding."),
                java.util.List.of(new Citation(
                        "nvda-sec-risk-001#chunk-001",
                        "SEC",
                        "NVDA sample filing risk factors",
                        "https://example.com/nvda-sec-risk-001",
                        "Risk Factors",
                        java.util.Map.of("cik", "0001045810", "form_type", "10-Q"))),
                new SourceCoverage(1, 1, 0),
                new ReportDiagnostics("local_retrieval", "completed", "completed", "completed"),
                createdAt);
    }
}
