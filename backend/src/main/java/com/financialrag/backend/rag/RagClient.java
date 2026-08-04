package com.financialrag.backend.rag;

public interface RagClient {

    RagServiceContract.GenerateReportResponse generateReport(
            RagServiceContract.GenerateReportRequest request);
}
