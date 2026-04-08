# 💩 STOI - Shit Token On Investment

> 开发者侧首个基于 CLI 形态的「词元 (Token) 投资回报率」分析工具

## 简介

STOI 是一款衡量 AI 编程工具 Token 消耗转化率的效率产品。它通过监控底层 Token 消耗，结合 LLM-as-a-judge 机制，为开发者量化 **"有效代码输出 (Value)"** 与 **"无效/冗余消耗 (Shit)"** 的比例，最终给出一个直观的 **「含屎量」** 评级。

## 核心功能

| 命令 | 功能 |
|------|------|
| `stoi start` | 启动 Token 拦截代理 |
| `stoi analyze` | 分析单次对话的含屎量 |
| `stoi stats` | 查看统计信息 |
| `stoi blame` | 定位 Token 刺客 |
| `stoi trend` | 查看趋势分析 |
| `stoi tui` | 启动 TUI 图形界面 |

## 屎量评级

| 等级 | 含屎量 | 说明 |
|------|--------|------|
| 💎 S | < 10% | 钻石级，清新脱俗 |
| 🌟 A | 10-30% | 优秀，略有味道 |
| 💩 B | 30-50% | 良好，少量 |
| 💩💩 C | 50-70% | 一般，开始有屎 |
| 💩💩💩 D | 70-90% | 较差，屎量可观 |
| 💩💩💩💩💩 F | > 90% | 失败，史无前例 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key
export DASHSCOPE_API_KEY=your_key

# 启动代理
python stoi.py start

# 分析含屎量
python stoi.py analyze

# 启动 TUI
python stoi.py tui
```

## 工作原理

1. **拦截层** - 通过本地代理拦截 Claude Code 的 API 请求
2. **分析层** - 使用 LLM-as-judge 评估对话质量
3. **评分层** - 计算含屎量指数，给出改进建议

## 文件结构

```
STOI-Demo-cola/
├── stoi.py          # 主程序入口
├── stoi_engine.py   # 核心分析引擎
├── stoi_analyze.py  # 分析模块
├── stoi_proxy.py    # Token 拦截代理
├── stoi_tui.py      # TUI 界面
└── requirements.txt # 依赖
```

## 技术栈

- Python 3.9+
- OpenAI SDK
- Textual (TUI)
- SQLite

## License

MIT

---

💩 **代码无屎，便是晴天！**
