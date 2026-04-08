#!/usr/bin/env python3
"""
STOI Configuration Manager
参考 OpenClaw 配置系统设计的模型提供商配置面板
支持多提供商，统一使用 OpenAI 协议
提供友好的交互式菜单（支持上下键导航）
"""

import os
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

# 尝试导入 questionary 用于友好的交互式菜单
try:
    import questionary
    from questionary import Style
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False

# 尝试导入 Rich
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class ModelProvider:
    """模型提供商配置"""
    name: str
    provider_id: str
    api_key: str
    base_url: str
    default_model: str
    available_models: List[str]
    enabled: bool = True
    timeout: int = 60
    max_retries: int = 3


@dataclass
class STOIConfig:
    """STOI 全局配置"""
    version: str = "1.0.0"
    active_provider: str = "dashscope"
    providers: Dict[str, ModelProvider] = None
    tts_enabled: bool = True
    tts_voice: str = "default"
    ui_mode: str = "auto"

    def __post_init__(self):
        if self.providers is None:
            self.providers = {}


class ConfigManager:
    """配置管理器"""

    CONFIG_DIR = Path.home() / ".stoi"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    ENV_MAPPINGS = {
        "dashscope": ["DASHSCOPE_API_KEY"],
        "openai": ["OPENAI_API_KEY", "OPENAI_API_KEYS"],
        "azure": ["AZURE_OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "siliconflow": ["SILICONFLOW_API_KEY"],
    }

    PRESET_PROVIDERS = {
        "dashscope": {
            "name": "阿里云 DashScope",
            "provider_id": "dashscope",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-max",
            "available_models": [
                "qwen-max",
                "qwen-max-latest",
                "qwen-plus",
                "qwen-turbo",
                "qwen-coder-plus",
            ],
        },
        "openai": {
            "name": "OpenAI",
            "provider_id": "openai",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4",
            "available_models": [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        },
        "azure": {
            "name": "Azure OpenAI",
            "provider_id": "azure",
            "base_url": "",
            "default_model": "gpt-4",
            "available_models": [
                "gpt-4",
                "gpt-35-turbo",
            ],
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "provider_id": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-opus-20240229",
            "available_models": [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
        },
        "deepseek": {
            "name": "DeepSeek",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "available_models": [
                "deepseek-chat",
                "deepseek-coder",
            ],
        },
        "siliconflow": {
            "name": "SiliconFlow",
            "provider_id": "siliconflow",
            "base_url": "https://api.siliconflow.cn/v1",
            "default_model": "Qwen/Qwen2.5-72B-Instruct",
            "available_models": [
                "Qwen/Qwen2.5-72B-Instruct",
                "deepseek-ai/DeepSeek-V3",
                "deepseek-ai/DeepSeek-R1",
                "meta-llama/Meta-Llama-3.1-70B-Instruct",
            ],
        },
        "custom": {
            "name": "自定义提供商",
            "provider_id": "custom",
            "base_url": "",
            "default_model": "",
            "available_models": [],
        },
    }

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> STOIConfig:
        """加载配置"""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                providers = {}
                for pid, pdata in data.get("providers", {}).items():
                    providers[pid] = ModelProvider(**pdata)

                return STOIConfig(
                    version=data.get("version", "1.0.0"),
                    active_provider=data.get("active_provider", "dashscope"),
                    providers=providers,
                    tts_enabled=data.get("tts_enabled", True),
                    tts_voice=data.get("tts_voice", "default"),
                    ui_mode=data.get("ui_mode", "auto"),
                )
            except Exception as e:
                print(f"⚠️ 配置文件加载失败: {e}，使用默认配置")

        return self._create_default_config()

    def _create_default_config(self) -> STOIConfig:
        """创建默认配置"""
        config = STOIConfig()

        for pid, preset in self.PRESET_PROVIDERS.items():
            api_key = self._get_api_key_from_env(pid)
            if api_key or pid == "custom":
                config.providers[pid] = ModelProvider(
                    name=preset["name"],
                    provider_id=pid,
                    api_key=api_key or "",
                    base_url=preset["base_url"],
                    default_model=preset["default_model"],
                    available_models=preset["available_models"],
                    enabled=bool(api_key),
                )

        return config

    def _get_api_key_from_env(self, provider_id: str) -> Optional[str]:
        """从环境变量获取 API Key"""
        env_vars = self.ENV_MAPPINGS.get(provider_id, [])
        for var in env_vars:
            value = os.getenv(var)
            if value:
                return value.split(',')[0].strip()
        return None

    def save(self):
        """保存配置"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.config.version,
            "active_provider": self.config.active_provider,
            "providers": {
                pid: asdict(p) for pid, p in self.config.providers.items()
            },
            "tts_enabled": self.config.tts_enabled,
            "tts_voice": self.config.tts_voice,
            "ui_mode": self.config.ui_mode,
        }

        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_active_provider(self) -> Optional[ModelProvider]:
        """获取当前启用的提供商"""
        return self.config.providers.get(self.config.active_provider)

    def set_active_provider(self, provider_id: str) -> bool:
        """设置当前提供商"""
        if provider_id not in self.config.providers:
            return False
        self.config.active_provider = provider_id
        self.save()
        return True

    def add_provider(self, provider: ModelProvider):
        """添加/更新提供商"""
        self.config.providers[provider.provider_id] = provider
        self.save()

    def list_providers(self) -> List[Dict]:
        """列出所有提供商"""
        return [
            {
                "id": pid,
                "name": p.name,
                "enabled": p.enabled,
                "has_key": bool(p.api_key),
                "is_active": pid == self.config.active_provider,
                "model": p.default_model,
            }
            for pid, p in self.config.providers.items()
        ]


class InteractiveConfig:
    """交互式配置面板 - 支持上下键导航"""

    # 自定义样式（仅在 questionary 可用时使用）
    CUSTOM_STYLE = None
    if QUESTIONARY_AVAILABLE:
        CUSTOM_STYLE = Style([
            ('qmark', 'fg:#5BBF5B bold'),
            ('question', 'fg:#F9F9F9 bold'),
            ('answer', 'fg:#5BBF5B bold'),
            ('pointer', 'fg:#5BBF5B bold'),      # 选中项的指针
            ('highlighted', 'fg:#5BBF5B bold'),  # 高亮项
            ('selected', 'fg:#5BBF5B bold'),     # 已选项
            ('separator', 'fg:#666666'),
            ('instruction', 'fg:#666666'),
        ])

    def __init__(self, manager: ConfigManager):
        self.manager = manager
        self.console = Console() if RICH_AVAILABLE else None

    def clear_screen(self):
        """清屏"""
        os.system('clear' if os.name == 'posix' else 'cls')

    def print_header(self):
        """打印标题"""
        if self.console:
            self.console.print(Panel.fit(
                "[bold cyan]💩 STOI 配置面板[/bold cyan]\n"
                "[dim]参考 OpenClaw 配置系统设计 | 支持上下键导航[/dim]",
                border_style="cyan"
            ))
        else:
            print("\n💩 STOI 配置面板")
            print("参考 OpenClaw 配置系统设计")
            print("-" * 40)

    def print_provider_table(self):
        """打印提供商表格"""
        providers = self.manager.list_providers()

        if self.console:
            table = Table(
                title="[bold]已配置的模型提供商[/bold]",
                box=box.ROUNDED,
                border_style="cyan"
            )
            table.add_column("状态", justify="center", width=4)
            table.add_column("提供商", style="bright_white")
            table.add_column("当前模型", style="dim")
            table.add_column("API Key", justify="center", width=8)

            for p in providers:
                status = "●" if p["is_active"] else "○"
                status_style = "[green]" if p["is_active"] else "[dim]"
                key_status = "[green]✓[/green]" if p["has_key"] else "[red]✗[/red]"
                table.add_row(
                    f"{status_style}{status}",
                    p["name"],
                    p["model"],
                    key_status
                )
            self.console.print(table)
        else:
            print("\n已配置的提供商:")
            for p in providers:
                status = "●" if p["is_active"] else "○"
                key = "✓" if p["has_key"] else "✗"
                print(f"  [{status}] {p['name']} (模型: {p['model']}, Key: {key})")

    def run(self):
        """运行配置面板"""
        if QUESTIONARY_AVAILABLE:
            self._run_questionary_ui()
        elif RICH_AVAILABLE:
            self._run_rich_ui()
        else:
            self._run_simple_ui()

    def _run_questionary_ui(self):
        """使用 questionary 的友好 UI（支持上下键）"""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_provider_table()

            # 主菜单 - 支持上下键导航
            choices = [
                questionary.Separator("─" * 40),
            ]

            # 动态添加提供商选项
            providers = self.manager.list_providers()
            for p in providers:
                prefix = "● " if p["is_active"] else "○ "
                suffix = " (当前默认)" if p["is_active"] else ""
                key_status = "✓" if p["has_key"] else "✗"
                choices.append(
                    f"{prefix}配置 {p['name']}{suffix} [Key: {key_status}]"
                )

            choices.extend([
                questionary.Separator("─" * 40),
                "➕ 添加自定义提供商",
                "🎤 配置 TTS 设置",
                "🎨 配置 UI 模式",
                questionary.Separator("─" * 40),
                "💾 保存并退出",
                "❌ 放弃并退出",
            ])

            choice = questionary.select(
                "\n请选择操作 (使用 ↑↓ 键导航，Enter 确认):",
                choices=choices,
                style=self.CUSTOM_STYLE,
                use_arrow_keys=True,
                show_selected=True,
            ).ask()

            if choice is None or choice == "❌ 放弃并退出":
                print("\n⚠️ 未保存更改")
                break
            elif choice == "💾 保存并退出":
                self.manager.save()
                print("\n✅ 配置已保存")
                break
            elif choice == "➕ 添加自定义提供商":
                self._add_custom_provider_questionary()
            elif choice == "🎤 配置 TTS 设置":
                self._config_tts_questionary()
            elif choice == "🎨 配置 UI 模式":
                self._config_ui_questionary()
            else:
                # 处理提供商配置
                for p in providers:
                    if p['name'] in choice:
                        self._config_provider_questionary(p["id"])
                        break

    def _config_provider_questionary(self, provider_id: str):
        """使用 questionary 配置单个提供商"""
        provider = self.manager.config.providers.get(provider_id)
        if not provider:
            return

        self.clear_screen()
        if self.console:
            self.console.print(Panel.fit(
                f"[bold]配置 {provider.name}[/bold]",
                border_style="blue"
            ))
        else:
            print(f"\n配置 {provider.name}")
            print("-" * 30)

        # API Key
        current_key_status = "已设置" if provider.api_key else "未设置"
        api_key = questionary.password(
            f"API Key (当前: {current_key_status}, 回车保持):",
            instruction="输入后按 Enter 确认"
        ).ask()

        if api_key:
            provider.api_key = api_key
            provider.enabled = True

        # Base URL（自定义提供商）
        if provider_id == "custom":
            base_url = questionary.text(
                f"Base URL [{provider.base_url}]:",
                default=provider.base_url
            ).ask()
            if base_url:
                provider.base_url = base_url

        # 默认模型
        if provider.available_models:
            model = questionary.select(
                "选择默认模型:",
                choices=provider.available_models + ["自定义..."],
                default=provider.default_model if provider.default_model in provider.available_models else None,
            ).ask()

            if model == "自定义...":
                model = questionary.text("输入模型名称:").ask()

            if model:
                provider.default_model = model
        else:
            model = questionary.text(
                f"默认模型 [{provider.default_model}]:",
                default=provider.default_model
            ).ask()
            if model:
                provider.default_model = model

        # 设为默认
        is_default = questionary.confirm(
            "设为默认提供商?",
            default=False
        ).ask()

        if is_default:
            self.manager.set_active_provider(provider_id)
            if self.console:
                self.console.print(f"[green]✓ {provider.name} 已设为默认[/green]")

        self.manager.save()

        questionary.press_any_key_to_continue("按任意键继续...").ask()

    def _add_custom_provider_questionary(self):
        """使用 questionary 添加自定义提供商"""
        self.clear_screen()
        if self.console:
            self.console.print(Panel.fit("[bold]添加自定义提供商[/bold]"))
        else:
            print("\n添加自定义提供商")

        name = questionary.text("显示名称:").ask()
        provider_id = questionary.text("唯一标识 (如: my-openai):").ask()
        base_url = questionary.text("Base URL (OpenAI 兼容):").ask()
        api_key = questionary.password("API Key:").ask()
        default_model = questionary.text("默认模型:").ask()

        if all([name, provider_id, base_url, api_key, default_model]):
            provider = ModelProvider(
                name=name,
                provider_id=provider_id,
                api_key=api_key,
                base_url=base_url,
                default_model=default_model,
                available_models=[default_model],
                enabled=True,
            )
            self.manager.add_provider(provider)
            if self.console:
                self.console.print(f"[green]✓ {name} 已添加[/green]")
            questionary.press_any_key_to_continue("按任意键继续...").ask()

    def _config_tts_questionary(self):
        """使用 questionary 配置 TTS"""
        self.clear_screen()
        if self.console:
            self.console.print(Panel.fit("[bold]TTS 配置[/bold]"))

        enabled = questionary.confirm(
            "启用 TTS?",
            default=self.manager.config.tts_enabled
        ).ask()
        self.manager.config.tts_enabled = enabled

        voice = questionary.select(
            "选择语音风格:",
            choices=[
                questionary.Choice("默认 (Ting-Ting)", value="default"),
                questionary.Choice("戏剧化 (Bad)", value="dramatic"),
                questionary.Choice("耳语 (Whisper)", value="whisper"),
            ],
            default=self.manager.config.tts_voice
        ).ask()

        if voice:
            self.manager.config.tts_voice = voice

        self.manager.save()
        if self.console:
            self.console.print("[green]✓ TTS 配置已保存[/green]")
        questionary.press_any_key_to_continue("按任意键继续...").ask()

    def _config_ui_questionary(self):
        """使用 questionary 配置 UI"""
        self.clear_screen()
        if self.console:
            self.console.print(Panel.fit("[bold]UI 模式配置[/bold]"))

        mode = questionary.select(
            "选择 UI 模式:",
            choices=[
                questionary.Choice("自动检测", value="auto"),
                questionary.Choice("简洁模式", value="compact"),
                questionary.Choice("仪表盘模式", value="dashboard"),
            ],
            default=self.manager.config.ui_mode
        ).ask()

        if mode:
            self.manager.config.ui_mode = mode
            self.manager.save()
            if self.console:
                self.console.print(f"[green]✓ UI 模式已设为 {mode}[/green]")
            questionary.press_any_key_to_continue("按任意键继续...").ask()

    def _run_rich_ui(self):
        """备用 Rich UI（不支持上下键）"""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_provider_table()

            self.console.print("\n[bold]选项:[/bold]")
            self.console.print("  [1-9] 选择并配置对应提供商")
            self.console.print("  [a] 添加自定义提供商")
            self.console.print("  [t] 配置 TTS 设置")
            self.console.print("  [u] 配置 UI 模式")
            self.console.print("  [s] 保存并退出")
            self.console.print("  [q] 放弃并退出")

            choice = input("\n> ").strip().lower()

            if choice == 'q':
                self.console.print("[yellow]⚠️ 未保存更改[/yellow]")
                break
            elif choice == 's':
                self.manager.save()
                self.console.print("[green]✅ 配置已保存[/green]")
                break
            elif choice == 'a':
                self._add_custom_provider_simple()
            elif choice == 't':
                self._config_tts_simple()
            elif choice == 'u':
                self._config_ui_simple()
            elif choice.isdigit():
                idx = int(choice) - 1
                providers = self.manager.list_providers()
                if 0 <= idx < len(providers):
                    self._config_provider_simple(providers[idx]["id"])

    def _run_simple_ui(self):
        """简单 UI"""
        print("\n💩 STOI 配置面板")
        print("=" * 40)
        self._run_rich_ui()  # 回退到 Rich UI 的逻辑，只是没有 Rich 样式

    def _config_provider_simple(self, provider_id: str):
        """简单模式配置提供商"""
        provider = self.manager.config.providers.get(provider_id)
        if not provider:
            return

        print(f"\n配置 {provider.name}")
        print("-" * 30)

        api_key = input(f"API Key (回车保持当前{'已设置' if provider.api_key else '未设置'}): ").strip()
        if api_key:
            provider.api_key = api_key
            provider.enabled = True

        model = input(f"默认模型 [{provider.default_model}]: ").strip()
        if model:
            provider.default_model = model

        set_default = input("设为默认提供商? [y/N]: ").strip().lower()
        if set_default == 'y':
            self.manager.set_active_provider(provider_id)

        self.manager.save()

    def _add_custom_provider_simple(self):
        """简单模式添加自定义提供商"""
        print("\n添加自定义提供商")
        print("-" * 30)

        name = input("显示名称: ").strip()
        provider_id = input("唯一标识: ").strip()
        base_url = input("Base URL (OpenAI 兼容): ").strip()
        api_key = input("API Key: ").strip()
        default_model = input("默认模型: ").strip()

        if all([name, provider_id, base_url, api_key, default_model]):
            provider = ModelProvider(
                name=name,
                provider_id=provider_id,
                api_key=api_key,
                base_url=base_url,
                default_model=default_model,
                available_models=[default_model],
            )
            self.manager.add_provider(provider)
            print(f"✓ {name} 已添加")

    def _config_tts_simple(self):
        """简单模式配置 TTS"""
        print("\nTTS 配置")
        enabled = input(f"启用 TTS? [Y/n]: ").strip().lower()
        self.manager.config.tts_enabled = enabled != 'n'

        voice = input(f"语音风格 (default/dramatic/whisper): ").strip()
        if voice:
            self.manager.config.tts_voice = voice

        self.manager.save()
        print("✓ TTS 配置已保存")

    def _config_ui_simple(self):
        """简单模式配置 UI"""
        print("\nUI 模式配置")
        print("  auto - 自动检测")
        print("  compact - 简洁模式")
        print("  dashboard - 仪表盘模式")

        mode = input(f"UI 模式 [{self.manager.config.ui_mode}]: ").strip()
        if mode in ["auto", "compact", "dashboard"]:
            self.manager.config.ui_mode = mode
            self.manager.save()
            print(f"✓ UI 模式已设为 {mode}")


def get_openai_client():
    """
    获取配置好的 OpenAI 客户端
    使用 OpenAI 兼容协议，支持多提供商
    """
    manager = ConfigManager()
    provider = manager.get_active_provider()

    if not provider:
        # 没有激活的提供商
        if manager.CONFIG_FILE.exists():
            raise ValueError(
                f"配置文件中没有可用的模型提供商\n"
                f"配置文件位置: {manager.CONFIG_FILE}\n"
                f"请运行 'stoi config' 添加提供商"
            )
        else:
            raise ValueError(
                "未配置模型提供商\n"
                "请运行: stoi config\n"
                "或设置环境变量: export DASHSCOPE_API_KEY=your_key"
            )

    if not provider.api_key:
        # 提供商存在但没有 API key
        raise ValueError(
            f"提供商 '{provider.name}' 没有配置 API Key\n"
            f"请运行 'stoi config' 配置 API Key\n"
            f"或使用 --provider 指定其他提供商"
        )

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "请安装 OpenAI SDK: pip install openai\n"
            "所有提供商都通过 OpenAI 兼容协议访问"
        )

    return OpenAI(
        api_key=provider.api_key,
        base_url=provider.base_url,
        timeout=provider.timeout,
        max_retries=provider.max_retries,
    ), provider.default_model


def main():
    """配置面板入口"""
    manager = ConfigManager()
    panel = InteractiveConfig(manager)
    panel.run()


if __name__ == "__main__":
    main()
