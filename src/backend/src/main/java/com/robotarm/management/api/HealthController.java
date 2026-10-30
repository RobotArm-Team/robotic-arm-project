package com.robotarm.management.api;

import com.robotarm.management.domain.SystemStatus;
import com.robotarm.management.dto.ApiModels.HealthStatus;
import com.robotarm.management.service.SystemStatusService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;

@RestController
@RequestMapping("/api/v1")
public class HealthController {

    private final SystemStatusService systemStatusService;

    public HealthController(SystemStatusService systemStatusService) {
        this.systemStatusService = systemStatusService;
    }

    @GetMapping("/health")
    public HealthStatus health() {
        SystemStatus status = systemStatusService.current();
        return new HealthStatus(status.getStatus(), status.getArmState(), status.isEstopActive(),
                status.isFaultCleared(), Instant.now());
    }
}
