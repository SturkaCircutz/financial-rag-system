package com.financialrag.backend.report;

import java.util.Optional;

public interface ReportRepository {

    ReportResponse save(ReportResponse report);

    Optional<ReportResponse> findById(String reportId);
}
