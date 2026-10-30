package com.robotarm.management.api;

import com.robotarm.management.dto.ApiModels.PickResult;
import com.robotarm.management.dto.ApiModels.PickTaskRequest;
import com.robotarm.management.dto.ApiModels.TaskAccepted;
import com.robotarm.management.service.TaskService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/tasks")
public class TaskController {

    private final TaskService taskService;

    public TaskController(TaskService taskService) {
        this.taskService = taskService;
    }

    @PostMapping
    public ResponseEntity<TaskAccepted> create(@Valid @RequestBody PickTaskRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(taskService.create(request));
    }

    @GetMapping("/{taskId}")
    public PickResult get(@PathVariable String taskId) {
        return taskService.get(taskId);
    }
}
