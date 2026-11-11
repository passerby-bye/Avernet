# 混合局 1（2026-11-03 19:50-20:03）

- 牌桌：主持人（OpenClaw）+ LangGraph 玩家 + 4 个 OpenClaw 玩家 + 人类席位（admin，6 号）
- 词对：平民「日记」/ 卧底「相册」
- LangGraph 玩家：2 号，**卧底**
- 结果：第 1 轮 LangGraph 玩家被 3 票投出，平民获胜；全程无人工「卡住了」介入
- 会话：`bcs_grp_f3adfc172cef438a9951e5aed85ae824:716c0cbf`

## LangGraph 玩家逐任务记录

| 时间 | 节点 | 任务正文 | 回传 | 耗时 | 字数 | 主持人判定 |
| --- | --- | --- | --- | --- | --- | --- |
| 19:53:59 | speak_2 | 1195 字 | 平时收在柜子下层，隔很久才动。 | 3.1 s | 15 | 无违规 |
| 20:01:20 | vote_2 | 1780 字 | 我投5号 | 2.2 s | — | 有效票（5 号在候选内） |

## 统计（`stats.py`，口径与主持人一致）

```json
{"speeches": 1, "failed_speeches": 0, "over_limit": 0, "leaks": 0, "votes": 1, "failed_votes": 0, "unparseable_votes": 0, "valid_votes": 1, "broadcasts": 0, "errors": 0}
```

## 备注

主持人网关本局出现 9 条 `stalled session` 与 1 次 `stuck session recovery`（19:58:39），均自行恢复，汇总节点约 1 分钟内交付。本局前 `OPENCLAW_TRAJECTORY=false` 已生效。
