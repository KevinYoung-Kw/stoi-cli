# 💩 STOI Skill - Shit Token On Investment

一个让 Claude Code 能分析自己 Token 效率的 CLI 工具，带 💩 屎量评级和 TTS 语音播报！

## 💩 功能特色

- **CLI 命令**: `stoi analyze` - 分析当前会话的 💩 屎量
- **Web 界面**: `stoi gui` - 苹果风格网页界面
- **戏剧播报**: `stoi analyze --dramatic` - 语音播报（屎量过高会警报！）
- **TTS 测试**: `stoi tts "message"` - 测试 TTS 播报

## 🎭 屎量评级系统

| 等级 | 表情 | 含屎量 | 说明 |
|------|------|--------|------|
| S | 💎 | < 10% | 钻石级，清新脱俗 |
| A | 🌟 | 10-30% | 优秀，略有味道 |
| B | 💩 | 30-50% | 良好，少量 |
| C | 💩💩 | 50-70% | 一般，开始有屎 |
| D | 💩💩💩 | 70-90% | 较差，屎量可观 |
| F | 💩💩💩💩💩 | > 90% | 失败，史无前例 |

## 🚀 安装

```bash
# 1. 进入目录
cd stoi-skill

# 2. 安装依赖
pip3 install openai rich questionary

# 安装 Web GUI 依赖（可选）
pip3 install flask  # Apple Design Web 界面

# 3. 设置环境变量或配置
export DASHSCOPE_API_KEY=your_key_here
# 或运行交互式配置
python3 stoi.py config

# 4. 初始化
python3 stoi.py init
```

## 💩 使用示例

```bash
# 分析刚才的对话
python3 stoi.py analyze --session your_session_id

# 戏剧化播报（屎量高时会"警报"！）
python3 stoi.py analyze --session your_session_id --dramatic

# 测试语音
python3 stoi.py tts --message "检测到屎山！建议立即清理！"
```

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

## 🎤 TTS 语音效果

**普通模式**: "分析完成。等级C，开始有屎，建议检查是否有废话。"

**戏剧模式** (--dramatic):
> 🗣️ **"警报！检测到屎山！等级C！建议立即清理！"**
> 🗣️ **"纯净度41分，含屎量59%。注意，你的Token正在变成屎！"**

## 🎨 GUI/TUI 界面

### TUI 终端界面（Apple Design）

苹果风格的终端图形界面：

```bash
# 启动 TUI
python3 stoi.py gui --mode tui
# 或
python3 stoi_tui.py
```

**特点：**
- 键盘快捷键 (q-退出, r-刷新, a-分析, s-播报)
- 左侧会话列表，右侧分析面板
- 实时显示等级卡片、维度评分、AI 评价
- 支持多来源切换（Claude、Kimi、OpenAI）

### Web 界面（Apple Design）

简约、现代、优雅的苹果风格 Web 界面：

```bash
# 启动 Web GUI
python3 stoi.py gui --mode web
# 或
python3 stoi_gui.py
```

然后打开 http://127.0.0.1:5000

**设计特点：**
- 🎨 **苹果风格** - 简约、克制、优雅
- 💎 **玻璃态设计** - backdrop-filter 毛玻璃效果
- 🌈 **渐变等级卡** - S/A/B/C/D/F 等级使用不同渐变色
- 📊 **数据可视化** - 进度条、统计卡片、维度分析
- 📱 **响应式布局** - 适配各种屏幕尺寸

## 📥 会话来源

支持从以下 AI 工具导入会话：

| 来源 | 状态 | 说明 |
|------|------|------|
| Claude Code | ✅ 自动 | 读取 `~/.claude/history.jsonl` |
| Kimi | 📝 手动 | 需要导出 JSON 文件 |
| OpenAI | 📝 手动 | 需要导出或使用 API |

## 🔧 技术栈

- Python 3.9+
- OpenAI SDK（多提供商支持）
- Textual（TUI 界面）
- Flask（Web 界面）
- SQLite（本地存储）
- macOS `say` 命令 (TTS)

## 📝 TODO

- [ ] `stoi blame` - 找出 Token 刺客
- [ ] `stoi stats` - 历史屎量统计
- [ ] 更多语音特效
- [ ] 屎量趋势图

---

💩 **记住：代码无屎，便是晴天！**
