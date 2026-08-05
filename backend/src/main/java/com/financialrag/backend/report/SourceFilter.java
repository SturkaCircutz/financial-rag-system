package com.financialrag.backend.report;

import java.util.List;

public enum SourceFilter {
    SEC,
    NEWS,
    EARNINGS;

    public static List<SourceFilter> defaultFilters() {
        return List.of(SEC, NEWS, EARNINGS);
    }
}
