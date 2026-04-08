#!/usr/bin/env python3
"""
STOI Configuration - Simple like OpenClaw
直接读取环境变量，支持交互式配置
"""

import os
import sys
from typing import Optional, Dict

# 提供商配置
PROVIDERS = {
    # 国内主流
    "dashscope": {
        "name": "阿里云 DashScope",
        "env_var": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
    },
    "zhipu": {
        "name": "智谱 AI (GLM)",
        "env_var": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4",
    },
    "baidu": {
        "name": "百度千帆",
        "env_var": "BAIDU_API_KEY",
        "base_url": "https://qianfan.baidubce.com/v2",
        "model": "ernie-bot-4",
    },
    "minimax": {
        "name": "MiniMax",
        "env_var": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.chat/v1",
        "model": "abab6.5s-chat",
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "env_var": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    # 国际主流
    "openai": {
        "name": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-opus-20240229",
    },
    "gemini": {
        "name": "Google Gemini",
        "env_var": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-pro",
    },
    "azure": {
        "name": "Azure OpenAI",
        "env_var": "AZURE_OPENAI_API_KEY",
        "base_url": "",  # 需要用户自定义
        "model": "gpt-4",
    },
    # 聚合平台
    "deepseek": {
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "env_var": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-72B-Instruct",
    },
    "volcengine": {
        "name": "火山引擎",
        "env_var": "VOLCENGINE_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-4k",
    },
}


def get_api_key(provider: str) -> Optional[str]:
    """从环境变量获取 API Key"""
    if provider not in PROVIDERS:
        return None
    return os.getenv(PROVIDERS[provider]["env_var"])


def get_available_providers() -> Dict[str, Dict]:
    """获取所有可用的提供商"""
    available = {}
    for pid, config in PROVIDERS.items():
        api_key = get_api_key(pid)
        if api_key:
            available[pid] = {**config, "api_key": api_key}
    return available


def interactive_setup():
    """交互式配置（OpenClaw 风格）"""
    print("\n💩 STOI 配置")
    print("=" * 40)
    print("\n选择模型提供商:\n")

    providers_list = list(PROVIDERS.items())
    for i, (pid, config) in enumerate(providers_list, 1):
        env_value = os.getenv(config["env_var"])
        status = "✓" if env_value else " "
        print(f"  [{status}] {i}. {config['name']}")

    print("\n  [ ] 0. 跳过配置\n")

    try:
        choice = input("请输入数字 (0-4): ").strip()
        if choice == "0":
            print("\n跳过配置。可以稍后设置环境变量。")
            return

        idx = int(choice) - 1
        if 0 <= idx < len(providers_list):
            pid, config = providers_list[idx]
            print(f"\n已选择: {config['name']}")
            print(f"请设置环境变量:\n")
            print(f"  export {config['env_var']}=your_api_key")
            print(f"\n然后重新运行 stoi init 检查配置。")
    except (ValueError, IndexError):
        print("\n无效选择，跳过配置。")


def get_openai_client(provider: Optional[str] = None):
    """获取 OpenAI 客户端"""
    available = get_available_providers()

    if not available:
        raise ValueError(
            "未配置 API Key。请设置环境变量:\n"
            "  export DASHSCOPE_API_KEY=sk-xxxxx  # 阿里云\n"
            "  export OPENAI_API_KEY=sk-xxxxx     # OpenAI\n"
            "\n或运行: stoi config"
        )

    # 使用指定的或第一个可用的
    if provider and provider in available:
        selected = available[provider]
    else:
        selected = list(available.values())[0]

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请安装 OpenAI SDK: pip install openai")

    return OpenAI(
        api_key=selected["api_key"],
        base_url=selected["base_url"],
    ), selected["model"]


# 兼容旧代码
ConfigManager = None
InteractiveConfig = None
