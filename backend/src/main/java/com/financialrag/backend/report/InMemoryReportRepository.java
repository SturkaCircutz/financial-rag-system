package com.financialrag.backend.report;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

@Repository
@ConditionalOnProperty(prefix = "reports.repository", name = "mode", havingValue = "memory", matchIfMissing = true)
public class InMemoryReportRepository implements ReportRepository {

    private final ConcurrentMap<String, ReportResponse> reports = new ConcurrentHashMap<>();

    @Override
    public ReportResponse save(ReportResponse report) {
        reports.put(report.reportId(), report);
        return report;
    }

    @Override
    public Optional<ReportResponse> findById(String reportId) {
        return Optional.ofNullable(reports.get(reportId));
    }
}
