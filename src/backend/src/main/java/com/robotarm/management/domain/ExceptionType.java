package com.robotarm.management.domain;

/**
 * F4 异常类型，与 docs/PROJECT_PLAN.md 6.3 节保持一致。
 */
public enum ExceptionType {
    LOW_CONFIDENCE,
    OUT_OF_BOUNDS,
    ARM_TIMEOUT,
    GRAB_FAILED,
    SERVICE_UNAVAILABLE
}
