package com.financialrag.backend.report;

import java.util.List;
import java.util.Locale;

import com.financialrag.backend.rag.RagClient;
import com.financialrag.backend.rag.RagServiceContract;
import org.springframework.stereotype.Service;

@Service
public class ReportJobProcessor {

    private final ReportRepository reportRepository;
    private final RagClient ragClient;

    public ReportJobProcessor(ReportRepository reportRepository, RagClient ragClient) {
        this.reportRepository = reportRepository;
        this.ragClient = ragClient;
    }

    public void process(ReportJob job) {
        ReportResponse report = reportRepository.findById(job.reportId())
                .orElseThrow(() -> new ReportNotFoundException(job.reportId()));

        reportRepository.save(runningResponse(report));

        try {
            RagServiceContract.GenerateReportResponse ragResponse = ragClient.generateReport(
                    new RagServiceContract.GenerateReportRequest(
                            report.tickers(),
                            report.question(),
                            report.reportType().name(),
                            report.timeHorizon(),
                            mapSourceFilters(report.sourceFilters())));

            reportRepository.save(completedResponse(report, ragResponse));
        } catch (RuntimeException exception) {
            reportRepository.save(failedResponse(report));
        }
    }

    private static List<String> mapSourceFilters(List<SourceFilter> sourceFilters) {
        return sourceFilters.stream()
                .map(SourceFilter::name)
                .toList();
    }

    private static List<Citation> mapCitations(List<RagServiceContract.Citation> citations) {
        return citations.stream()
                .map(citation -> new Citation(
                        citation.evidenceId(),
                        citation.sourceType(),
                        citation.title(),
                        citation.url(),
                        citation.section(),
                        citation.sourceMetadata()))
                .toList();
    }

    private static SourceCoverage mapSourceCoverage(RagServiceContract.SourceCoverage sourceCoverage) {
        return new SourceCoverage(
                sourceCoverage.secChunks(),
                sourceCoverage.newsChunks(),
                sourceCoverage.earningsChunks());
    }

    private static ReportDiagnostics mapDiagnostics(RagServiceContract.Diagnostics diagnostics) {
        return new ReportDiagnostics(
                diagnostics.mode(),
                diagnostics.ragServiceStatus(),
                diagnostics.retrievalStatus(),
                diagnostics.generationStatus());
    }

    private static ReportResponse runningResponse(ReportResponse report) {
        return pendingResponse(report, ReportStatus.RUNNING);
    }

    private static ReportResponse pendingResponse(ReportResponse report, ReportStatus status) {
        return new ReportResponse(
                report.reportId(),
                status,
                report.tickers(),
                report.reportType(),
                report.question(),
                report.timeHorizon(),
                report.sourceFilters(),
                "",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", status.name().toLowerCase(Locale.ROOT), "not_started", "not_started"),
                report.createdAt());
    }

    private static ReportResponse completedResponse(
            ReportResponse report,
            RagServiceContract.GenerateReportResponse ragResponse) {
        return new ReportResponse(
                report.reportId(),
                ReportStatus.COMPLETED,
                report.tickers(),
                report.reportType(),
                report.question(),
                report.timeHorizon(),
                report.sourceFilters(),
                ragResponse.summary(),
                ragResponse.keyFindings(),
                mapCitations(ragResponse.citations()),
                mapSourceCoverage(ragResponse.sourceCoverage()),
                mapDiagnostics(ragResponse.diagnostics()),
                report.createdAt());
    }

    private static ReportResponse failedResponse(ReportResponse report) {
        return new ReportResponse(
                report.reportId(),
                ReportStatus.FAILED,
                report.tickers(),
                report.reportType(),
                report.question(),
                report.timeHorizon(),
                report.sourceFilters(),
                "Report generation failed before completion.",
                List.of(),
                List.of(),
                new SourceCoverage(0, 0, 0),
                new ReportDiagnostics("pending", "failed", "not_started", "failed"),
                report.createdAt());
    }
}
