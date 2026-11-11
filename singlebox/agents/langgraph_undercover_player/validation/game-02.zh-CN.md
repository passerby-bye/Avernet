# 混合局 2（2026-11-03 20:32-20:46）

- 牌桌：主持人（OpenClaw）+ LangGraph 玩家 + 4 个 OpenClaw 玩家 + 人类席位（admin）
- 词对：平民「超市」/ 卧底「便利店」
- LangGraph 玩家：1 号，平民
- 结果：卧底 4 号（稳健老陈）第 1 轮被投出，平民获胜；无人工介入
- 会话：`bcs_grp_f3adfc172cef438a9951e5aed85ae824:5c9a981b`
- 本局前已把 6 个 OpenClaw profile 的 `diagnostics.stuckSessionWarnMs/AbortMs` 设为 30000/90000

## LangGraph 玩家逐任务记录

| 时间 | 节点 | 任务正文 | 回传 | 耗时 | 字数 | 主持人判定 |
| --- | --- | --- | --- | --- | --- | --- |
| 20:35:11 | speak_1 | 1169 字 | 需要的时候常会去一趟，东西挺齐全。 | 1.1 s | 17 | 无违规 |
| 20:44:29 | vote_start | 1546 字 | 投票开始，请大家投出一票，等待主持人公布结果。 | 0.8 s | — | 预备确认播报，原样输出 |
| 20:44:30 | vote_1 | 1788 字 | 我投6号 | 1.7 s | — | 有效票 |

`vote_start` 是状态机在开投前派给一名存活玩家的预备确认任务，本局派给了 1 号；它不计入投票数。

## 统计

```json
{"speeches": 1, "failed_speeches": 0, "over_limit": 0, "leaks": 0, "votes": 1, "failed_votes": 0, "unparseable_votes": 0, "valid_votes": 1, "broadcasts": 1, "errors": 0}
```
