package com.robotarm.management.api;

import com.robotarm.management.service.RobotAgentClient;
import java.util.Map;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 手势识别代理：把板子上 robot_agent 的摄像头识别结果透传给前端。
 *
 * <p>识别在板子上完成，前端只负责展示画面与手势类别，不做任何图像处理。
 */
@RestController
@RequestMapping("/api/v1/gesture")
public class GestureController {

    private final RobotAgentClient robotAgentClient;

    public GestureController(RobotAgentClient robotAgentClient) {
        this.robotAgentClient = robotAgentClient;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        return robotAgentClient.gestureStatus();
    }

    @GetMapping("/latest")
    public Map<String, Object> latest() {
        return robotAgentClient.gestureLatest();
    }

    @PostMapping("/start")
    public ResponseEntity<Map<String, Object>> start() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(robotAgentClient.gestureStart());
    }

    @PostMapping("/stop")
    public ResponseEntity<Map<String, Object>> stop() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(robotAgentClient.gestureStop());
    }

    /** 最新一帧 JPEG；尚未出画面时返回 204，前端保留上一帧。 */
    @GetMapping("/frame")
    public ResponseEntity<byte[]> frame() {
        byte[] jpeg = robotAgentClient.gestureFrame();
        if (jpeg == null || jpeg.length == 0) {
            return ResponseEntity.status(HttpStatus.NO_CONTENT).build();
        }
        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_JPEG)
                .cacheControl(CacheControl.noStore())
                .body(jpeg);
    }
}
