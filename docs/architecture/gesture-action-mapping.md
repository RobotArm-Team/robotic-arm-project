# 手势 → 安全动作 映射表（草案，供 C 确认/自定义）

> 起草：A（手势/语音/验收）　|　owner：**C（控制/安全）**
> 状态：**草案，C 可改动作语义，但急停优先级不可降**
> 编号来源（单一事实源）：`src/gesture/gesture_command.py` 的 `GESTURE_CODES`
> 约束：A 不直接控舵机；所有动作须经 C 安全状态机（RECEIVED→VALIDATING→EXECUTING→VERIFYING→SUCCEEDED/SAFE_MODE）

## 映射草案

| gesture_code | gesture_id | 草案动作（语义） | 安全级别 | 说明 |
|---|---|---|---|---|
| 1 | FIST | **暂停**当前抓取任务（pause） | 受限、可恢复 | 不丢任务，停在当前安全位 |
| 2 | OPEN_PALM | **恢复/继续**（resume） | 受限、可恢复 | 与 FIST 配对，解除暂停 |
| 3 | POINT_UP | **单步/确认下一目标** | 受限、可审计 | 可选：手动步进模式触发一次 PickTask |
| 4 | PEACE | **复位到安全初始位**（reset/home） | 受限、可审计 | 回零/回安全home，不改变任务队列 |
| 5 | ROCK | **取消当前任务**（cancel） | 受限、可审计 | 中止当前 PickTask，回安全位 |
| 6 | PINCH | **急停 E-STOP** | **最高优先级** | 超越其它手势与语音命令，立即进入 SAFE_MODE |
| 7 | THUMBS_UP | **系统就绪/开始**（start/ready） | 受限、可恢复 | 可选：解除待机、进入可运行态 |
| 0 | NONE/UNKNOWN | 不触发 | — | command_gate 已拦截，不下发 |

## C 侧实现要点（建议）

- 以 `gesture_code` 为主键查表，勿依赖 gesture_id 字符串。
- 急停（=6）在任何状态下都可打断，进入 SAFE_MODE；恢复须人工确认。
- 所有动作写入事件（SortEvent/事件服务），不止打印终端——符合 system-architecture 接口边界。
- 冷却 10s 由 A 侧 command_gate 保证；C 侧仍建议对该事件去重，防编排层重投。

## 如需调整

若 C 希望换手势含义（例如把急停绑到 THUMBS_UP），只需改本表与 C 侧映射，
**A 侧代码与 GESTURE_CODES 无需改动**——这正是"编号解耦"的目的。
