package com.financialrag.backend.report;

import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

public record ReportRequest(
        @NotEmpty List<@NotBlank String> tickers,
        @NotBlank String question,
        @NotNull ReportType reportType,
        String timeHorizon,
        List<SourceFilter> sourceFilters) {
}
