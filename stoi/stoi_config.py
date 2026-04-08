#!/usr/bin/env python3
"""
stoi_config.py — STOI 配置管理
支持交互式 onboard 和配置读写

配置文件：~/.stoi/config.json
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

console = Console()

CONFIG_DIR  = Path("~/.stoi").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "version":    "1.0",
    "llm": {
        "provider":  "",       # anthropic | openai | qwen | custom
        "api_key":   "",
        "model":     "",
        "base_url":  "",       # 自定义 endpoint
    },
    "tts": {
        "enabled":  True,
        "voice":    "Ting-Ting",  # macOS say voice
    },
    "analysis": {
        "auto_insights":   False,  # session 结束后自动触发 insights
        "insights_model":  "",     # 可单独配置 insights 用的模型
        "min_turns_for_insights": 5,
    },
    "display": {
        "theme":   "dark",
        "language": "zh",
    }
}

PROVIDER_MODELS = {
    "anthropic": {
        "default": "claude-opus-4-5",
        "models":  ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-3-5"],
        "base_url": "https://api.anthropic.com",
        "env_key":  "ANTHROPIC_API_KEY",
    },
    "openai": {
        "default": "gpt-4o",
        "models":  ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "base_url": "https://api.openai.com/v1",
        "env_key":  "OPENAI_API_KEY",
    },
    "qwen": {
        "default": "qwen-max",
        "models":  ["qwen-max", "qwen-plus", "qwen-turbo"],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key":  "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "default": "deepseek-chat",
        "models":  ["deepseek-chat", "deepseek-reasoner"],
        "base_url": "https://api.deepseek.com/v1",
        "env_key":  "DEEPSEEK_API_KEY",
    },
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        # 合并默认值
        merged = DEFAULT_CONFIG.copy()
        for k, v in data.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            else:
                merged[k] = v
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_api_key(provider: str) -> str:
    """从环境变量或配置文件获取 API key"""
    cfg = load_config()
    # 先看配置文件
    key = cfg.get("llm", {}).get("api_key", "")
    if key:
        return key
    # 再看环境变量
    env_key = PROVIDER_MODELS.get(provider, {}).get("env_key", "")
    if env_key:
        return os.environ.get(env_key, "")
    return ""


def is_configured() -> bool:
    cfg = load_config()
    llm = cfg.get("llm", {})
    return bool(llm.get("provider") and llm.get("api_key"))


def run_onboard() -> None:
    """交互式 onboard 流程"""
    console.print()
    console.print(Panel.fit(
        "[bold #FFB800]💩 STOI — 初始配置[/bold #FFB800]\n"
        "[dim]配置 LLM，用于生成 AI 改进建议[/dim]",
        border_style="#FFB800",
    ))
    console.print()

    cfg = load_config()

    # ── 选择 LLM Provider ──────────────────────────────────────────────────────
    console.print("[bold white]选择 LLM Provider[/bold white]")
    console.print("  [dim]1[/dim]  Anthropic Claude  [dim](推荐，与 Claude Code 生态一致)[/dim]")
    console.print("  [dim]2[/dim]  OpenAI GPT")
    console.print("  [dim]3[/dim]  通义千问 Qwen")
    console.print("  [dim]4[/dim]  DeepSeek")
    console.print("  [dim]5[/dim]  自定义 OpenAI 兼容接口")
    console.print()

    choice = Prompt.ask("请选择", choices=["1", "2", "3", "4", "5"], default="1")
    provider_map = {"1": "anthropic", "2": "openai", "3": "qwen", "4": "deepseek", "5": "custom"}
    provider = provider_map[choice]

    # ── API Key ────────────────────────────────────────────────────────────────
    console.print()
    if provider != "custom":
        pinfo = PROVIDER_MODELS[provider]
        env_key = pinfo["env_key"]
        existing = os.environ.get(env_key, "")
        if existing:
            console.print(f"[dim]检测到环境变量 {env_key}，将直接使用[/dim]")
            api_key = existing
        else:
            console.print(f"[bold white]输入 API Key[/bold white] [dim]({env_key})[/dim]")
            api_key = Prompt.ask("API Key", password=True)
    else:
        api_key = Prompt.ask("[bold white]API Key[/bold white]", password=True)

    # ── 选择模型 ──────────────────────────────────────────────────────────────
    console.print()
    if provider != "custom":
        pinfo = PROVIDER_MODELS[provider]
        models = pinfo["models"]
        console.print("[bold white]选择模型[/bold white]")
        for i, m in enumerate(models, 1):
            suffix = " [dim](默认)[/dim]" if m == pinfo["default"] else ""
            console.print(f"  [dim]{i}[/dim]  {m}{suffix}")
        model_choice = Prompt.ask("请选择", choices=[str(i) for i in range(1, len(models)+1)], default="1")
        model = models[int(model_choice) - 1]
        base_url = pinfo["base_url"]
    else:
        base_url = Prompt.ask("[bold white]API Base URL[/bold white]", default="https://api.openai.com/v1")
        model = Prompt.ask("[bold white]模型名称[/bold white]", default="gpt-4o")

    # ── TTS 配置 ──────────────────────────────────────────────────────────────
    console.print()
    tts_enabled = Confirm.ask("[bold white]启用语音播报（TTS）？[/bold white]", default=True)

    # ── 保存 ──────────────────────────────────────────────────────────────────
    cfg["llm"]["provider"] = provider
    cfg["llm"]["api_key"]  = api_key
    cfg["llm"]["model"]    = model
    cfg["llm"]["base_url"] = base_url
    cfg["tts"]["enabled"]  = tts_enabled
    save_config(cfg)

    console.print()
    console.print(Panel.fit(
        f"[bold green]✅ 配置完成！[/bold green]\n"
        f"  Provider: [cyan]{provider}[/cyan]\n"
        f"  Model:    [cyan]{model}[/cyan]\n"
        f"  TTS:      [cyan]{'开启' if tts_enabled else '关闭'}[/cyan]",
        border_style="green",
    ))
    console.print()
    console.print("现在运行 [bold #FFB800]stoi analyze[/bold #FFB800] 分析你的 session，")
    console.print("然后 [bold #FFB800]stoi insights[/bold #FFB800] 获取 AI 改进建议。")
    console.print()


def show_config() -> None:
    """显示当前配置"""
    cfg = load_config()
    llm = cfg.get("llm", {})
    key = llm.get("api_key", "")
    key_display = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else ("已配置" if key else "未配置")

    console.print(Panel.fit(
        f"[bold #FFB800]STOI 当前配置[/bold #FFB800]\n\n"
        f"  Provider:  [cyan]{llm.get('provider', '未配置')}[/cyan]\n"
        f"  Model:     [cyan]{llm.get('model', '未配置')}[/cyan]\n"
        f"  API Key:   [dim]{key_display}[/dim]\n"
        f"  Base URL:  [dim]{llm.get('base_url', '')}[/dim]\n"
        f"  TTS:       [cyan]{'开启' if cfg.get('tts', {}).get('enabled') else '关闭'}[/cyan]\n"
        f"  配置文件:  [dim]{CONFIG_FILE}[/dim]",
        border_style="#FFB800",
    ))
