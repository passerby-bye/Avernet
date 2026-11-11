# LangGraph 玩家：用非 OpenClaw 引擎接入「谁是卧底」牌桌

一个用 **LangGraph + OpenAI 兼容模型接口（本地用 DeepSeek 验证）** 实现的「谁是卧底」玩家。它通过 BCN WebSocket 协议（V3）作为普通 Bot 加入现有的 `6bots_undercover_game_profile` 牌桌，替换其中任意一名 OpenClaw 玩家；主持人、其他玩家、BCS 服务端和前端都不需要改动。

对应 Issue：inclusionAI/Avernet#2611。

## 它做什么、不做什么

- 做：连接 `/ws/bot`、onboard、接收状态机下发的发言/投票任务、用 LangGraph 跑「生成 → 校验 →（有上限的重试）」、把结果作为 `chat` 事件回传；精确处理 `chat.abort`，取消后的迟到结果不提交。
- 不做：不重写主持人逻辑，不读取其他玩家状态，不主动发群消息。玩家只看到任务正文里提供的上下文（`[Input]` 历史发言、`[Upstream Outputs]` 本轮前序发言、`[Instruction]` 当前要求）。

目录：

| 文件 | 职责 |
| --- | --- |
| `main.py` | 建连、握手（`protocol_version: 3`）、保存身份、onboard、把帧交给 `Runtime` |
| `runtime.py` | BCN 请求生命周期：`chat.send` ACK 与异步执行、`chat.abort`、`chat.inject`、`chat.history`；秘密词按 canonical session 隔离；可选 `timeout_ms` 兜底 |
| `player.py` | LangGraph 图：`generate → validate`，校验失败带原因重生成（最多 3 次）；字数、泄词、投票格式/候选/自投的确定性校验 |
| `INTEGRATION-NOTE.zh-CN.md` | 接入笔记：协议保证什么、引擎必须自己做什么、踩过的坑 |
| `validation/` | 4 局完整混合局的逐任务记录与统计，以及 2 次失败尝试 |
| `test_player.py` / `test_runtime.py` | 19 个单元测试：取消竞态、迟到结果不提交、秘密词隔离与继承、上游 run_id 幂等与跨会话冲突拒绝、`timeout_ms` 超时回 error（含吞掉取消的模型）、重试上限、各类违规输出 |

## 前置条件

- 已按《谁是卧底教程》跑通原版：BCS 在 `127.0.0.1:21000`，前端在 `8000`，六个游戏 Bot 已 `start bots` 且 `status bots` 全部 Running。
- Python 3.12 与一个虚拟环境。
- `singlebox/.env.local` 中已填写三项模型参数（与 OpenClaw Bot 共用）：
  `OPENCLAW_OPENAI_BASE_URL`、`OPENCLAW_OPENAI_API_KEY`、`OPENCLAW_OPENAI_MODEL_ID`。本地验证用的是 DeepSeek 的 OpenAI 兼容接口。

## 安装（约 2 分钟）

```bash
cd singlebox/agents/langgraph_undercover_player
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q          # 预期：19 passed
```

## 启动（约 10 秒）

在仓库根目录执行。身份文件会在首次握手后创建（含 token，权限 0600，请勿提交）；之后每次启动用同一身份重连，不会产生新 Bot。

```bash
set -a; . singlebox/.env.local; set +a
singlebox/agents/langgraph_undercover_player/.venv/bin/python \
  singlebox/agents/langgraph_undercover_player/main.py \
  --ws-url ws://127.0.0.1:21000/ws/bot \
  --http-url http://127.0.0.1:21000 \
  --identity "$HOME/.avernet/langgraph-identity.json" \
  --rules singlebox/agents/6bots_undercover_game_profile/player-luoji/skills/undercover-game-player/SKILL.md
```

看到 `Player onboarded: bot_xxxxxxxx` 即接入成功。此后进程把每个任务和回传记成一行 JSON 打到标准输出（不含秘密词），建议重定向到日志文件。

`--rules` 指向任意一个原玩家的 skill 说明，用作系统提示；任务正文里的具体要求（字数、钝度、候选）始终优先于它。`--name` 可改显示名（默认 `LangGraph玩家`）。

## 开一局混合牌桌

1. 打开 `http://localhost:8000/`，切到人类视角，「拉起协作」：任务协作型；主节点选「谁是卧底主持人」；成员选 **LangGraph玩家 + 4 个 OpenClaw 玩家 + 主持人**（即用它替换一名原玩家）。
2. 创建后「加入当前会话」，发送 `开始`，主持人开场后再发一次 `开始` 发牌。
3. 轮到人类席位时在右侧副屏发言、投票；其余由状态机驱动。
4. 再开一局：同一群里「新建会话」即可。

## 停止

`Ctrl+C` 或结束进程即可。运行中的任务会被取消，不会回传结果。

## 日志与排查

| 现象 | 处理 |
| --- | --- |
| 握手报 `Required BCN V3 capabilities missing` | BCS 版本过旧，需支持 `unified_run_events` 与 `canonical_session_id`。 |
| `BCN handshake rejected` 且身份文件存在 | BCS 数据被重置导致 token 失效：删除身份文件重新 onboard。 |
| 主持人汇总显示该玩家违规 | 查看进程日志里对应 run 的 `content`；校验器在回传前已拒绝超字数/泄词/非法票，若主持人仍判违规，请连同任务正文一起反馈。 |
| 玩家在线但建群时选不到 | 刷新页面；确认 onboard 成功（日志有 `Player onboarded`）。 |

本地验证记录（WSL2 + DeepSeek）：原版一局完整结束；混合牌桌 4 局完整结束（2026-11-03 三局，2026-11-11 冷启动复验一局），LangGraph 玩家的发言与投票均被主持人接受、无违规；每个任务从收到到回传约 1-5 秒。逐局记录见 `validation/`。
