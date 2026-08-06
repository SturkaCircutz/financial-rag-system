package com.financialrag.backend.report;

import java.util.Map;

public record CitationDetail(
        String reportId,
        String evidenceId,
        String sourceType,
        String documentTitle,
        String documentUrl,
        String section,
        String publishedAt,
        String sourceChunk,
        Map<String, String> sourceMetadata) {
}
