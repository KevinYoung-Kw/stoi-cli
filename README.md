
![STOI Banner](assets/images/banner.jpg)

# 💩 STOI — Shit Token On Investment

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)

**量化 AI 编程工具的 Token 效率，定位浪费根因。**

STOI 是一款专为 [Claude Code](https://code.claude.com) 及兼容工具设计的**终端级 Token 效率分析仪**。它通过三层指标体系（KV Cache / 输出有效性 / 成本拆解），帮你回答一个核心问题：

> **我花在 AI 上的 token，到底有多少被浪费了？**

<p align="center">
  <img src="assets/images/logo.png" width="120" alt="STOI Logo">
</p>

---

## ✨ 核心特性

- **🧪 三层分析模型**
  - **L1 Cache 效率**：量化 KV Cache 命中率，识别"含屎量"（无效 token 占比）
  - **L2 输出有效性**：基于真实对话反馈，判断 AI 输出是否被用户否定
  - **L3 成本拆解**：按 Anthropic 官方定价精确换算每一笔对话的真实花费

- **🔌 多源兼容**
  - 原生支持 **Claude Code** 会话 JSONL
  - 支持 **OpenCode** SQLite 数据库
  - 支持 **STOI Proxy** 实时监控日志

- **🤖 AI 深度建议（ReAct）**
  - LLM 按需查询内置知识库（Prompt Caching、Context Engineering、Claude Code Skills）
  - 给出可落地的操作指令，而非泛泛而谈

- **🖥️ 交互式 REPL + 实时监控**
  - `/report`、`/insights`、`/compare`、`/blame` 等命令
  - `/compact` 建议、System Prompt 审计、Session 拆分指导

- **🔧 MCP 服务器**
  - Claude Code 可直接调用 STOI 检查自己的 session 效率

---

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/KevinYoung-Kw/stoi.git
cd stoi

# 安装到当前环境（可编辑模式，开发推荐）
pip install -e .

# 或标准安装
pip install .
```

安装完成后，全局可用命令：

```bash
stoi help
```

---

## 🚀 快速开始

### 1. 分析最新的 session

```bash
stoi report
```

输出示例：

```
💩 STOI 分析报告
────────────────────────────────────────
会话: claude-code-project/abc123
含屎量: 34.5% (🟡 MILD_SHIT)
缓存命中: 62.3%
有效率: 78.9%
实际花费: $0.1245
────────────────────────────────────────
```

### 2. 开启 AI 深度建议

```bash
stoi report --llm
```

STOI 会调用 LLM 查询内部知识库，生成如：
- "System Prompt 中存在时间戳注入，建议移至 user message"
- "Session 已达 18 轮，建议使用 `/compact` 压缩历史"

### 3. 交互式 REPL

```bash
stoi
```

在 REPL 中使用 `/` 命令：

```
❯ /report          # 快速分析
❯ /insights        # AI 深度建议
❯ /compare         # before/after 对比
❯ /blame           # 粘贴 System Prompt，定位缓存失效元凶
❯ /quit            # 退出
```

### 4. 实时监控代理

```bash
stoi start
```

自动拦截 Claude Code API 请求，实时计算每轮含屎量，数据写入 `~/.stoi/`。

---

## 📊 核心指标解读

| 指标 | 含义 | 健康范围 |
|------|------|----------|
| **含屎量 (STOI)** | 未命中缓存的无效 token 占比 | `< 30%` ✅ |
| **缓存命中率** | KV Cache read / total input | `> 70%` ✅ |
| **有效率** | 未被用户否定的 AI 输出比例 | `> 80%` ✅ |
| **上下文膨胀** | 多轮对话后 input tokens 增长倍数 | `< 300%` ✅ |

---

## 🏗️ 架构与海报

<p align="center">
  <img src="assets/images/poster.jpg" width="700" alt="STOI Poster">
</p>

---

## 🔌 MCP 配置（可选）

让 Claude Code 直接调用 STOI 分析自己：

```bash
stoi setup   # 或在 REPL 中输入 /setup
```

按提示将 `stoi_mcp` 添加到 Claude Code 的 MCP 服务器列表中，即可在对话里直接说：

> "分析本次会话的 token 效率"

---

## 📁 项目结构

```
stoi/
├── stoi/                    # 主包
│   ├── stoi.py              # CLI 入口
│   ├── stoi_core.py         # 核心分析引擎（L1/L2/L3）
│   ├── stoi_advisor.py      # ReAct LLM 建议引擎
│   ├── stoi_repl.py         # 交互式 REPL
│   ├── stoi_report.py       # CLI / HTML 渲染
│   ├── stoi_proxy.py        # 实时监控代理
│   ├── stoi_mcp.py          # MCP 服务器
│   ├── stoi_output_analysis.py  # 输出质量分析
│   ├── stoi_tavily.py       # 知识库维护工具（Tavily 搜索）
│   └── stoi_knowledge/      # Token 效率知识库
│       ├── claude_code_skills.md
│       ├── kv_cache.md
│       ├── context_engineering.md
│       ├── prompt_design.md
│       └── thinking_tokens.md
├── assets/                  # 品牌素材
├── pyproject.toml           # 现代 Python 包配置
└── README.md
```

---

## 📝 相关知识库来源

本工具内置知识库基于以下官方文档与学术研究维护：

- [Anthropic Prompt Caching Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- Liu et al. (2023) *Lost in the Middle* (TACL)
- Microsoft LLMLingua / LongLLMLingua (EMNLP 2023 / ACL 2024)

---

## ⚠️ 已知限制

- 当前针对 **Claude Code** 的 session 格式做了最佳适配，其他工具的支持可能不完整。
- LLM 深度建议需要配置 API Key（支持 Anthropic / OpenAI / 阿里云 Qwen / DeepSeek）。

---

## 📄 License

[MIT](LICENSE)

---

<p align="center">
  <sub>Built with 💩 for cleaner tokens.</sub>
</p>
