package com.robotarm.management.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

/**
 * 异常事件，对应表 exception_event。
 */
@Entity
@Table(name = "exception_event")
public class ExceptionEvent {

    @Id
    @Column(name = "exception_id", nullable = false, length = 64)
    private String exceptionId;

    @Column(name = "task_id", length = 64)
    private String taskId;

    @Enumerated(EnumType.STRING)
    @Column(name = "exception_type", nullable = false, length = 32)
    private ExceptionType exceptionType;

    @Column(name = "module", nullable = false, length = 32)
    private String module;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column(name = "message", nullable = false, length = 512)
    private String message;

    @Column(name = "retried", nullable = false)
    private boolean retried;

    @Column(name = "final_result", nullable = false, length = 32)
    private String finalResult;

    protected ExceptionEvent() {
    }

    private ExceptionEvent(String exceptionId, String taskId, ExceptionType exceptionType, String module,
                           String message, boolean retried, String finalResult, Instant occurredAt) {
        this.exceptionId = exceptionId;
        this.taskId = taskId;
        this.exceptionType = exceptionType;
        this.module = module;
        this.message = message;
        this.retried = retried;
        this.finalResult = finalResult;
        this.occurredAt = occurredAt;
    }

    public static ExceptionEvent record(String taskId, ExceptionType type, String module, String message,
                                        boolean retried, String finalResult, Instant occurredAt) {
        return new ExceptionEvent(UUID.randomUUID().toString(), taskId, type, module, message, retried, finalResult,
                occurredAt);
    }

    public String getExceptionId() {
        return exceptionId;
    }

    public String getTaskId() {
        return taskId;
    }

    public ExceptionType getExceptionType() {
        return exceptionType;
    }

    public String getModule() {
        return module;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public String getMessage() {
        return message;
    }

    public boolean isRetried() {
        return retried;
    }

    public String getFinalResult() {
        return finalResult;
    }
}
