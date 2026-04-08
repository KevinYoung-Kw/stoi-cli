# 💩 STOI - Shit Token On Investment

> 一个让 Claude Code 能分析自己 Token 效率的 CLI 工具，带 💩 屎量评级和 TTS 语音播报！
> 参考 OpenClaw 配置系统设计，支持多模型提供商，统一使用 OpenAI 兼容协议。

---

## 💩 STOI 是什么？

STOI（Shit Token On Investment，屎量投资回报率）是一个有趣但实用的 CLI 工具，用于分析 AI 对话的效率。它评估你的 Token 使用中有多少真正产生了价值 - 并用幽默的 💩 评级系统和可选的语音警报来指出"屎"的部分。

名字灵感来自 ROI（投资回报率），但我们关注的是 Token 效率！

---

## ✨ 功能特色

- 💩 **屎量计** - 用我们独家的便便刻度来量化对话效率
- 🎭 **戏剧化 TTS** - 根据屎量等级升级的语音播报（屎量过高会警报！）
- 📊 **多维度分析** - 问题解决度、代码质量、信息密度
- 🤖 **AI 驱动评估** - 支持多模型提供商（OpenAI、阿里云、DeepSeek等）
- ⚙️ **灵活配置** - 参考 OpenClaw 设计的交互式配置面板
- 🔌 **OpenAI 兼容** - 统一协议访问所有提供商
- 🗣️ **macOS 语音集成** - 内置有个性化的文字转语音

---

## 🎖️ 屎量评级系统

| 等级 | 表情 | 含屎量 | 说明 |
|------|------|--------|------|
| S | 💎 | < 10% | 钻石级，清新脱俗 |
| A | 🌟 | 10-30% | 优秀，略有味道 |
| B | 💩 | 30-50% | 良好，少量 |
| C | 💩💩 | 50-70% | 一般，开始有屎 |
| D | 💩💩💩 | 70-90% | 较差，屎量可观 |
| F | 💩💩💩💩💩 | > 90% | 失败，史无前例 |

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/stoi.git
cd stoi/stoi-skill

# 安装依赖
pip3 install openai rich questionary

# 配置模型提供商（支持上下键导航的交互式菜单）
python3 stoi.py config

# 或使用环境变量
export DASHSCOPE_API_KEY=your_key_here

# 初始化 STOI
python3 stoi.py init
```

### 使用方法

```bash
# 打开配置面板（OpenClaw 风格）
python3 stoi.py config

# 使用默认提供商分析
python3 stoi.py analyze --session your_session_id

# 指定提供商
python3 stoi.py analyze --session your_session_id --provider openai

# 指定模型
python3 stoi.py analyze --session your_session_id --model gpt-4-turbo

# 戏剧化模式，带有升级的语音警报
python3 stoi.py analyze --session your_session_id --dramatic

# 测试语音
python3 stoi.py tts --message "检测到屎山！建议立即清理！"
```

---

## ⚙️ 配置系统

STOI 参考 [OpenClaw](https://docs.openclaw.ai/) 的配置系统设计：

### 交互式配置面板

```bash
stoi config
```

功能：
- 查看所有已配置的提供商
- 添加/编辑提供商 API Key
- 设置默认模型
- 添加自定义提供商
- 配置 TTS 和 UI 选项

### 配置文件

位置：`~/.stoi/config.json`

```json
{
  "version": "1.0.0",
  "active_provider": "dashscope",
  "providers": {
    "dashscope": {
      "name": "阿里云 DashScope",
      "provider_id": "dashscope",
      "api_key": "sk-xxxxx",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "default_model": "qwen-max",
      "enabled": true
    }
  }
}
```

### 环境变量

所有提供商都支持通过环境变量配置：

```bash
export DASHSCOPE_API_KEY=sk-xxxxx      # 阿里云
export OPENAI_API_KEY=sk-xxxxx          # OpenAI
export AZURE_OPENAI_API_KEY=xxxxx       # Azure
export ANTHROPIC_API_KEY=sk-ant-xxxxx   # Anthropic
export DEEPSEEK_API_KEY=sk-xxxxx        # DeepSeek
export SILICONFLOW_API_KEY=sk-xxxxx     # SiliconFlow
```

---

## 🔌 支持的模型提供商

| 提供商 | 标识符 | Base URL | 默认模型 |
|--------|--------|----------|----------|
| 阿里云 DashScope | `dashscope` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| OpenAI | `openai` | `https://api.openai.com/v1` | `gpt-4` |
| Azure OpenAI | `azure` | 自定义 | `gpt-4` |
| Anthropic | `anthropic` | `https://api.anthropic.com/v1` | `claude-3-opus-20240229` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` |
| SiliconFlow | `siliconflow` | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| 自定义 | `custom` | 自定义 | 自定义 |

**为什么使用 OpenAI 协议？**

OpenAI 的 API 协议已成为事实标准。大多数模型提供商都提供兼容的接口，这样只需安装一个 `openai` SDK，通过不同的 `base_url` 即可访问所有提供商。

---

## 📊 输出示例

### 🌸 清新脱俗 (S级)

```
==================================================
💩 STOI 屎量分析报告
==================================================

【💩 屎量指数】
  纯净度: 95.0/100 (越高越好)
  等级: 💎 (S)
  含屎量: 5.0%
  屎量评级: 🌸 清新脱俗

【💩 维度分析】
  问题解决度: 💎💎💎💎💎 (5/5)
  代码质量: 💎💎💎💎💩 (4/5)
  信息密度: 💎💎💎💎💎 (5/5)

【🤖 AI屎评】
  太棒了！你的代码清新脱俗！

【💎 建议】
  继续保持！
```

### 💩💩 屎量可观 (C级)

```
==================================================
💩 STOI 屎量分析报告
==================================================

【💩 屎量指数】
  纯净度: 41.0/100 (越高越好)
  等级: 💩💩 (C)
  含屎量: 59.0%
  屎量评级: 💩💩 屎量可观

【💩 维度分析】
  问题解决度: 💎💎💩💩💩 (2/5)
  信息密度: 💎💩💩💩💩 (1/5)

【🤖 AI屎评】
  回复冗长且缺乏实质性内容

【💩 建议】
  开始有屎了！建议检查是否有废话。
```

---

## 🎤 TTS 语音效果

**普通模式**: "分析完成。等级C，开始有屎，建议检查是否有废话。"

**戏剧模式** (`--dramatic`):
> 🗣️ **"警报！检测到屎山！等级C！建议立即清理！"**
> 🗣️ **"纯净度41分，含屎量59%。注意，你的Token正在变成屎！"**

---

## 🛠️ 技术栈

- Python 3.9+
- OpenAI SDK（统一接口访问所有提供商）
- SQLite（本地存储）
- macOS `say` 命令（TTS）

---

## 📋 系统要求

- macOS（用于 TTS 功能）
- Python 3.9 或更高版本
- 任一支持提供商的 API 密钥

---

## 🤝 贡献指南

欢迎贡献！请随时提交 Pull Request。

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详情请查看 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- 感谢 [DashScope](https://dashscope.aliyun.com/) 提供 Qwen-Max API
- 感谢 [OpenClaw](https://docs.openclaw.ai/) 的配置系统灵感
- 灵感来自优化 AI 对话效率的需求
- 用 💩 和 ❤️ 构建

---

<p align="center">
  💩 <strong>记住：代码无屎，便是晴天！</strong> 💩
</p>
