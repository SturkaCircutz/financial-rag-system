package com.financialrag.backend.health;

import java.time.Instant;
import java.util.Map;

import com.financialrag.backend.web.RequestIdFilter;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.headers.Header;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
@Tag(name = "Health", description = "Backend health and readiness probes.")
public class HealthController {

    private final String activeProfile;

    public HealthController(@Value("${spring.profiles.active:local}") String activeProfile) {
        this.activeProfile = activeProfile;
    }

    @GetMapping("/health")
    @Operation(summary = "Health check")
    @ApiResponse(
            responseCode = "200",
            description = "Backend is alive.",
            headers = @Header(
                    name = RequestIdFilter.REQUEST_ID_HEADER,
                    description = "Request correlation ID.",
                    schema = @Schema(type = "string")))
    public Map<String, String> health() {
        return Map.of(
                "status", "ok",
                "environment", activeProfile,
                "timestamp", Instant.now().toString());
    }

    @GetMapping("/ready")
    @Operation(summary = "Readiness check")
    @ApiResponse(
            responseCode = "200",
            description = "Backend is ready to receive traffic.",
            headers = @Header(
                    name = RequestIdFilter.REQUEST_ID_HEADER,
                    description = "Request correlation ID.",
                    schema = @Schema(type = "string")))
    public Map<String, String> ready() {
        return Map.of("status", "ready");
    }
}
