# 🔧 STOI 配置系统

> 参考 OpenClaw 配置系统设计的模型提供商配置面板
> 支持多提供商，统一使用 OpenAI 兼容协议

---

## 快速开始

### 1. 交互式配置（推荐）

```bash
stoi config
```

这会打开**支持上下键导航**的交互式配置面板，你可以：
- 使用 ↑↓ 键选择菜单项
- 按 Enter 确认选择
- 查看已配置的提供商
- 配置 API Key
- 设置默认模型
- 添加自定义提供商

**菜单预览：**
```
💩 STOI 配置面板
参考 OpenClaw 配置系统设计 | 支持上下键导航

请选择操作 (使用 ↑↓ 键导航，Enter 确认):
────────────────────────────────────────
● 配置 阿里云 DashScope (当前默认) [Key: ✓]
○ 配置 OpenAI [Key: ✗]
○ 配置 DeepSeek [Key: ✓]
────────────────────────────────────────
➕ 添加自定义提供商
🎤 配置 TTS 设置
🎨 配置 UI 模式
────────────────────────────────────────
💾 保存并退出
❌ 放弃并退出
```

### 2. 环境变量配置

```bash
# DashScope（阿里云）
export DASHSCOPE_API_KEY=sk-xxxxx

# OpenAI
export OPENAI_API_KEY=sk-xxxxx

# Azure OpenAI
export AZURE_OPENAI_API_KEY=your_key

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# DeepSeek
export DEEPSEEK_API_KEY=sk-xxxxx

# SiliconFlow
export SILICONFLOW_API_KEY=sk-xxxxx
```

### 3. 配置文件位置

```
~/.stoi/config.json
```

---

## 支持的提供商

| 提供商 | 标识符 | Base URL | 默认模型 |
|--------|--------|----------|----------|
| 阿里云 DashScope | `dashscope` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| OpenAI | `openai` | `https://api.openai.com/v1` | `gpt-4` |
| Azure OpenAI | `azure` | 需自定义 | `gpt-4` |
| Anthropic | `anthropic` | `https://api.anthropic.com/v1` | `claude-3-opus-20240229` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` |
| SiliconFlow | `siliconflow` | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| 自定义 | `custom` | 自定义 | 自定义 |

---

## CLI 使用

### 使用默认配置分析

```bash
stoi analyze <session_id>
```

### 指定提供商

```bash
stoi analyze <session_id> --provider openai
```

### 指定具体模型

```bash
stoi analyze <session_id> --model gpt-4-turbo
```

### 查看当前配置

```bash
stoi init
```

---

## 配置文件示例

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
      "available_models": ["qwen-max", "qwen-plus", "qwen-turbo"],
      "enabled": true,
      "timeout": 60,
      "max_retries": 3
    },
    "openai": {
      "name": "OpenAI",
      "provider_id": "openai",
      "api_key": "sk-xxxxx",
      "base_url": "https://api.openai.com/v1",
      "default_model": "gpt-4",
      "available_models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
      "enabled": true
    }
  },
  "tts_enabled": true,
  "tts_voice": "default",
  "ui_mode": "auto"
}
```

---

## 添加自定义提供商

任何支持 OpenAI 兼容协议的 API 都可以添加：

```bash
stoi config
# 选择 [a] 添加自定义提供商
```

需要填写：
- 显示名称
- 唯一标识符
- Base URL（OpenAI 兼容端点）
- API Key
- 默认模型

---

## 为什么使用 OpenAI 协议？

OpenAI 的 API 协议已成为事实标准。大多数模型提供商都提供兼容的接口：

- **DashScope**: `/compatible-mode/v1`
- **DeepSeek**: `/v1`
- **SiliconFlow**: `/v1`
- **Azure**: OpenAI API 兼容
- **Anthropic**: 支持 OpenAI 兼容层

这样只需安装一个 `openai` SDK，通过不同的 `base_url` 即可访问所有提供商。

---

## 故障排除

### 错误：未配置有效的模型提供商

```
运行: stoi config
或设置环境变量: export DASHSCOPE_API_KEY=your_key
```

### 错误：连接超时

```python
# 在 config.json 中调整超时设置
{
  "providers": {
    "xxx": {
      "timeout": 120,  # 增加到 120 秒
      "max_retries": 5
    }
  }
}
```

### 切换提供商不生效

```bash
# 确认配置已保存
stoi config
# 或手动编辑 ~/.stoi/config.json
```

---

## 参考

- [OpenClaw 配置系统](https://docs.openclaw.ai/gateway/configuration)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [DashScope 兼容模式](https://dashscope.aliyun.com/)
