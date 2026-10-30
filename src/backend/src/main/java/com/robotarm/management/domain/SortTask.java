package com.robotarm.management.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * 分拣任务记录，对应表 sort_task。
 */
@Entity
@Table(name = "sort_task")
public class SortTask {

    @Id
    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Column(name = "arm_id", nullable = false, length = 32)
    private String armId;

    @Column(name = "x_mm", nullable = false)
    private double xMm;

    @Column(name = "y_mm", nullable = false)
    private double yMm;

    @Column(name = "z_mm", nullable = false)
    private double zMm;

    @Column(name = "calibration_id", nullable = false, length = 64)
    private String calibrationId;

    @Column(name = "workspace_ok", nullable = false)
    private boolean workspaceOk;

    @Column(name = "bin_id", nullable = false, length = 64)
    private String binId;

    @Column(name = "timeout_ms", nullable = false)
    private long timeoutMs;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private TaskStatus status;

    @Column(name = "servo_state", length = 2048)
    private String servoState;

    @Column(name = "vision_verified", nullable = false)
    private boolean visionVerified;

    @Column(name = "retry_count", nullable = false)
    private int retryCount;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "duration_ms", nullable = false)
    private double durationMs;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected SortTask() {
    }

    private SortTask(String taskId, String armId, double xMm, double yMm, double zMm, String calibrationId,
                     boolean workspaceOk, String binId, long timeoutMs, TaskStatus status, String errorCode,
                     Instant now) {
        this.taskId = taskId;
        this.armId = armId;
        this.xMm = xMm;
        this.yMm = yMm;
        this.zMm = zMm;
        this.calibrationId = calibrationId;
        this.workspaceOk = workspaceOk;
        this.binId = binId;
        this.timeoutMs = timeoutMs;
        this.status = status;
        this.errorCode = errorCode;
        this.visionVerified = false;
        this.retryCount = 0;
        this.durationMs = 0;
        this.createdAt = now;
        this.updatedAt = now;
    }

    public static SortTask create(String taskId, String armId, double xMm, double yMm, double zMm,
                                  String calibrationId, boolean workspaceOk, String binId, long timeoutMs,
                                  TaskStatus status, String errorCode, Instant now) {
        return new SortTask(taskId, armId, xMm, yMm, zMm, calibrationId, workspaceOk, binId, timeoutMs, status,
                errorCode, now);
    }

    public String getTaskId() {
        return taskId;
    }

    public String getArmId() {
        return armId;
    }

    public double getXMm() {
        return xMm;
    }

    public double getYMm() {
        return yMm;
    }

    public double getZMm() {
        return zMm;
    }

    public String getCalibrationId() {
        return calibrationId;
    }

    public boolean isWorkspaceOk() {
        return workspaceOk;
    }

    public String getBinId() {
        return binId;
    }

    public long getTimeoutMs() {
        return timeoutMs;
    }

    public TaskStatus getStatus() {
        return status;
    }

    public String getServoState() {
        return servoState;
    }

    public boolean isVisionVerified() {
        return visionVerified;
    }

    public int getRetryCount() {
        return retryCount;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public double getDurationMs() {
        return durationMs;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
