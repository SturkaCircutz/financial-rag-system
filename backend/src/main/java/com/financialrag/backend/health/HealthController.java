package com.financialrag.backend.health;

import java.time.Instant;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class HealthController {

    private final String activeProfile;

    public HealthController(@Value("${spring.profiles.active:local}") String activeProfile) {
        this.activeProfile = activeProfile;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of(
                "status", "ok",
                "environment", activeProfile,
                "timestamp", Instant.now().toString());
    }

    @GetMapping("/ready")
    public Map<String, String> ready() {
        return Map.of("status", "ready");
    }
}
