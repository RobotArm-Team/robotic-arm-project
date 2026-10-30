# 后端管理服务（D：F3 / F4）

Java 17 + Spring Boot 4 + Spring Data JPA + Flyway + H2 的全栈管理平台后端骨架。
接口字段以仓库根目录的 `api/openapi.yaml` 为唯一事实来源，本模块不自行扩展字段。

## 运行

需要 JDK 17 及以上（本机 JDK 23 已验证）；无需单独安装 Maven，使用仓库自带的 Wrapper：

```powershell
cd src/backend
.\mvnw.cmd test          # 编译并运行测试
.\mvnw.cmd spring-boot:run
```

启动后服务地址为 `http://localhost:8080/api/v1`，H2 控制台为 `http://localhost:8080/h2-console`
（JDBC URL `jdbc:h2:file:./data/management`，用户名 `sa`，密码为空）。

## 已实现接口（与 OpenAPI 一致）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 系统与机械臂安全状态 |
| POST | `/api/v1/tasks` | 创建分拣任务；同一 `task_id` 重复提交返回已有任务且 `idempotent=true` |
| GET | `/api/v1/tasks/{taskId}` | 查询任务结果 |
| GET | `/api/v1/events` | 按时间倒序查询事件，支持 `task_id`、`status`、`limit` |
| GET | `/api/v1/statistics/summary` | 看板总览统计 |
| POST | `/api/v1/safety/stop` | 软件安全停止，写入系统状态 |

安全门禁：`workspace_ok=false` 或系统处于 `SAFE_MODE`/停机状态时返回 409，
解析为 `ErrorResponse`；越界任务同时写入 `exception_event`（`OUT_OF_BOUNDS`），可追溯。

## 数据表（Flyway 管理）

迁移脚本位于 `src/main/resources/db/migration`，共 5 张表：

- `sort_task`：任务记录
- `detection_event`：识别事件
- `arm_execution`：机械臂执行记录
- `exception_event`：异常事件（F4）
- `system_status`：系统状态（单行）

JPA 配置为 `ddl-auto=none`，表结构只由 Flyway 迁移创建，避免出现两套建表口径。

## 尚未覆盖的契约缺口

`api/openapi.yaml` 目前没有定义异常查询、任务取消与独立系统状态接口，因此本模块暂不暴露
`/api/exceptions`、`POST /api/tasks/{taskId}/cancel`、`/system/status`。异常已持久化，
待 OpenSpec 变更并由 B 确认后再补接口，不在代码里私自定义路径或字段。

## 代码结构

```text
src/main/java/com/robotarm/management
├── api/          # Controller 与统一错误响应
├── domain/       # 5 张表的 JPA 实体与状态枚举
├── dto/          # 与 OpenAPI 对齐的请求/响应模型
├── repository/   # Spring Data JPA 仓储
└── service/      # 任务受理、事件、统计、安全停止
```
