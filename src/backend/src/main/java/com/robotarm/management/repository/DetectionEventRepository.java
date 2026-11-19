package com.robotarm.management.repository;

import com.robotarm.management.domain.DetectionEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface DetectionEventRepository extends JpaRepository<DetectionEvent, String> {

    @Query("select d.classId as classId, count(d) as total from DetectionEvent d "
            + "where d.classId is not null group by d.classId")
    List<Object[]> countGroupedByClass();

    List<DetectionEvent> findByTaskId(@Param("taskId") String taskId);
}
