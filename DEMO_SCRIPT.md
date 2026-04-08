# STOI 答辩 Demo 脚本

> 答辩时间：2 分钟 Demo
> 目录：`cd ~/.cola/outputs/STOI-Demo-开发`

---

## 第一步：离线分析（0:00 - 0:30）

> "STOI 不需要任何配置，直接读你的 Claude Code 历史记录。"

```bash
python3 stoi.py analyze
```

**期望效果**：
- 自动找到最近的 Claude Code session 文件
- 打印含屎量报告，显示每轮的 STOI 分数
- 表格展示：时间、含屎量、输入 tokens、缓存命中、浪费量、等级

---

## 第二步：含屎量统计 + TTS（0:30 - 1:00）

> "一行命令，含屎量一目了然。"

```bash
python3 stoi.py stats
```

**期望效果**：
- 打印总报告：会话数、平均含屎量、总浪费 tokens
- 等级分布柱状图
- 🔊 **TTS 语音播报**（这是全场高潮）："含屎量严重超标，建议立刻停止 Vibe Coding。"

---

## 第三步：多轮趋势（1:00 - 1:20）

> "更重要的是趋势——含屎量在随时间增长，还是在收敛？"

```bash
python3 stoi.py trend
```

**期望效果**：
- ASCII 柱状图，显示最近 30 轮含屎量变化
- 指出"这里发生了一次 cache 击穿事件"

---

## 第四步：TUI 实时看板（1:20 - 2:00）

> "这是我们的实时监控界面。"

```bash
python3 stoi.py tui
```

**期望效果**：
- 暗色 TUI 界面启动
- 左侧：大字含屎量分数 + 进度条
- 右侧：本次会话 token 数据
- 底部：多轮趋势 sparkline + 改进建议
- 按 `q` 退出

---

## 备用：Blame 演示（如有时间）

> "还能找出是谁在造屎。"

```bash
python3 stoi.py blame
# 粘贴一段包含时间戳的 System Prompt
# 例：System prompt with timestamp: 2026-04-08T22:00:00
# 输入 END
```

**期望效果**：
- 检测出时间戳注入
- 给出"移至 user message"的具体建议

---

## 环境确认清单（答辩前检查）

```bash
# 确认依赖
pip3 show textual rich aiohttp | grep -E "Name|Version"

# 确认数据存在
ls ~/.stoi/sessions.jsonl  # 或
ls ~/.claude/projects/

# 跑一遍全流程
python3 stoi.py analyze
python3 stoi.py stats
python3 stoi.py trend
python3 stoi.py tui  # Ctrl+C 退出
```

---

## 答辩时的话术

**开场**：
> "现在所有人都在为 AI 工具付账单，但没有人知道这些钱花得值不值。STOI 是第一个回答这个问题的工具。"

**展示 analyze 时**：
> "这是我今天用 Claude Code 的真实数据，STOI 直接从本地文件读取，零侵入。"

**TTS 响起时**：
> （笑）"这就是含含告诉我的。"

**结尾**：
> "有 OKR，有 ROI，现在有 STOI。"
