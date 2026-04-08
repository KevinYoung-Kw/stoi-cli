#!/usr/bin/env python3
"""
STOI Configuration - Simple like OpenClaw
直接使用环境变量配置 API Keys
"""

import os
from typing import Optional, Dict

# 环境变量映射（类似 OpenClaw）
ENV_MAPPINGS = {
    "dashscope": ["DASHSCOPE_API_KEY"],
    "openai": ["OPENAI_API_KEY", "OPENAI_API_KEYS"],
    "azure": ["AZURE_OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "siliconflow": ["SILICONFLOW_API_KEY"],
}

# 默认配置
DEFAULT_CONFIGS = {
    "dashscope": {
        "name": "DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
    },
}


def get_api_key(provider: str) -> Optional[str]:
    """从环境变量获取 API Key"""
    env_vars = ENV_MAPPINGS.get(provider, [])
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # 支持逗号分隔的多个 key（取第一个）
            return value.split(',')[0].strip()
    return None


def get_available_providers() -> Dict[str, Dict]:
    """获取所有可用的提供商（有环境变量的）"""
    providers = {}
    for provider_id, config in DEFAULT_CONFIGS.items():
        api_key = get_api_key(provider_id)
        if api_key:
            providers[provider_id] = {
                **config,
                "api_key": api_key,
                "provider_id": provider_id,
            }
    return providers


def get_openai_client(provider: Optional[str] = None):
    """
    获取配置好的 OpenAI 客户端
    类似 OpenClaw: 优先使用环境变量
    """
    available = get_available_providers()

    if not available:
        raise ValueError(
            "未找到 API Key。请设置环境变量:\n"
            "  export DASHSCOPE_API_KEY=your_key  # 阿里云\n"
            "  export OPENAI_API_KEY=your_key     # OpenAI\n"
            "  export DEEPSEEK_API_KEY=your_key   # DeepSeek\n"
            "  export SILICONFLOW_API_KEY=your_key # SiliconFlow"
        )

    # 如果指定了提供商，使用指定的
    if provider and provider in available:
        selected = available[provider]
    else:
        # 默认使用第一个可用的
        selected = list(available.values())[0]

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请安装 OpenAI SDK: pip install openai")

    return OpenAI(
        api_key=selected["api_key"],
        base_url=selected["base_url"],
    ), selected["default_model"]


# 兼容旧代码
ConfigManager = None
InteractiveConfig = None
