# 语音 → 安全动作 映射表（团队约定 v1，C 可自定义动作）

> 起草：A（手势/语音/验收）　|　owner：**C（控制/安全）**
> 状态：**团队约定（v1）。C 拥有动作语义决定权。**
> 编号来源（单一事实源）：`src/voice/voice_command.py` 的 `VOICE_CODES`
> 约束：A 不直接控舵机；所有动作须经 C 安全状态机（RECEIVED→VALIDATING→EXECUTING→VERIFYING→SUCCEEDED/SAFE_MODE）

## 映射（当前 6 条命令）

| voice_code | 命令名 | 触发短语（关键词包含匹配） | 草案动作（语义） | 安全级别 |
|---|---|---|---|---|
| 1 | SORT_ONE | “帮我分类” | **触发一次完整分拣**（一次 PickTask） | 受限、可审计 |
| 2 | START | “开始” / “开始分拣” | 启动分拣流程 | 受限、可审计 |
| 3 | PAUSE | “暂停” | 暂停当前动作 | 受限、可审计 |
| 4 | RESET | “复位” | 回到初始位姿 | 受限、可审计 |
| 5 | CANCEL | “取消” | 取消当前指令/任务 | 受限、可审计 |
| 6 | ESTOP | “急停” | **立即停止所有运动（最高优先级）** | 最高优先级 |
| 0 | 未识别 / 无关语音 | — | 不触发 | — |

> 识别策略：Vosk **自由解码**（默认），能听清任意话语；只有命中上表关键词才下发 `voice_code`，
> 闲聊/噪声只显示、不触发。嘈杂展台可用 `--grammar` 切换受限严格模式。
> 急停 `voice_code=6` 与手势 `gesture_code=6`（急停）对齐，便于 C 侧统一最高优先级处理。

## C 侧实现要点（建议）

- 以 `voice_code` 为主键查表，勿依赖 `text` 字符串。
- 触发后由 B 编排层创建一次 `PickTask`（走现有 `task_id` 幂等规则），复用 F2 抓取流程。
- 所有触发写入事件（SortEvent/事件服务），不止打印终端——符合 system-architecture 接口边界。
- A 侧已做 **按命令独立的 3s 冷却**（同命令重复说才拦，不同命令互不影响）；C 侧仍建议对该事件去重，防编排层重投。

## 如需扩展

新增语音命令只需：在 `src/voice/recognizer.py` 的 `COMMAND_KEYWORDS` 增加关键词 → 命令名映射，
在 `src/voice/voice_command.py` 的 `VOICE_CODES` 分配新编号，并在 `DEFAULT_GRAMMAR`（如启用 `--grammar`）
登记空格分词短语；**A 侧数据结构与 API 契约无需改动**。动作语义由 C 在本表定义。
