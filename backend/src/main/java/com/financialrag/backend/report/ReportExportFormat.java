package com.financialrag.backend.report;

import java.util.Locale;

public enum ReportExportFormat {
    JSON("application/json", "json"),
    MARKDOWN("text/markdown; charset=UTF-8", "md"),
    PDF("application/pdf", "pdf");

    private final String mediaType;
    private final String extension;

    ReportExportFormat(String mediaType, String extension) {
        this.mediaType = mediaType;
        this.extension = extension;
    }

    public String mediaType() {
        return mediaType;
    }

    public String extension() {
        return extension;
    }

    public static ReportExportFormat fromPathValue(String value) {
        return switch (value.toLowerCase(Locale.ROOT)) {
            case "json" -> JSON;
            case "markdown", "md" -> MARKDOWN;
            case "pdf" -> PDF;
            default -> throw new IllegalArgumentException("Unsupported report export format: " + value);
        };
    }
}
