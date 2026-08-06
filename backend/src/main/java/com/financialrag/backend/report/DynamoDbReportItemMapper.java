package com.financialrag.backend.report;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import software.amazon.awssdk.services.dynamodb.model.AttributeValue;

final class DynamoDbReportItemMapper {

    private static final String REPORT_PK_PREFIX = "REPORT#";
    private static final String META_SK = "META";

    private DynamoDbReportItemMapper() {
    }

    static Map<String, AttributeValue> toItem(ReportResponse report) {
        return Map.ofEntries(
                Map.entry("PK", stringValue(reportPk(report.reportId()))),
                Map.entry("SK", stringValue(META_SK)),
                Map.entry("entityType", stringValue("REPORT")),
                Map.entry("reportId", stringValue(report.reportId())),
                Map.entry("status", stringValue(report.status().name())),
                Map.entry("tickers", stringListValue(report.tickers())),
                Map.entry("reportType", stringValue(report.reportType().name())),
                Map.entry("question", stringValue(report.question())),
                Map.entry("timeHorizon", stringValue(report.timeHorizon())),
                Map.entry("sourceFilters", sourceFiltersValue(report.sourceFilters())),
                Map.entry("summary", stringValue(report.summary())),
                Map.entry("keyFindings", stringListValue(report.keyFindings())),
                Map.entry("citations", citationsValue(report.citations())),
                Map.entry("sourceCoverage", sourceCoverageValue(report.sourceCoverage())),
                Map.entry("diagnostics", diagnosticsValue(report.diagnostics())),
                Map.entry("createdAt", stringValue(report.createdAt().toString())),
                Map.entry("GSI1PK", stringValue("STATUS#" + report.status().name())),
                Map.entry("GSI1SK", stringValue("UPDATED#" + report.createdAt() + "#" + report.reportId())));
    }

    static ReportResponse fromItem(Map<String, AttributeValue> item) {
        return new ReportResponse(
                stringAttribute(item, "reportId"),
                ReportStatus.valueOf(stringAttribute(item, "status")),
                stringListAttribute(item, "tickers"),
                ReportType.valueOf(stringAttribute(item, "reportType")),
                stringAttribute(item, "question"),
                stringAttribute(item, "timeHorizon"),
                sourceFiltersAttribute(item, "sourceFilters"),
                stringAttribute(item, "summary"),
                stringListAttribute(item, "keyFindings"),
                citationsAttribute(item, "citations"),
                sourceCoverageAttribute(item, "sourceCoverage"),
                diagnosticsAttribute(item, "diagnostics"),
                Instant.parse(stringAttribute(item, "createdAt")));
    }

    static Map<String, AttributeValue> key(String reportId) {
        return Map.of(
                "PK", stringValue(reportPk(reportId)),
                "SK", stringValue(META_SK));
    }

    private static String reportPk(String reportId) {
        return REPORT_PK_PREFIX + reportId;
    }

    private static AttributeValue stringValue(String value) {
        return AttributeValue.builder().s(value).build();
    }

    private static AttributeValue numberValue(int value) {
        return AttributeValue.builder().n(Integer.toString(value)).build();
    }

    private static AttributeValue stringListValue(List<String> values) {
        return AttributeValue.builder()
                .l(values.stream().map(DynamoDbReportItemMapper::stringValue).toList())
                .build();
    }

    private static AttributeValue sourceFiltersValue(List<SourceFilter> sourceFilters) {
        return AttributeValue.builder()
                .l(sourceFilters.stream()
                        .map(sourceFilter -> stringValue(sourceFilter.name()))
                        .toList())
                .build();
    }

    private static AttributeValue citationsValue(List<Citation> citations) {
        return AttributeValue.builder()
                .l(citations.stream()
                        .map(citation -> AttributeValue.builder()
                                .m(Map.of(
                                        "evidenceId", stringValue(citation.evidenceId()),
                                        "sourceType", stringValue(citation.sourceType()),
                                        "title", stringValue(citation.title()),
                                        "url", stringValue(citation.url()),
                                        "section", stringValue(citation.section()),
                                        "sourceMetadata", stringMapValue(citation.sourceMetadata())))
                                .build())
                        .toList())
                .build();
    }

    private static AttributeValue stringMapValue(Map<String, String> values) {
        Map<String, String> safeValues = values == null ? Map.of() : values;
        return AttributeValue.builder()
                .m(safeValues.entrySet().stream()
                        .collect(java.util.stream.Collectors.toMap(
                                Map.Entry::getKey,
                                entry -> stringValue(entry.getValue()))))
                .build();
    }

    private static AttributeValue sourceCoverageValue(SourceCoverage sourceCoverage) {
        return AttributeValue.builder()
                .m(Map.of(
                        "secChunks", numberValue(sourceCoverage.secChunks()),
                        "newsChunks", numberValue(sourceCoverage.newsChunks()),
                        "earningsChunks", numberValue(sourceCoverage.earningsChunks())))
                .build();
    }

    private static AttributeValue diagnosticsValue(ReportDiagnostics diagnostics) {
        return AttributeValue.builder()
                .m(Map.of(
                        "mode", stringValue(diagnostics.mode()),
                        "ragServiceStatus", stringValue(diagnostics.ragServiceStatus()),
                        "retrievalStatus", stringValue(diagnostics.retrievalStatus()),
                        "generationStatus", stringValue(diagnostics.generationStatus())))
                .build();
    }

    private static String stringAttribute(Map<String, AttributeValue> item, String name) {
        return item.get(name).s();
    }

    private static List<String> stringListAttribute(Map<String, AttributeValue> item, String name) {
        return item.get(name).l().stream()
                .map(AttributeValue::s)
                .toList();
    }

    private static List<SourceFilter> sourceFiltersAttribute(Map<String, AttributeValue> item, String name) {
        return item.get(name).l().stream()
                .map(attributeValue -> SourceFilter.valueOf(attributeValue.s()))
                .toList();
    }

    private static List<Citation> citationsAttribute(Map<String, AttributeValue> item, String name) {
        return item.get(name).l().stream()
                .map(attributeValue -> {
                    Map<String, AttributeValue> citation = attributeValue.m();
                    return new Citation(
                            citation.get("evidenceId").s(),
                            citation.get("sourceType").s(),
                            citation.get("title").s(),
                            citation.get("url").s(),
                            optionalStringAttribute(citation, "section"),
                            stringMapAttribute(citation, "sourceMetadata"));
                })
                .toList();
    }

    private static String optionalStringAttribute(Map<String, AttributeValue> item, String name) {
        AttributeValue value = item.get(name);
        if (value == null || value.s() == null) {
            return "";
        }
        return value.s();
    }

    private static Map<String, String> stringMapAttribute(Map<String, AttributeValue> item, String name) {
        AttributeValue value = item.get(name);
        if (value == null || value.m() == null) {
            return Map.of();
        }
        return value.m().entrySet().stream()
                .collect(java.util.stream.Collectors.toMap(
                        Map.Entry::getKey,
                        entry -> entry.getValue().s()));
    }

    private static SourceCoverage sourceCoverageAttribute(Map<String, AttributeValue> item, String name) {
        Map<String, AttributeValue> sourceCoverage = item.get(name).m();
        return new SourceCoverage(
                integerAttribute(sourceCoverage, "secChunks"),
                integerAttribute(sourceCoverage, "newsChunks"),
                integerAttribute(sourceCoverage, "earningsChunks"));
    }

    private static ReportDiagnostics diagnosticsAttribute(Map<String, AttributeValue> item, String name) {
        Map<String, AttributeValue> diagnostics = item.get(name).m();
        return new ReportDiagnostics(
                diagnostics.get("mode").s(),
                diagnostics.get("ragServiceStatus").s(),
                diagnostics.get("retrievalStatus").s(),
                diagnostics.get("generationStatus").s());
    }

    private static int integerAttribute(Map<String, AttributeValue> item, String name) {
        return Integer.parseInt(item.get(name).n());
    }
}
