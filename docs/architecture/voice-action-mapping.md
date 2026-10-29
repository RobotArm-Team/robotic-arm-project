# 语音 → 安全动作 映射表（团队约定 v1，C 可自定义动作）

> 起草：A（手势/语音/验收）　|　owner：**C（控制/安全）**
> 状态：**团队约定（v1）。C 拥有动作语义决定权。**
> 编号来源（单一事实源）：`src/voice/voice_command.py` 的 `VOICE_CODES`
> 约束：A 不直接控舵机；所有动作须经 C 安全状态机（RECEIVED→VALIDATING→EXECUTING→VERIFYING→SUCCEEDED/SAFE_MODE）

## 映射（当前唯一命令）

| voice_code | 命令名 | 触发短语 | 草案动作（语义） | 安全级别 |
|---|---|---|---|---|
| 1 | SORT_ONE | “帮我分类” | **触发一次完整分拣**（一次 PickTask） | 受限、可审计 |
| 0 | 未识别 / 无关语音 | — | 不触发 | — |

## C 侧实现要点（建议）

- 以 `voice_code` 为主键查表，勿依赖 `text` 字符串。
- 触发后由 B 编排层创建一次 `PickTask`（走现有 `task_id` 幂等规则），复用 F2 抓取流程。
- 所有触发写入事件（SortEvent/事件服务），不止打印终端——符合 system-architecture 接口边界。
- A 侧已做 3s 冷却；C 侧仍建议对该事件去重，防编排层重投。

## 如需扩展

新增语音命令只需在 `src/voice/recognizer.py` 的 `COMMAND_KEYWORDS` 增加关键词 → `COMMAND_KEYWORDS` 映射，并在 `VOICE_CODES` 分配新编号；**A 侧数据结构与 API 契约无需改动**。动作语义由 C 在本表定义。
