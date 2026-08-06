package com.financialrag.backend.report;

import java.util.Map;

public record Citation(
        String evidenceId,
        String sourceType,
        String title,
        String url,
        String section,
        Map<String, String> sourceMetadata) {
}
