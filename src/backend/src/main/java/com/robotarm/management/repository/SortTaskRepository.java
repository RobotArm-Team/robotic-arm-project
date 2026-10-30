package com.robotarm.management.repository;

import com.robotarm.management.domain.SortTask;
import com.robotarm.management.domain.TaskStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SortTaskRepository extends JpaRepository<SortTask, String> {

    long countByStatus(TaskStatus status);

    List<SortTask> findAllByOrderByCreatedAtDesc(Pageable pageable);

    List<SortTask> findByStatusOrderByCreatedAtDesc(TaskStatus status, Pageable pageable);

    List<SortTask> findByTaskIdOrderByCreatedAtDesc(String taskId, Pageable pageable);

    List<SortTask> findByTaskIdAndStatusOrderByCreatedAtDesc(String taskId, TaskStatus status, Pageable pageable);

    Optional<SortTask> findFirstByOrderByCreatedAtAsc();
}
