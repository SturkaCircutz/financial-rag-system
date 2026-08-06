package com.financialrag.backend.report;

public class CitationNotFoundException extends RuntimeException {

    public CitationNotFoundException(String reportId, String evidenceId) {
        super("Citation not found for report " + reportId + ": " + evidenceId);
    }
}
