"""
等级徽章组件 - 显示 S/A/B/C/D/F 等级
"""

from dataclasses import dataclass
from typing import Optional
from rich.console import RenderableType
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

from ..theme import get_grade_config


@dataclass
class BadgeConfig:
    """徽章配置"""
    size: str = "medium"  # small, medium, large
    show_emoji: bool = True
    show_label: bool = True
    show_score: bool = True


class GradeBadge:
    """
    等级徽章组件 (S/A/B/C/D/F)

    输入:
        - grade: str 等级 (S/A/B/C/D/F)
        - stoi_index: float STOI 指数
        - config: BadgeConfig 配置选项

    输出:
        - RenderableType (Rich 可渲染对象)
    """

    def __init__(self, grade: str, stoi_index: float, config: Optional[BadgeConfig] = None):
        self.grade = grade.upper()
        self.stoi_index = stoi_index
        self.config = config or BadgeConfig()
        self.config_data = get_grade_config(self.grade)

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        # 构建徽章内容
        content = Text()

        if self.config.show_emoji:
            content.append(f"{self.config_data['emoji']} ", style="bold")

        content.append(self.grade, style=f"bold {self.config_data['color']}")

        if self.config.show_label:
            content.append(f" {self.config_data['label']}", style=self.config_data['color'])

        if self.config.show_score:
            content.append(f" ({self.stoi_index:.0f})", style="dim")

        # 根据尺寸调整
        if self.config.size == "large":
            return Panel(
                Align.center(content),
                border_style=self.config_data['color'],
                padding=(1, 3)
            )
        elif self.config.size == "small":
            return content
        else:  # medium
            return Panel(
                content,
                border_style=self.config_data['color'],
                padding=(0, 1)
            )

    def get_text(self) -> Text:
        """获取纯文本徽章"""
        text = Text()
        text.append(f"{self.config_data['emoji']} ", style="bold")
        text.append(self.grade, style=f"bold {self.config_data['color']}")
        text.append(f" {self.config_data['label']}", style=self.config_data['color'])
        return text

    def get_advice(self) -> str:
        """获取建议文本"""
        return self.config_data['advice']
