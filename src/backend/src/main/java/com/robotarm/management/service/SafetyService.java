package com.robotarm.management.service;

import com.robotarm.management.dto.ApiModels.SafetyStopResult;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

/**
 * 软件安全停止：仅更新系统状态；现场 K2 急停优先级更高。
 */
@Service
public class SafetyService {

    private static final String SAFE_MODE = "SAFE_MODE";

    private final SystemStatusService systemStatusService;

    public SafetyService(SystemStatusService systemStatusService) {
        this.systemStatusService = systemStatusService;
    }

    @Transactional
    public SafetyStopResult requestStop(String reason) {
        Instant now = Instant.now();
        systemStatusService.update(SAFE_MODE, "STOPPED", now);
        return new SafetyStopResult(SAFE_MODE, now);
    }
}
