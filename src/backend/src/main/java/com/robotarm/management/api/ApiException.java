package com.robotarm.management.api;

import org.springframework.http.HttpStatus;

/**
 * 携带 HTTP 状态与错误码的业务异常，由 GlobalExceptionHandler 统一转换为 ErrorResponse。
 */
public class ApiException extends RuntimeException {

    private final HttpStatus status;
    private final String code;
    private final String taskId;

    public ApiException(HttpStatus status, String code, String message, String taskId) {
        super(message);
        this.status = status;
        this.code = code;
        this.taskId = taskId;
    }

    public HttpStatus getStatus() {
        return status;
    }

    public String getCode() {
        return code;
    }

    public String getTaskId() {
        return taskId;
    }
}
