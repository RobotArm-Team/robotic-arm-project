-- 任务记录
CREATE TABLE sort_task (
    task_id          VARCHAR(64)  NOT NULL PRIMARY KEY,
    arm_id           VARCHAR(32)  NOT NULL,
    x_mm             DOUBLE PRECISION NOT NULL,
    y_mm             DOUBLE PRECISION NOT NULL,
    z_mm             DOUBLE PRECISION NOT NULL,
    calibration_id   VARCHAR(64)  NOT NULL,
    workspace_ok     BOOLEAN      NOT NULL,
    bin_id           VARCHAR(64)  NOT NULL,
    timeout_ms       BIGINT       NOT NULL,
    status           VARCHAR(32)  NOT NULL,
    servo_state      VARCHAR(2048),
    vision_verified  BOOLEAN      NOT NULL,
    retry_count      INTEGER      NOT NULL,
    error_code       VARCHAR(64),
    duration_ms      DOUBLE PRECISION NOT NULL,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_sort_task_status ON sort_task (status);
CREATE INDEX idx_sort_task_created_at ON sort_task (created_at);

-- 识别事件
CREATE TABLE detection_event (
    event_id     VARCHAR(64)  NOT NULL PRIMARY KEY,
    task_id      VARCHAR(64),
    frame_id     VARCHAR(64)  NOT NULL,
    class_id     VARCHAR(32)  NOT NULL,
    confidence   DOUBLE PRECISION NOT NULL,
    bbox_px      VARCHAR(128) NOT NULL,
    center_px    VARCHAR(64)  NOT NULL,
    inference_ms DOUBLE PRECISION NOT NULL,
    captured_at  TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_detection_event_task ON detection_event (task_id);

-- 机械臂执行记录
CREATE TABLE arm_execution (
    execution_id VARCHAR(64)  NOT NULL PRIMARY KEY,
    task_id      VARCHAR(64)  NOT NULL,
    status       VARCHAR(32)  NOT NULL,
    servo_state  VARCHAR(2048),
    duration_ms  DOUBLE PRECISION NOT NULL,
    error_code   VARCHAR(64),
    recorded_at  TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_arm_execution_task ON arm_execution (task_id);

-- 异常事件（F4）
CREATE TABLE exception_event (
    exception_id   VARCHAR(64)  NOT NULL PRIMARY KEY,
    task_id        VARCHAR(64),
    exception_type VARCHAR(32)  NOT NULL,
    module         VARCHAR(32)  NOT NULL,
    occurred_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    message        VARCHAR(512) NOT NULL,
    retried        BOOLEAN      NOT NULL,
    final_result   VARCHAR(32)  NOT NULL
);

CREATE INDEX idx_exception_event_task ON exception_event (task_id);
CREATE INDEX idx_exception_event_type ON exception_event (exception_type);

-- 系统状态（单行，主键固定为 1）
CREATE TABLE system_status (
    id            BIGINT       NOT NULL PRIMARY KEY,
    status        VARCHAR(32)  NOT NULL,
    arm_state     VARCHAR(32)  NOT NULL,
    estop_active  BOOLEAN      NOT NULL,
    fault_cleared BOOLEAN      NOT NULL,
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL
);
