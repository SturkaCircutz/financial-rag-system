package com.financialrag.backend.report;

public record ReportExport(
        ReportExportFormat format,
        String filename,
        byte[] content) {
}
