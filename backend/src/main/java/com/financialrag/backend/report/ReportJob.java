package com.financialrag.backend.report;

public record ReportJob(String reportId, String requestId) {

    public ReportJob(String reportId) {
        this(reportId, "unknown");
    }
}
