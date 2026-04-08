# 💩 STOI - Shit Token On Investment

> A CLI tool that analyzes Claude Code conversation efficiency with a 💩 Shit Meter and TTS voice announcements!

**[English](#english) | [中文](#中文)**

---

<a name="english"></a>

## 🌐 English

### What is STOI?

STOI (Shit Token On Investment) is a fun but practical CLI tool that analyzes your AI conversations for efficiency. It evaluates how much of your token usage actually delivers value - and humorously calls out the "shit" parts with a 💩 rating system and optional voice alerts.

### ✨ Features

- 💩 **Shit Meter** - Quantify conversation efficiency with our patented (not really) poop scale
- 🎭 **Dramatic TTS** - Voice announcements that escalate based on shit levels
- 📊 **Multi-dimensional Analysis** - Problem-solving, code quality, and information density
- 🤖 **AI-Powered Evaluation** - Uses Qwen-Max for intelligent assessment
- 🗣️ **macOS Voice Integration** - Built-in text-to-speech with personality

### 🎖️ Shit Rating System

| Grade | Emoji | Shit % | Description |
|-------|-------|--------|-------------|
| S | 💎 | < 10% | Diamond - Pristine & efficient |
| A | 🌟 | 10-30% | Excellent - Slightly scented |
| B | 💩 | 30-50% | Good - Minor traces |
| C | 💩💩 | 50-70% | Average - Getting shitty |
| D | 💩💩💩 | 70-90% | Poor - Substantial shit |
| F | 💩💩💩💩💩 | > 90% | Failed - Unprecedented levels |

### 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/stoi.git
cd stoi/stoi-skill

# Install dependencies
pip3 install dashscope

# Set your API key (for AI evaluation)
export DASHSCOPE_API_KEY=your_key_here

# Initialize STOI
python3 stoi.py init
```

### 📖 Usage

```bash
# Analyze a conversation session
python3 stoi.py analyze --session your_session_id

# Dramatic mode with escalating voice alerts
python3 stoi.py analyze --session your_session_id --dramatic

# Test TTS
python3 stoi.py tts --message "Shit mountain detected! Evacuate immediately!"
```

---

**[⬆ Back to Top](#-stoi---shit-token-on-investment) | [中文 →](#中文)**

---

<a name="中文"></a>

## 🌐 中文

### STOI 是什么？

STOI（Shit Token On Investment，屎量投资回报率）是一个有趣但实用的 CLI 工具，用于分析 AI 对话的效率。它评估你的 Token 使用中有多少真正产生了价值 - 并用幽默的 💩 评级系统和可选的语音警报来指出"屎"的部分。

名字灵感来自 ROI（投资回报率），但我们关注的是 Token 效率！

### ✨ 功能特色

- 💩 **屎量计** - 用我们独家的便便刻度来量化对话效率
- 🎭 **戏剧化 TTS** - 根据屎量等级升级的语音播报（屎量过高会警报！）
- 📊 **多维度分析** - 问题解决度、代码质量、信息密度
- 🤖 **AI 驱动评估** - 使用 Qwen-Max 进行智能评估
- 🗣️ **macOS 语音集成** - 内置有个性化的文字转语音

### 🎖️ 屎量评级系统

| 等级 | 表情 | 含屎量 | 说明 |
|------|------|--------|------|
| S | 💎 | < 10% | 钻石级，清新脱俗 |
| A | 🌟 | 10-30% | 优秀，略有味道 |
| B | 💩 | 30-50% | 良好，少量 |
| C | 💩💩 | 50-70% | 一般，开始有屎 |
| D | 💩💩💩 | 70-90% | 较差，屎量可观 |
| F | 💩💩💩💩💩 | > 90% | 失败，史无前例 |

### 🚀 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/stoi.git
cd stoi/stoi-skill

# 安装依赖
pip3 install dashscope

# 设置 API 密钥（用于 AI 评估）
export DASHSCOPE_API_KEY=your_key_here

# 初始化 STOI
python3 stoi.py init
```

### 📖 使用方法

```bash
# 分析一个对话会话
python3 stoi.py analyze --session your_session_id

# 戏剧化模式，带有升级的语音警报
python3 stoi.py analyze --session your_session_id --dramatic

# 测试语音
python3 stoi.py tts --message "检测到屎山！建议立即清理！"
```

### 📊 输出示例

#### 🌸 清新脱俗 (S级)
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

#### 💩💩 屎量可观 (C级)
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

### 🎤 TTS 语音效果

**普通模式**: "分析完成。等级C，开始有屎，建议检查是否有废话。"

**戏剧模式** (`--dramatic`):
> 🗣️ **"警报！检测到屎山！等级C！建议立即清理！"**
> 🗣️ **"纯净度41分，含屎量59%。注意，你的Token正在变成屎！"**

---

**[⬆ 回到顶部](#-stoi---shit-token-on-investment) | [English →](#english)**

---

## 🛠️ Tech Stack / 技术栈

- Python 3.9+
- DashScope API (Qwen-Max for evaluation)
- SQLite (local storage)
- macOS `say` command (TTS)

## 📋 Requirements / 系统要求

- macOS（for TTS / 用于 TTS 功能）
- Python 3.9 or higher / 或更高版本
- DashScope API key / API 密钥

## 🤝 Contributing / 贡献指南

Contributions are welcome! / 欢迎贡献！

1. Fork the repository / Fork 本仓库
2. Create your feature branch / 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. Commit your changes / 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch / 推送到分支 (`git push origin feature/AmazingFeature`)
5. Open a Pull Request / 打开 Pull Request

## 📄 License / 许可证

This project is licensed under the MIT License.
本项目采用 MIT 许可证。

## 🙏 Acknowledgments / 致谢

- Thanks to [DashScope](https://dashscope.aliyun.com/) / 感谢 [DashScope](https://dashscope.aliyun.com/)
- Built with 💩 and ❤️ / 用 💩 和 ❤️ 构建

---

<p align="center">
  💩 <strong>Remember: No shit in code, sunny days ahead!</strong> 💩<br>
  <strong>记住：代码无屎，便是晴天！</strong>
</p>
