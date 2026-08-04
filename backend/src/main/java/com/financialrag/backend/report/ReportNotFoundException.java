package com.financialrag.backend.report;

public class ReportNotFoundException extends RuntimeException {

    public ReportNotFoundException(String reportId) {
        super("Report not found: " + reportId);
    }
}
