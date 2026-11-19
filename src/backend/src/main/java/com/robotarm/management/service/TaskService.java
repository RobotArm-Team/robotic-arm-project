package com.robotarm.management.service;

import com.robotarm.management.api.ApiException;
import com.robotarm.management.domain.ExceptionEvent;
import com.robotarm.management.domain.ExceptionType;
import com.robotarm.management.domain.SortTask;
import com.robotarm.management.domain.SystemStatus;
import com.robotarm.management.domain.TaskStatus;
import com.robotarm.management.dto.ApiModels.PickResult;
import com.robotarm.management.dto.ApiModels.PickTaskRequest;
import com.robotarm.management.dto.ApiModels.TaskAccepted;
import com.robotarm.management.repository.ExceptionEventRepository;
import com.robotarm.management.repository.SortTaskRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

/**
 * 任务受理：幂等、安全门禁、任务落库。
 */
@Service
public class TaskService {

    private static final String ARM_ID = "arm_1";
    private static final String SAFE_MODE = "SAFE_MODE";
    private static final String OFFLINE = "OFFLINE";

    private final SortTaskRepository taskRepository;
    private final ExceptionEventRepository exceptionEventRepository;
    private final SystemStatusService systemStatusService;
    private final ObjectMapper objectMapper;

    public TaskService(SortTaskRepository taskRepository, ExceptionEventRepository exceptionEventRepository,
                       SystemStatusService systemStatusService, ObjectMapper objectMapper) {
        this.taskRepository = taskRepository;
        this.exceptionEventRepository = exceptionEventRepository;
        this.systemStatusService = systemStatusService;
        this.objectMapper = objectMapper;
    }

    @Transactional(noRollbackFor = ApiException.class)
    public TaskAccepted create(PickTaskRequest request) {
        Optional<SortTask> existing = taskRepository.findById(request.taskId());
        if (existing.isPresent()) {
            SortTask task = existing.get();
            return new TaskAccepted(task.getTaskId(), task.getStatus().name(), true);
        }
        if (!ARM_ID.equals(request.armId())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_ARM_ID", "arm_id 仅支持 arm_1", request.taskId());
        }

        Instant now = Instant.now();
        SystemStatus system = systemStatusService.current();
        boolean blocked = system.isEstopActive() || !system.isFaultCleared()
                || SAFE_MODE.equals(system.getStatus()) || OFFLINE.equals(system.getStatus());
        if (blocked) {
            persistRejected(request, "SAFE_MODE_ACTIVE", null, now);
            throw new ApiException(HttpStatus.CONFLICT, "SAFE_MODE_ACTIVE",
                    "急停未解除或系统处于安全/离线状态，任务被拒绝", request.taskId());
        }
        if (!Boolean.TRUE.equals(request.targetPose().workspaceOk())) {
            persistRejected(request, "WORKSPACE_REJECTED", ExceptionType.OUT_OF_BOUNDS, now);
            throw new ApiException(HttpStatus.CONFLICT, "WORKSPACE_REJECTED",
                    "目标点位于有效工作区之外，任务被拒绝", request.taskId());
        }

        SortTask task = SortTask.create(request.taskId(), request.armId(), request.targetPose().xMm(),
                request.targetPose().yMm(), request.targetPose().zMm(), request.targetPose().calibrationId(),
                true, request.binId(), request.timeoutMs(), TaskStatus.RECEIVED, null, now);
        taskRepository.save(task);
        return new TaskAccepted(task.getTaskId(), task.getStatus().name(), false);
    }

    @Transactional(readOnly = true)
    public PickResult get(String taskId) {
        SortTask task = taskRepository.findById(taskId).orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND,
                "TASK_NOT_FOUND", "任务不存在", taskId));
        return new PickResult(task.getTaskId(), task.getStatus().name(), readServoState(task.getServoState()),
                task.isVisionVerified(), task.getRetryCount(), task.getErrorCode(), task.getDurationMs());
    }

    private void persistRejected(PickTaskRequest request, String errorCode, ExceptionType exceptionType,
                                 Instant now) {
        SortTask rejected = SortTask.create(request.taskId(), request.armId(), request.targetPose().xMm(),
                request.targetPose().yMm(), request.targetPose().zMm(), request.targetPose().calibrationId(),
                Boolean.TRUE.equals(request.targetPose().workspaceOk()), request.binId(), request.timeoutMs(),
                TaskStatus.REJECTED, errorCode, now);
        taskRepository.save(rejected);
        if (exceptionType != null) {
            exceptionEventRepository.save(ExceptionEvent.record(request.taskId(), exceptionType, "CONTROL",
                    "任务被安全门禁拒绝：" + errorCode, false, "REJECTED", now));
        }
    }

    private Map<String, Object> readServoState(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {
            });
        } catch (JacksonException ex) {
            return Map.of();
        }
    }
}
