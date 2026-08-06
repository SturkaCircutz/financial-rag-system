package com.financialrag.backend.report;

import java.time.Instant;

import jakarta.validation.Valid;

import com.financialrag.backend.web.ApiError;
import com.financialrag.backend.web.RequestIdFilter;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.headers.Header;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/reports")
@Tag(name = "Reports", description = "Create and inspect queued financial report jobs.")
public class ReportController {

    private final ReportService reportService;
    private final ReportExportService reportExportService;

    public ReportController(ReportService reportService, ReportExportService reportExportService) {
        this.reportService = reportService;
        this.reportExportService = reportExportService;
    }

    @GetMapping
    @Operation(summary = "List report history", description = "Returns past report jobs, optionally filtered by ticker and creation time.")
    public ReportHistoryResponse listReports(
            @RequestParam(required = false) String ticker,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant createdAfter,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant createdBefore) {
        return reportService.listReports(ticker, createdAfter, createdBefore);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create a report job", description = "Queues a financial RAG report job and returns the initial job state.")
    @ApiResponses({
            @ApiResponse(
                    responseCode = "201",
                    description = "Report job queued.",
                    headers = @Header(
                            name = RequestIdFilter.REQUEST_ID_HEADER,
                            description = "Request correlation ID.",
                            schema = @Schema(type = "string"))),
            @ApiResponse(
                    responseCode = "400",
                    description = "Invalid or malformed request.",
                    headers = @Header(
                            name = RequestIdFilter.REQUEST_ID_HEADER,
                            description = "Request correlation ID.",
                            schema = @Schema(type = "string")),
                    content = @Content(schema = @Schema(implementation = ApiError.class)))
    })
    public ReportResponse createReport(@Valid @RequestBody ReportRequest request) {
        return reportService.createReport(request);
    }

    @GetMapping("/{reportId}")
    @Operation(summary = "Get report job state", description = "Returns the latest known state for a queued report job.")
    @ApiResponses({
            @ApiResponse(
                    responseCode = "200",
                    description = "Report job found.",
                    headers = @Header(
                            name = RequestIdFilter.REQUEST_ID_HEADER,
                            description = "Request correlation ID.",
                            schema = @Schema(type = "string"))),
            @ApiResponse(
                    responseCode = "404",
                    description = "Report job was not found.",
                    headers = @Header(
                            name = RequestIdFilter.REQUEST_ID_HEADER,
                            description = "Request correlation ID.",
                            schema = @Schema(type = "string")),
                    content = @Content(schema = @Schema(implementation = ApiError.class)))
    })
    public ReportResponse getReport(@PathVariable String reportId) {
        return reportService.getReport(reportId);
    }

    @GetMapping("/{reportId}/citations")
    @Operation(summary = "Get citation detail", description = "Returns source metadata and source chunk text for one report citation.")
    public CitationDetail getCitationDetail(
            @PathVariable String reportId,
            @RequestParam String evidenceId) {
        return reportService.getCitationDetail(reportId, evidenceId);
    }

    @GetMapping("/{reportId}/export")
    @Operation(summary = "Export report", description = "Exports a report as JSON, Markdown, or PDF.")
    public ResponseEntity<byte[]> exportReport(
            @PathVariable String reportId,
            @RequestParam(defaultValue = "markdown") String format) {
        ReportResponse report = reportService.getReport(reportId);
        ReportExport export = reportExportService.export(report, ReportExportFormat.fromPathValue(format));

        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(export.format().mediaType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + export.filename() + "\"")
                .body(export.content());
    }
}
