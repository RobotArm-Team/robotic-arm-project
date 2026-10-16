# API 契约与 Swagger

`openapi.yaml` 是 Web 看板与事件服务之间 HTTP 接口的唯一事实来源。接口字段、数据类型、单位、错误码或路径变化，都必须与它在同一个 Pull Request 中修改。

## 使用 Swagger UI 联调

在后端服务实现后，将 Swagger UI 挂载在 `/docs`，并加载：

```text
/api/openapi.yaml
```

在后端尚未实现前，可把 `openapi.yaml` 导入 Swagger Editor 进行只读预览和字段讨论。Swagger 用于 HTTP API；视觉、标定和 ROS2 控制层内部仍按需求基线的数据对象和安全门禁工作，不能由 Web 直接绕过。

## 当前覆盖范围

- `GET /health`：系统、急停与故障状态；
- `POST /tasks`、`GET /tasks/{taskId}`：任务创建与查询；
- `GET /events`、`GET /statistics/summary`：看板数据；
- `POST /safety/stop`：软件安全停止请求，K2 急停优先级更高。
