package com.financialrag.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import software.amazon.awssdk.services.dynamodb.model.AttributeValue;

class DynamoDbReportItemMapperTest {

    @Test
    void mapsReportToDynamoDbItemAndBack() {
        ReportResponse report = report();

        Map<String, AttributeValue> item = DynamoDbReportItemMapper.toItem(report);
        ReportResponse mappedReport = DynamoDbReportItemMapper.fromItem(item);

        assertThat(item.get("PK").s()).isEqualTo("REPORT#report-test");
        assertThat(item.get("SK").s()).isEqualTo("META");
        assertThat(item.get("GSI1PK").s()).isEqualTo("STATUS#COMPLETED");
        assertThat(item.get("citations").l()).hasSize(1);
        assertThat(mappedReport).isEqualTo(report);
    }

    @Test
    void buildsReportKey() {
        Map<String, AttributeValue> key = DynamoDbReportItemMapper.key("report-test");

        assertThat(key.get("PK").s()).isEqualTo("REPORT#report-test");
        assertThat(key.get("SK").s()).isEqualTo("META");
    }

    static ReportResponse report() {
        return new ReportResponse(
                "report-test",
                ReportStatus.COMPLETED,
                List.of("NVDA"),
                ReportType.FILING_ANALYSIS,
                "What changed in the latest filing?",
                "30d",
                List.of(SourceFilter.SEC, SourceFilter.NEWS),
                "Generated report summary.",
                List.of("SEC finding.", "News finding."),
                List.of(new Citation(
                        "nvda-sec-risk-001#chunk-001",
                        "SEC",
                        "NVDA sample filing risk factors",
                        "https://example.com/nvda-sec-risk-001")),
                new SourceCoverage(1, 1, 0),
                new ReportDiagnostics("local_retrieval", "completed", "completed", "completed"),
                Instant.parse("2026-08-05T00:00:00Z"));
    }
}
