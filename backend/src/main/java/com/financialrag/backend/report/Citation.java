package com.financialrag.backend.report;

public record Citation(
        String evidenceId,
        String sourceType,
        String title,
        String url) {
}
