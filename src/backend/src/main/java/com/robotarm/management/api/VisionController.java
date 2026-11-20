package com.robotarm.management.api;

import com.robotarm.management.service.RobotAgentClient;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 垃圾分拣：摄像头画面、YOLO 识别结果汇聚、按类别抓取投放。
 *
 * <p>识别在本机用 YOLO 推理后，通过 {@code POST /detections} 回传；本控制器只保存最近一次结果，
 * 不参与推理。动作由板子上的 robot_agent 执行。
 */
@RestController
@RequestMapping("/api/v1/vision")
public class VisionController {

    private static final Set<String> CLASSES =
            Set.of("recyclable", "hazardous", "kitchen", "other");
    private static final Map<String, String> CLASS_LABELS = Map.of(
            "recyclable", "可回收物",
            "hazardous", "有害垃圾",
            "kitchen", "厨余垃圾",
            "other", "其他垃圾");
    /** 识别结果超过该时长未更新视为过期。 */
    private static final long STALE_MS = 3000;

    private final RobotAgentClient client;
    private final AtomicReference<Map<String, Object>> latest = new AtomicReference<>();
    private final AtomicReference<Long> latestAt = new AtomicReference<>(0L);

    public VisionController(RobotAgentClient client) {
        this.client = client;
    }

    /** 识别侧回传一帧确认结果。 */
    @PostMapping("/detections")
    public ResponseEntity<Map<String, Object>> detections(@RequestBody Map<String, Object> body) {
        Object classId = body.get("class_id");
        if (classId == null || !CLASSES.contains(String.valueOf(classId))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR",
                    "class_id 必须是 " + CLASSES, null);
        }
        latest.set(body);
        latestAt.set(System.currentTimeMillis());
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Map.of("status", "ACCEPTED", "class_id", classId));
    }

    /** 最近一次识别结果；超过 3 秒未更新则认为目标已离开。 */
    @GetMapping("/latest")
    public Map<String, Object> latest() {
        Map<String, Object> detection = latest.get();
        long age = System.currentTimeMillis() - latestAt.get();
        boolean fresh = detection != null && age <= STALE_MS;
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("detection", fresh ? detection : null);
        result.put("stale", detection != null && !fresh);
        result.put("age_ms", detection == null ? null : age);
        return result;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("camera", client.visionStatus());
        result.put("latest", latest());
        result.put("classes", classes());
        return result;
    }

    @GetMapping("/classes")
    public List<Map<String, Object>> classes() {
        return CLASSES.stream().sorted().map(id -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("class_id", id);
            item.put("label", CLASS_LABELS.get(id));
            return item;
        }).toList();
    }

    @PostMapping("/camera/start")
    public ResponseEntity<Map<String, Object>> cameraStart() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(client.visionStart());
    }

    @PostMapping("/camera/stop")
    public ResponseEntity<Map<String, Object>> cameraStop() {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(client.visionStop());
    }

    /** 摄像头最新一帧；暂无画面返回 204。 */
    @GetMapping("/frame")
    public ResponseEntity<byte[]> frame() {
        byte[] data = client.visionFrame();
        if (data == null) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .contentType(MediaType.IMAGE_JPEG)
                .body(data);
    }

    /** 按识别类别执行一次抓取投放。 */
    @PostMapping("/sort")
    public ResponseEntity<Map<String, Object>> sort(@RequestBody Map<String, Object> body) {
        Object raw = body.get("class_id");
        if (raw == null || !CLASSES.contains(String.valueOf(raw))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR",
                    "class_id 必须是 " + CLASSES, null);
        }
        String classId = String.valueOf(raw);
        Map<String, Object> result = new LinkedHashMap<>(client.sort(classId));
        result.put("class_label", CLASS_LABELS.get(classId));
        result.put("requested_at", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(result);
    }
}
