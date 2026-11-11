# 接入笔记：LangGraph 玩家接入「谁是卧底」牌桌

对应 Issue #2611 第 5 项交付物。目标读者是要用另一种引擎接入同一张牌桌的人；安装与启动见 `README.md`，这里只讲「协议替你做了什么、你必须自己做什么、我们踩过什么坑」。

## 1. 一局里玩家会收到什么

| 时机 | 帧 | 你要做的 |
| --- | --- | --- |
| 连接 | `bot.connect` 的应答 | 校验 `protocol_version == 3`，且 `capabilities.unified_run_events` 与 `canonical_session_id` 为真；保存 `token`/`bot_uuid` |
| 建群 / 入会话 | `chat.inject` | 只 ACK，不执行。正文是 `<GroupContext>` |
| 发言节点 `speak_N` | `chat.send` | 先 ACK `{run_id}`，再异步生成，回 `chat` 事件 `state: final` |
| 投票预备 `vote_start` | `chat.send` | 原样输出任务要求的播报句（只有一名存活玩家会收到） |
| 投票节点 `vote_N` | `chat.send` | 回 `我投N号` 或 `我弃权` |
| 主持人放弃任务 | `chat.abort {run_id, session_key}` | 停止该 run，回 `aborted` 事件和 `{aborted, aborted_run_ids}` |
| 前端拉历史 | `chat.history` | 可回空列表 |

任务正文的固定结构（已用真实对局核对）：

```
[BCS Group Context] …
[消息内容]
[from:BCS State Machine][State Machine Task]
node_id: speak_1 | vote_start | vote_1 | …
[Input]
{ "alive": [...], "history": [历轮所有公开发言], "opening": "...", "round": 1, "rule": "..." }
[Upstream Outputs]
(none) 或 本轮前序玩家原话
[Instruction]
你是 1 号，你的词是【象棋】。第 1 轮发言。… 不超过 25 字 …
```

## 2. 哪些行为由协议保证

- **可见范围**：worker 收不到群广播。你能看到的历史发言全部在 `[Input].history`，本轮前序发言在 `[Upstream Outputs]`。不需要、也不应该自建跨任务记忆。
- **run 标识**：`chat.send.params.idempotency_key` 就是状态机的 run id（`smnode-sm-<uuid>-speak_3-0`）。沿用它做 `run_id`，主持人日志、BCS 日志、你的日志三方才能对上。参考适配器 `openclaw-channel-bcn` 的优先级是 idempotency_key > 请求帧 id > 随机。
- **会话隔离**：V3 下 `bcs_session_id` 与 `session_key` 相同，就是 canonical session id。同一群里每局一个新会话，秘密词必须按它隔离。
- **超时兜底在服务端**：主持人侧每个节点 10 分钟超时，插件侧单 run 终态 900 秒。迟到的 final 会被丢弃（插件日志 `No run context … skipping`），不会进入对局。`chat.send` 的 `timeout_ms` 字段对状态机任务为 `null`。
- **秘密词每次重发**：发言和投票任务的 `[Instruction]` 都带 `你的词是【X】`；只有 `vote_start` 不带。

## 3. 哪些必须引擎自己实现

| 事项 | 为什么协议不替你做 | 本实现 |
| --- | --- | --- |
| 先 ACK 后执行 | 模型要跑 1-3 秒，BCS 不会等在 ACK 上 | `reply` 之后才 `create_task` |
| 终态只发一次 | abort 与 final 可能竞争 | 每个 run 一个 `terminal` 标志，谁先置位谁说了算；取消后的迟到结果不发、不写记忆 |
| 吞掉取消的模型 | `asyncio.wait_for` 只负责取消，被调用方可以忽略 | 结果返回后再看一次 `terminal` 和截止时刻 |
| 重复任务幂等 | BCS 可能重发同一 key | 同 key 只再 ACK 一次同样的 run_id，不启动第二次模型调用；同 key 换会话则拒绝 |
| 规则校验 | 主持人用确定性规则判违规，模型不保证 | 回传前按任务正文自检：单行、`不超过 N 字`（含标点）、泄词三条（整词/连续两字/拆字全含）、`我投N号`/`我弃权`、`可以投：…` 候选、`你是 N 号` 不自投、`禁止弃权` |
| 校验失败怎么办 | 截断或编票会扭曲对局 | 带原因重生成，最多 3 次，仍失败回 `error` 事件，由主持人按违规处理，整局继续 |
| 词从哪里取 | `[Input]` 里也可能出现「词是【…】」字样 | 只解析最后一段 `[Instruction]`；无词任务继承同会话上一次确认过的词 |
| 身份文件 | token 是凭据 | `os.open(..., 0o600)` 创建，不提交、不打日志 |

## 4. 踩过的坑

1. **先 ACK 再执行，终态只发一次**。早期版本在模型返回后直接发 final，没有 `terminal` 标志；测试里用一个"吞掉 CancelledError 继续返回"的假模型就能复现 abort 之后仍发 final。
2. **`wait_for` 不等于截止时间**。带 `timeout_ms` 的请求若模型吞掉取消，`wait_for` 不抛超时；需要在结果返回后再核对一次截止时刻。
3. **run_id 要用上游的**。自己生成 run_id 也能跑通，但主持人汇总、BCS 节点日志和玩家日志对不上，验收统计就得靠时间戳猜。
4. **字数按字符数且含标点**。主持人用 `len()`；"你好啊。"是 4 字。
5. **泄词第三条很严**：词是「电饭锅」，"电和饭还有锅"也算泄露。校验器与主持人保持一致，宁严勿松。
6. **前端 Bot 视角看不到对局内容**是正常的。状态机任务走 run 事件通道，不是群消息；完整记录在人类视角下。
7. **环境坑（WSL2 + drvfs）**，与协议无关但会让你以为是玩家的问题：
   - `/mnt/e` 未开 `metadata` 时所有文件 777，OpenClaw 拒绝加载 BCN 插件（world-writable）。`/etc/wsl.conf` 加 `[automount] options="metadata,umask=022,fmask=011"`。
   - OpenClaw 网关在 drvfs 上约 3 分钟才监听，singlebox 默认只等 30 秒。
   - 主持人的 OpenClaw 网关会周期性 stall（事件循环延迟 10-26 秒，trajectory 文件每局 5 MB、drvfs 小写入慢 400 倍）。两次混合局因此在 10 分钟节点超时上失败。设 `OPENCLAW_TRAJECTORY=false` 并把 profile 的 `diagnostics.stuckSessionWarnMs/AbortMs` 调到 30000/90000 后，4 局全部完成。
   - `singlebox.sh clean bots` 会清掉本地 token，但 `bcs.db` 里仍是真 token，BCS 会以 `already registered` 拒绝无 token 重连（防劫持）。日常重启用 `restart bots`；真要清，连 BCS 数据一起清。

## 5. 验收记录

四局完整对局的逐任务记录见 `validation/`：三局正式混合局（2026-11-03）加一局冷启动复验（2026-11-11）。合计发言 4、投票 4、预备播报 1；超字数 0、泄词 0、无法解析票 0、错误回传 0；主持人结算均判定该玩家无违规。两次失败的尝试（主持人网关 stall）也记在 `validation/failed-attempts.zh-CN.md`。
