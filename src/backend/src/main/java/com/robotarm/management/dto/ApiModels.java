package com.robotarm.management.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.Map;

/**
 * HTTP 请求与响应模型，字段名与 api/openapi.yaml 一致（JSON 使用 snake_case）。
 */
public final class ApiModels {

    private ApiModels() {
    }

    public record TargetPose(
            @NotBlank String taskId,
            @NotNull Double xMm,
            @NotNull Double yMm,
            @NotNull Double zMm,
            @NotBlank String calibrationId,
            @NotNull Boolean workspaceOk) {
    }

    public record PickTaskRequest(
            @NotBlank String taskId,
            @NotBlank String armId,
            @NotNull @Valid TargetPose targetPose,
            @NotBlank String binId,
            @NotNull @Min(1) Long timeoutMs) {
    }

    public record TaskAccepted(String taskId, String status, boolean idempotent) {
    }

    public record PickResult(
            String taskId,
            String status,
            Map<String, Object> servoState,
            boolean visionVerified,
            int retryCount,
            String errorCode,
            double durationMs) {
    }

    public record SortEvent(
            String eventId,
            String taskId,
            String classId,
            String armId,
            String status,
            Map<String, String> timestamps,
            Map<String, Object> metrics,
            String errorCode) {
    }

    public record StatisticsSummary(
            Instant from,
            Instant to,
            long totalTasks,
            long successCount,
            long failureCount,
            Map<String, Long> byClass) {
    }

    public record HealthStatus(
            String status,
            String armState,
            boolean estopActive,
            boolean faultCleared,
            Instant timestamp) {
    }

    public record SafetyStopRequest(@NotBlank String reason) {
    }

    public record SafetyStopResult(String status, Instant requestedAt) {
    }

    public record ErrorResponse(String code, String message, String taskId) {
    }
}
