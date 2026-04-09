
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

### 推荐：一键安装脚本

无需手动 clone，一条命令搞定（自动处理 PATH）：

```bash
curl -fsSL https://raw.githubusercontent.com/KevinYoung-Kw/stoi-cli/main/install.sh | bash
```

脚本会**自动检测** `uv` → `pipx` → `pip`，并优先使用能自动管理 PATH 的工具。安装完成后直接运行 `stoi help`。

### 手动安装（开发推荐）

```bash
git clone https://github.com/KevinYoung-Kw/stoi-cli.git
cd stoi

# 方式 A：uv（推荐，最快，自动管理 PATH）
uv tool install .

# 方式 B：pipx（自动将命令链接到 ~/.local/bin）
pipx install .

# 方式 C：pip 可编辑模式（需要手动确保 PATH 包含 pip 用户脚本目录）
pip install -e .
```

### 安装后验证

```bash
stoi help
```

如果提示 `command not found`，说明 Python 用户脚本目录尚未加入 PATH。请执行：

```bash
# 通用
export PATH="$HOME/.local/bin:$PATH"

# macOS 系统自带 Python（如 3.9）
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
```

建议把对应路径永久写入 `~/.zshrc` 或 `~/.bash_profile`，重开终端即可直接使用 `stoi`。

---

## 🚀 快速开始

### 1. 交互式 REPL（推荐）

```bash
stoi
```

进入一个极简的终端交互环境，使用 `/` 命令操作：

```
❯ /report          # 快速分析当前 session
❯ /insights        # AI 深度建议（需配置 API key）
❯ /sessions        # 切换要分析的 session
❯ /overview        # 查看所有历史 session 的全局报告
❯ /compare         # before/after 效果对比
❯ /blame           # 粘贴 System Prompt，定位缓存失效元凶
❯ /setup           # 一键配置 MCP
❯ /quit            # 退出
```

REPL 右下角会显示 `[green]● MCP[/green]`，表示当前 `stoi` 已支持 Claude Code 直接调用。

### 2. 实时监控代理

```bash
stoi start
```

启动后自动拦截 Claude Code API 请求，实时计算每轮含屎量，数据写入 `~/.stoi/`。

---

## 📊 核心指标解读

| 指标 | 含义 | 健康范围 |
|------|------|----------|
| **含屎量 (STOI)** | 未命中缓存的无效 token 占比 | `< 30%` ✅ |
| **缓存命中率** | KV Cache read / total input | `> 70%` ✅ |
| **有效率** | 未被用户否定的 AI 输出比例 | `> 80%` ✅ |
| **上下文膨胀** | 多轮对话后 input tokens 增长倍数 | `< 300%` ✅ |

---

## ⌨️ CLI 命令速查

| 命令 | 说明 |
|------|------|
| `stoi report` | 分析最新 session |
| `stoi report --llm` | 开启 AI 深度建议 |
| `stoi report --html` | 生成 HTML 报告并自动打开 |
| `stoi report --all` | 汇总最近所有 session |
| `stoi start` | 启动实时监控代理 |
| `stoi config` | 配置 LLM Provider |
| `stoi help` | 查看完整帮助 |

---

## 🏗️ 架构与海报

<p align="center">
  <img src="assets/images/poster.jpg" width="700" alt="STOI Poster">
</p>

---

## 🔌 MCP 配置（可选）

`stoi` 支持**双模态运行**：终端里它是 REPL，被 Claude Code 启动时自动变成 MCP Server。

一键注册：

```bash
claude mcp add stoi stoi
```

> 如果环境找不到 `stoi`，可用 `claude mcp add stoi -- python3 -m stoi`
>
> 也可以直接在 REPL 中输入 `/setup`，它会自动帮你完成配置。

注册成功后，在 Claude Code 里直接说：

> "分析本次会话的 token 效率"
>
> "我的含屎量怎么样？"

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
