package com.robotarm.management.service;

import com.robotarm.management.api.ApiException;
import com.robotarm.management.domain.SortTask;
import com.robotarm.management.domain.TaskStatus;
import com.robotarm.management.dto.ApiModels.SortEvent;
import com.robotarm.management.repository.SortTaskRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 事件查询：按时间倒序返回任务事件，可按 task_id 与状态过滤。
 */
@Service
public class EventService {

    private final SortTaskRepository taskRepository;

    public EventService(SortTaskRepository taskRepository) {
        this.taskRepository = taskRepository;
    }

    @Transactional(readOnly = true)
    public List<SortEvent> list(String taskId, String status, int limit) {
        if (limit < 1 || limit > 100) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_LIMIT", "limit 取值范围为 1-100", null);
        }
        TaskStatus parsedStatus = parseStatus(status);
        Pageable page = PageRequest.of(0, limit);
        List<SortTask> tasks;
        if (taskId != null && !taskId.isBlank()) {
            tasks = parsedStatus == null
                    ? taskRepository.findByTaskIdOrderByCreatedAtDesc(taskId, page)
                    : taskRepository.findByTaskIdAndStatusOrderByCreatedAtDesc(taskId, parsedStatus, page);
        } else if (parsedStatus != null) {
            tasks = taskRepository.findByStatusOrderByCreatedAtDesc(parsedStatus, page);
        } else {
            tasks = taskRepository.findAllByOrderByCreatedAtDesc(page);
        }
        return tasks.stream().map(this::toEvent).toList();
    }

    private TaskStatus parseStatus(String status) {
        if (status == null || status.isBlank()) {
            return null;
        }
        try {
            return TaskStatus.valueOf(status);
        } catch (IllegalArgumentException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_STATUS", "未知的任务状态：" + status, null);
        }
    }

    private SortEvent toEvent(SortTask task) {
        Map<String, String> timestamps = new LinkedHashMap<>();
        timestamps.put("created_at", task.getCreatedAt().toString());
        timestamps.put("updated_at", task.getUpdatedAt().toString());
        Map<String, Object> metrics = new LinkedHashMap<>();
        metrics.put("duration_ms", task.getDurationMs());
        metrics.put("retry_count", task.getRetryCount());
        metrics.put("vision_verified", task.isVisionVerified());
        return new SortEvent("evt-" + task.getTaskId(), task.getTaskId(), null, task.getArmId(),
                task.getStatus().name(), timestamps, metrics, task.getErrorCode());
    }
}
