package com.robotarm.management.service;

import com.robotarm.management.domain.SortTask;
import com.robotarm.management.domain.TaskStatus;
import com.robotarm.management.dto.ApiModels.StatisticsSummary;
import com.robotarm.management.repository.DetectionEventRepository;
import com.robotarm.management.repository.SortTaskRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 看板总览统计。
 */
@Service
public class StatisticsService {

    private final SortTaskRepository taskRepository;
    private final DetectionEventRepository detectionEventRepository;

    public StatisticsService(SortTaskRepository taskRepository, DetectionEventRepository detectionEventRepository) {
        this.taskRepository = taskRepository;
        this.detectionEventRepository = detectionEventRepository;
    }

    @Transactional(readOnly = true)
    public StatisticsSummary summary() {
        long total = taskRepository.count();
        long success = taskRepository.countByStatus(TaskStatus.SUCCEEDED);
        long failure = taskRepository.countByStatus(TaskStatus.FAILED)
                + taskRepository.countByStatus(TaskStatus.SAFE_MODE);
        Instant from = taskRepository.findFirstByOrderByCreatedAtAsc()
                .map(SortTask::getCreatedAt)
                .orElseGet(Instant::now);
        Map<String, Long> byClass = new LinkedHashMap<>();
        List<Object[]> rows = detectionEventRepository.countGroupedByClass();
        for (Object[] row : rows) {
            byClass.put((String) row[0], ((Number) row[1]).longValue());
        }
        return new StatisticsSummary(from, Instant.now(), total, success, failure, byClass);
    }
}
