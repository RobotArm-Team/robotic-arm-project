package com.robotarm.management.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * 识别事件，对应表 detection_event；字段来源为 OpenAPI 的 DetectionResult。
 */
@Entity
@Table(name = "detection_event")
public class DetectionEvent {

    @Id
    @Column(name = "event_id", nullable = false, length = 64)
    private String eventId;

    @Column(name = "task_id", length = 64)
    private String taskId;

    @Column(name = "frame_id", nullable = false, length = 64)
    private String frameId;

    @Column(name = "class_id", nullable = false, length = 32)
    private String classId;

    @Column(name = "confidence", nullable = false)
    private double confidence;

    @Column(name = "bbox_px", nullable = false, length = 128)
    private String bboxPx;

    @Column(name = "center_px", nullable = false, length = 64)
    private String centerPx;

    @Column(name = "inference_ms", nullable = false)
    private double inferenceMs;

    @Column(name = "captured_at", nullable = false)
    private Instant capturedAt;

    protected DetectionEvent() {
    }

    public DetectionEvent(String eventId, String taskId, String frameId, String classId, double confidence,
                          String bboxPx, String centerPx, double inferenceMs, Instant capturedAt) {
        this.eventId = eventId;
        this.taskId = taskId;
        this.frameId = frameId;
        this.classId = classId;
        this.confidence = confidence;
        this.bboxPx = bboxPx;
        this.centerPx = centerPx;
        this.inferenceMs = inferenceMs;
        this.capturedAt = capturedAt;
    }

    public String getEventId() {
        return eventId;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getFrameId() {
        return frameId;
    }

    public String getClassId() {
        return classId;
    }

    public double getConfidence() {
        return confidence;
    }

    public String getBboxPx() {
        return bboxPx;
    }

    public String getCenterPx() {
        return centerPx;
    }

    public double getInferenceMs() {
        return inferenceMs;
    }

    public Instant getCapturedAt() {
        return capturedAt;
    }
}
