package com.robotarm.management.domain;

/**
 * 任务状态机，取值与 api/openapi.yaml 中 PickResult.status 保持一致。
 */
public enum TaskStatus {
    RECEIVED,
    REJECTED,
    EXECUTING,
    RETRYING,
    SUCCEEDED,
    FAILED,
    SAFE_MODE
}
