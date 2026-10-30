package com.robotarm.management.api;

import com.robotarm.management.dto.ApiModels.SortEvent;
import com.robotarm.management.service.EventService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1")
public class EventController {

    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @GetMapping("/events")
    public List<SortEvent> list(@RequestParam(name = "task_id", required = false) String taskId,
                                @RequestParam(name = "status", required = false) String status,
                                @RequestParam(name = "limit", defaultValue = "20") int limit) {
        return eventService.list(taskId, status, limit);
    }
}
