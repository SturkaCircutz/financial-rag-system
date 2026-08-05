package com.financialrag.backend.report;

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
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/reports")
@Tag(name = "Reports", description = "Create and inspect queued financial report jobs.")
public class ReportController {

    private final ReportService reportService;

    public ReportController(ReportService reportService) {
        this.reportService = reportService;
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
}
