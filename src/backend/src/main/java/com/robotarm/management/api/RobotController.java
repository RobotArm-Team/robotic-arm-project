package com.robotarm.management.api;

import com.robotarm.management.service.RobotAgentClient;
import java.util.Map;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 机械臂动作控制：把前端按钮转发给板子上的 robot_agent.py。
 *
 * <p>接口路径前缀 /api/v1/robot，动作名限定为小写字母与下划线。
 */
@RestController
@RequestMapping("/api/v1/robot")
public class RobotController {

    private static final Pattern ACTION_NAME = Pattern.compile("[a-z][a-z0-9_]{0,31}");

    private final RobotAgentClient robotAgentClient;

    public RobotController(RobotAgentClient robotAgentClient) {
        this.robotAgentClient = robotAgentClient;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return robotAgentClient.health();
    }

    @GetMapping("/actions")
    public Map<String, Object> actions() {
        return robotAgentClient.actions();
    }

    @GetMapping("/state")
    public Map<String, Object> state() {
        return robotAgentClient.state();
    }

    @PostMapping("/actions/{action}")
    public ResponseEntity<Map<String, Object>> run(@PathVariable("action") String action) {
        if (!ACTION_NAME.matcher(action).matches()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ACTION_NOT_FOUND",
                    "未知的机械臂动作：" + action, null);
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(robotAgentClient.run(action));
    }

    @PostMapping("/stop")
    public ResponseEntity<Map<String, Object>> stop() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(robotAgentClient.stop());
    }
}
