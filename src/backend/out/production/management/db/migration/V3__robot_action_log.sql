-- 机械臂动作执行日志：记录前端按钮、手势联动产生的每一次动作下发
CREATE TABLE robot_action_log (
    log_id       VARCHAR(64)  NOT NULL PRIMARY KEY,
    action       VARCHAR(32)  NOT NULL,
    action_label VARCHAR(64)  NOT NULL,
    source       VARCHAR(16)  NOT NULL,
    gesture_id   VARCHAR(32),
    status       VARCHAR(32)  NOT NULL,
    error_code   VARCHAR(64),
    message      VARCHAR(512),
    requested_at DATETIME(6)  NOT NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE INDEX idx_robot_action_log_requested ON robot_action_log (requested_at);
CREATE INDEX idx_robot_action_log_action ON robot_action_log (action);
