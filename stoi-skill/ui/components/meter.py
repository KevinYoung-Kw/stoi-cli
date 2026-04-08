"""
屎量仪表盘组件 - ASCII 艺术风格仪表盘
"""

from dataclasses import dataclass
from typing import Optional
from rich.console import RenderableType
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

from ..theme import get_color_by_waste_ratio, get_shit_meter_label


@dataclass
class MeterConfig:
    """仪表盘配置"""
    width: int = 30
    show_label: bool = True
    show_value: bool = True


class ShitMeter:
    """
    ASCII 艺术风格的屎量仪表盘

    输入:
        - value: float (0.0 - 1.0) 当前值
        - label: str 标签文本
        - config: MeterConfig 配置选项

    输出:
        - RenderableType (Rich 可渲染对象)

    视觉设计:
            [    💎    ]
           [   /    \   ]
          [  /      \  ]
         [ /   35%   \ ]  <- 指针随值变化
        [_______________]
           开始有屎
    """

    def __init__(self, value: float, label: str = "含屎量", config: Optional[MeterConfig] = None):
        self.value = max(0.0, min(1.0, value))
        self.label = label
        self.config = config or MeterConfig()
        self.color = get_color_by_waste_ratio(self.value)

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        # 生成仪表盘 ASCII 艺术
        lines = self._generate_gauge()
        gauge_text = Text("\n".join(lines))

        # 添加标签
        if self.config.show_label:
            label_text = Text(f"\n{self.label}", style=f"bold {self.color}")
            content = Text.assemble(gauge_text, label_text)
        else:
            content = gauge_text

        return Panel(
            Align.center(content),
            border_style=self.color,
            padding=(1, 2)
        )

    def _generate_gauge(self) -> list:
        """生成仪表盘 ASCII 艺术"""
        width = self.config.width
        lines = []

        # 计算指针位置
        # 0% = 左边, 100% = 右边
        pointer_pos = int(self.value * (width - 2))

        # 顶部装饰
        top_padding = " " * (width // 3)
        lines.append(f"{top_padding}╭{'─' * (width // 3)}╮")

        # 弧形上半部分
        for i in range(3):
            spaces = " " * (3 - i)
            arc_width = width - 6 + i * 2
            lines.append(f"{spaces}╭{'─' * arc_width}╮")

        # 指针行
        pointer_line = [" "] * width
        pointer_line[0] = "│"
        pointer_line[-1] = "│"

        # 根据值设置指针位置
        if 0 <= pointer_pos < width:
            pointer_line[pointer_pos] = "▲"

        # 添加数值显示
        value_str = f" {self.value * 100:.0f}% "
        value_start = max(0, pointer_pos - len(value_str) // 2)

        for i, char in enumerate(value_str):
            pos = value_start + i
            if 0 < pos < width - 1 and pointer_line[pos] == " ":
                pointer_line[pos] = char

        lines.append("".join(pointer_line))

        # 底部
        lines.append(f"╰{'─' * (width - 2)}╯")

        # 评级标签
        if self.config.show_value:
            label = get_shit_meter_label(self.value)
            lines.append(label.center(width))

        return lines


class SimpleMeter:
    """简化版仪表盘 - 水平条形"""

    def __init__(self, value: float, width: int = 40):
        self.value = max(0.0, min(1.0, value))
        self.width = width
        self.color = get_color_by_waste_ratio(self.value)

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        filled = int(self.value * self.width)
        empty = self.width - filled

        bar = Text()

        # 左括号
        bar.append("[", style="dim")

        # 填充部分（渐变色）
        if filled > 0:
            for i in range(filled):
                # 从绿色渐变到红色
                ratio = i / self.width
                char = self._get_gradient_char(ratio)
                bar.append(char, style=self._get_gradient_style(ratio))

        # 空白部分
        if empty > 0:
            bar.append("░" * empty, style="dim")

        # 右括号
        bar.append("]", style="dim")

        # 百分比
        bar.append(f" {self.value * 100:.1f}%", style=f"bold {self.color}")

        return bar

    def _get_gradient_char(self, ratio: float) -> str:
        """获取渐变字符"""
        chars = ["█", "▉", "▊", "▋", "▌", "▍", "▎", "▏"]
        idx = int(ratio * (len(chars) - 1))
        return chars[idx]

    def _get_gradient_style(self, ratio: float) -> str:
        """获取渐变色样式"""
        if ratio < 0.2:
            return "bright_cyan"
        elif ratio < 0.4:
            return "bright_green"
        elif ratio < 0.6:
            return "bright_yellow"
        elif ratio < 0.8:
            return "yellow"
        else:
            return "dark_red"
