package com.robotarm.management.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * 机械臂执行记录，对应表 arm_execution。
 */
@Entity
@Table(name = "arm_execution")
public class ArmExecution {

    @Id
    @Column(name = "execution_id", nullable = false, length = 64)
    private String executionId;

    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "servo_state", length = 2048)
    private String servoState;

    @Column(name = "duration_ms", nullable = false)
    private double durationMs;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "recorded_at", nullable = false)
    private Instant recordedAt;

    protected ArmExecution() {
    }

    public ArmExecution(String executionId, String taskId, String status, String servoState, double durationMs,
                        String errorCode, Instant recordedAt) {
        this.executionId = executionId;
        this.taskId = taskId;
        this.status = status;
        this.servoState = servoState;
        this.durationMs = durationMs;
        this.errorCode = errorCode;
        this.recordedAt = recordedAt;
    }

    public String getExecutionId() {
        return executionId;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getStatus() {
        return status;
    }

    public String getServoState() {
        return servoState;
    }

    public double getDurationMs() {
        return durationMs;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public Instant getRecordedAt() {
        return recordedAt;
    }
}
