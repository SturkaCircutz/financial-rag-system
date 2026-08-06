package com.financialrag.backend.report;

import java.util.Optional;
import java.util.List;

public interface ReportRepository {

    ReportResponse save(ReportResponse report);

    Optional<ReportResponse> findById(String reportId);

    List<ReportResponse> findAll();
}
