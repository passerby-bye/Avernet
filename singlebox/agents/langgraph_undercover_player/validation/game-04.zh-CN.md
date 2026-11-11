# 混合局 4：冷启动复验（2026-11-11 10:06-10:21）

一周后所有本地服务从停止状态重新拉起（BCS、前端、6 个 OpenClaw bot、LangGraph 玩家用原身份文件重连），再打一局，验证接入步骤可重复。

- 牌桌：主持人（OpenClaw）+ LangGraph 玩家 + 4 个 OpenClaw 玩家 + 人类席位（admin，2 号）
- 词对：平民「微波炉」/ 卧底「烤箱」
- LangGraph 玩家：3 号，平民
- 结果：卧底 6 号（逻辑控林工）第 1 轮被 5 票投出，平民获胜；无人工介入
- 会话：`bcs_grp_f3adfc172cef438a9951e5aed85ae824:01cda263`

## LangGraph 玩家逐任务记录

| 时间 | 节点 | 任务正文 | 回传 | 耗时 | 字数 | 主持人判定 |
| --- | --- | --- | --- | --- | --- | --- |
| 10:12:29 | speak_3 | 1195 字 | 摆在角落，用时按一下。 | 1.1 s | 11 | `violation: null` |
| 10:18:27 | vote_3 | 1741 字 | 我投6号 | 4.6 s | — | `violation: null`，计入 6 号 |

主持人 `speeches-set` / `votes-set` 的原始返回里，3 号两条记录的 `violation` 均为 `null`。

## 玩家事件日志（原样，不含秘密词）

```json
{"ts": 1794388349902, "event": "task", "run_id": "smnode-sm-2629b0ef-42c1-4bc0-8c0b-9ab85b488277-speak_3-0", "session": "bcs_grp_f3adfc172cef438a9951e5aed85ae824:01cda263", "node": "speak_3", "chars": 1195}
{"ts": 1794388351035, "event": "chat", "run_id": "smnode-sm-2629b0ef-42c1-4bc0-8c0b-9ab85b488277-speak_3-0", "state": "final", "content": "摆在角落，用时按一下。"}
{"ts": 1794388707458, "event": "task", "run_id": "smnode-sm-6608d961-a51c-4b90-9cce-c7f50d421adc-vote_3-0", "session": "bcs_grp_f3adfc172cef438a9951e5aed85ae824:01cda263", "node": "vote_3", "chars": 1741}
{"ts": 1794388712065, "event": "chat", "run_id": "smnode-sm-6608d961-a51c-4b90-9cce-c7f50d421adc-vote_3-0", "state": "final", "content": "我投6号"}
```

## 统计

```json
{"speeches": 1, "failed_speeches": 0, "over_limit": 0, "leaks": 0, "votes": 1, "failed_votes": 0, "unparseable_votes": 0, "valid_votes": 1, "broadcasts": 0, "errors": 0}
```

## 备注

- 主持人网关开场时出现一次 `stalled session`（事件循环延迟 14 s），90 s 内自行恢复；汇总节点 5 s、计票节点 7 s。
- 人类席位的结构化票面被主持人脚本标为「超过 10 字」，但票仍正确计入 6 号；这是主持人侧对结构化 human 票的处理，与本玩家无关。
