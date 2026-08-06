package com.financialrag.backend.report;

import java.util.List;

public record ReportHistoryResponse(
        List<ReportResponse> reports,
        int count) {
}
