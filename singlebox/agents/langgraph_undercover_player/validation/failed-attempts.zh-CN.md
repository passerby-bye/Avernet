# 两次失败的尝试（2026-11-03，如实记录）

两次都不是玩家侧问题，但按验收口径不计入「无需人工解卡」的完整局。

## 尝试 1（19:17-19:32）

- LangGraph 玩家 1 号。第 1 轮 6 人发言全部正常收齐（LangGraph `speak_1` 被主持人接受）。
- 状态机把 `collect` 节点派给主持人（19:22:39），主持人的 OpenClaw 网关 ACK 后约 15 分钟才真正开始执行，BCS 侧 10 分钟节点超时 → `run_failed`（19:32:40），副屏显示「本阶段未正常完成」。人类发过「卡住了」。
- 根因：主持人网关日志反复出现 `stalled session`、`stuck session recovery … abort_embedded_run`，事件循环延迟 P99 达 23 秒。模型侧（DeepSeek）0.4 秒返回，排除。主持人每局 trajectory 文件 4.4-5.4 MB，在 WSL2 drvfs 上 500 字节追加写比 ext4 慢约 400 倍。
- 处理：`OPENCLAW_TRAJECTORY=false` 重启全部 bot。

## 尝试 2（20:04-20:20）

- LangGraph 玩家 6 号。6 人发言全部正常（LangGraph「边角磨得发白，还立在架子上」）。
- `collect` 节点 20:10:39 派给主持人后其网关再次 stall，OpenClaw 自身的 stuck-session 恢复直到 20:16:51 才触发，且恢复后先重跑了排在前面的一条人类消息，`collect` 没赶上 10 分钟超时（20:20:39 `run_failed`）。
- 说明关闭 trajectory 没有根治。OpenClaw 的恢复阈值可配置：把 6 个 profile 的 `diagnostics.stuckSessionWarnMs` / `stuckSessionAbortMs` 设为 30000 / 90000 并重启 bot。
- 此后混合局 2、3、4 全部完整结束，主持人汇总节点在 5 秒到 1 分钟内交付。
