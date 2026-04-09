#!/usr/bin/env python3
"""
stoi_config.py — STOI 配置管理
支持交互式 onboard 和配置读写

配置文件：~/.stoi/config.json
"""

import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
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


try:
    import questionary
    _HAS_QUESTIONARY = True
except Exception:
    _HAS_QUESTIONARY = False

_QUESTIONARY_STYLE = questionary.Style([
    ("selected", "fg:#FFB800 bold"),
    ("pointer", "fg:#FFB800 bold"),
    ("question", "fg:white bold"),
    ("answer", "fg:#FFB800 bold"),
]) if _HAS_QUESTIONARY else None


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


def _step_header(step: int, total: int, title: str) -> None:
    console.print()
    console.print(Panel.fit(
        f"[bold #FFB800]Step {step}/{total} — {title}[/bold #FFB800]",
        border_style="#FFB800",
        padding=(0, 2),
    ))


def _qselect(message: str, choices, default=None):
    if _HAS_QUESTIONARY:
        return questionary.select(
            message,
            choices=choices,
            default=default,
            style=_QUESTIONARY_STYLE,
        ).ask()
    # minimal fallback
    console.print(f"[bold white]{message}[/bold white]")
    for i, c in enumerate(choices, 1):
        label = c if isinstance(c, str) else c.value
        console.print(f"  [dim]{i}[/dim]  {label}")
    idx = int(Prompt.ask("请选择", default="1")) - 1
    return choices[idx] if choices else None


def _qconfirm(message: str, default: bool = True):
    if _HAS_QUESTIONARY:
        return questionary.confirm(message, default=default, style=_QUESTIONARY_STYLE).ask()
    return Confirm.ask(message, default=default)


def _qprompt(message: str, default: str = "", password: bool = False):
    if _HAS_QUESTIONARY:
        return questionary.text(message, default=default, style=_QUESTIONARY_STYLE).ask() if not password else Prompt.ask(message, password=True)
    return Prompt.ask(message, default=default, password=password)


def run_onboard() -> None:
    """交互式 onboard 流程"""
    console.print()
    console.print(Panel.fit(
        "[bold #FFB800]STOI — 初始配置[/bold #FFB800]\n"
        "[dim]配置 LLM，用于生成 AI 改进建议[/dim]",
        border_style="#FFB800",
    ))
    console.print()

    cfg = load_config()
    TOTAL_STEPS = 4

    # ── Step 1: 选择 LLM Provider ─────────────────────────────────────────────
    _step_header(1, TOTAL_STEPS, "选择 LLM Provider")

    provider_choices = [
        questionary.Choice("Anthropic Claude  (推荐，与 Claude Code 生态一致)", value="anthropic"),
        questionary.Choice("OpenAI GPT", value="openai"),
        questionary.Choice("通义千问 Qwen", value="qwen"),
        questionary.Choice("DeepSeek", value="deepseek"),
        questionary.Choice("自定义 OpenAI 兼容接口", value="custom"),
    ] if _HAS_QUESTIONARY else [
        "anthropic (推荐，与 Claude Code 生态一致)",
        "openai",
        "qwen",
        "deepseek",
        "custom (自定义 OpenAI 兼容接口)",
    ]

    if _HAS_QUESTIONARY:
        provider = questionary.select(
            "请选择 LLM Provider:",
            choices=provider_choices,
            default=provider_choices[0],
            style=_QUESTIONARY_STYLE,
        ).ask()
    else:
        for i, c in enumerate(provider_choices, 1):
            console.print(f"  [dim]{i}[/dim]  {c}")
        provider_map = {"1": "anthropic", "2": "openai", "3": "qwen", "4": "deepseek", "5": "custom"}
        provider = provider_map[Prompt.ask("请选择", choices=["1","2","3","4","5"], default="1")]

    # ── Step 2: API Key ───────────────────────────────────────────────────────
    _step_header(2, TOTAL_STEPS, "API Key")

    if provider != "custom":
        pinfo = PROVIDER_MODELS[provider]
        env_key = pinfo["env_key"]
        existing = os.environ.get(env_key, "")
        if existing:
            console.print(f"[dim]检测到环境变量 {env_key}，将直接使用[/dim]")
            api_key = existing
        else:
            api_key = _qprompt(f"请输入 {env_key}", password=True)
    else:
        api_key = _qprompt("API Key", password=True)

    # ── Step 3: 选择模型 ──────────────────────────────────────────────────────
    _step_header(3, TOTAL_STEPS, "选择模型")

    if provider != "custom":
        pinfo = PROVIDER_MODELS[provider]
        models = pinfo["models"]
        default_model = pinfo["default"]
        if _HAS_QUESTIONARY:
            model_choices = [
                questionary.Choice(
                    f"{m}  (默认)" if m == default_model else m,
                    value=m,
                )
                for m in models
            ]
            model = questionary.select(
                "请选择模型:",
                choices=model_choices,
                default=next((c for c in model_choices if c.value == default_model), model_choices[0]),
                style=_QUESTIONARY_STYLE,
            ).ask()
        else:
            for i, m in enumerate(models, 1):
                suffix = " [dim](默认)[/dim]" if m == default_model else ""
                console.print(f"  [dim]{i}[/dim]  {m}{suffix}")
            model = models[int(Prompt.ask("请选择", choices=[str(i) for i in range(1, len(models)+1)], default="1")) - 1]
        base_url = pinfo["base_url"]
    else:
        base_url = _qprompt("API Base URL", default="https://api.openai.com/v1")
        model = _qprompt("模型名称", default="gpt-4o")

    # ── Step 4: TTS 配置 ──────────────────────────────────────────────────────
    _step_header(4, TOTAL_STEPS, "语音播报")

    tts_enabled = _qconfirm("启用语音播报（TTS）？", default=True)

    # ── 保存 ──────────────────────────────────────────────────────────────────
    cfg["llm"]["provider"] = provider
    cfg["llm"]["api_key"]  = api_key
    cfg["llm"]["model"]    = model
    cfg["llm"]["base_url"] = base_url
    cfg["tts"]["enabled"]  = tts_enabled
    save_config(cfg)

    console.print()
    # Summary panel
    summary_table = Table(show_header=False, box=box.SIMPLE)
    summary_table.add_column("Key", style="dim", justify="right")
    summary_table.add_column("Value", style="cyan")
    summary_table.add_row("Provider", provider)
    summary_table.add_row("Model", model)
    summary_table.add_row("TTS", "开启" if tts_enabled else "关闭")
    summary_table.add_row("配置文件", str(CONFIG_FILE))

    console.print(Panel(
        summary_table,
        title="[bold green]配置完成！[/bold green]",
        border_style="green",
        padding=(1, 2),
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

    table = Table(show_header=False, box=box.ROUNDED, expand=False)
    table.add_column("Key", style="dim", justify="right", no_wrap=True)
    table.add_column("Value", style="cyan")

    table.add_row("Provider", llm.get("provider", "未配置") or "未配置")
    table.add_row("Model", llm.get("model", "未配置") or "未配置")
    table.add_row("API Key", key_display)
    table.add_row("Base URL", llm.get("base_url", "") or "—")
    table.add_row("TTS", "开启" if cfg.get("tts", {}).get("enabled") else "关闭")
    table.add_row("配置文件", str(CONFIG_FILE))

    console.print(Panel(
        table,
        title="[bold #FFB800]STOI 当前配置[/bold #FFB800]",
        border_style="#FFB800",
        padding=(1, 2),
    ))
