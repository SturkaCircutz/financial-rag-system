package com.financialrag.backend.report;

public record ReportDiagnostics(
        String mode,
        String ragServiceStatus,
        String retrievalStatus,
        String generationStatus) {
}
