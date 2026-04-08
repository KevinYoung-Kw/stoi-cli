"""
雷达图组件 - ASCII 艺术四维雷达图
"""

from dataclasses import dataclass
from typing import List, Optional
from rich.console import RenderableType
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
import math


@dataclass
class RadarData:
    """雷达图数据点"""
    label: str
    value: int
    max_value: int = 5


@dataclass
class RadarConfig:
    """雷达图配置"""
    size: int = 12
    show_grid: bool = True
    fill_char: str = "█"
    grid_char: str = "·"
    axis_char: str = "─"


class RadarChart:
    """
    ASCII 艺术四维雷达图

    输入:
        - data: List[RadarData] 四个维度的数据
        - config: RadarConfig 配置选项

    输出:
        - RenderableType (Rich 可渲染对象)

    维度顺序:
        - 问题解决度 (上)
        - 代码质量 (右)
        - 信息密度 (下)
        - 上下文效率 (左)
    """

    DIMENSIONS = ["问题解决度", "代码质量", "信息密度", "上下文效率"]

    def __init__(self, data: List[RadarData], config: Optional[RadarConfig] = None):
        assert len(data) == 4, "雷达图需要恰好4个维度"
        self.data = data
        self.config = config or RadarConfig()

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        # 生成雷达图文本
        chart_lines = self._generate_chart()

        # 构建完整文本
        chart_text = Text("\n".join(chart_lines))

        return Panel(
            Align.center(chart_text),
            title="[bold]📊 维度分析[/bold]",
            border_style="cyan",
            padding=(1, 2)
        )

    def _generate_chart(self) -> List[str]:
        """生成雷达图文本行"""
        size = self.config.size
        center = size // 2

        # 创建网格
        grid = [[" " for _ in range(size)] for _ in range(size)]

        # 绘制坐标轴
        for i in range(size):
            if i != center:
                grid[center][i] = self.config.grid_char  # 水平轴
                grid[i][center] = self.config.grid_char  # 垂直轴

        # 四个顶点位置 (上、右、下、左)
        angles = [math.pi/2, 0, -math.pi/2, math.pi]
        max_radius = center - 1

        # 绘制数据多边形
        points = []
        for i, (data_point, angle) in enumerate(zip(self.data, angles)):
            radius = (data_point.value / data_point.max_value) * max_radius
            x = int(center + radius * math.cos(angle))
            y = int(center - radius * math.sin(angle))
            points.append((x, y))

        # 连接各点形成多边形
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            self._draw_line(grid, x1, y1, x2, y2)

        # 标记顶点
        for i, (x, y) in enumerate(points):
            if 0 <= y < size and 0 <= x < size:
                grid[y][x] = str(self.data[i].value)

        # 中心点
        grid[center][center] = "+"

        # 转换为文本行并添加标签
        lines = []

        # 上标签
        top_label = f"  {self.data[0].label} ({self.data[0].value})"
        lines.append(top_label.center(size * 2))

        for i, row in enumerate(grid):
            line = "".join(row)

            # 添加左右标签
            if i == center - 1:
                left = f"{self.data[3].label}({self.data[3].value})"
                right = f"({self.data[1].value}){self.data[1].label}"
                line = f"{left[:6]:<6} {line} {right:>6}"
            else:
                line = f"         {line}"

            lines.append(line)

        # 下标签
        bottom_label = f"  {self.data[2].label} ({self.data[2].value})"
        lines.append(bottom_label.center(size * 2))

        return lines

    def _draw_line(self, grid, x1, y1, x2, y2):
        """在网格上绘制线条（Bresenham 算法简化版）"""
        size = len(grid)

        # 简化的直线绘制
        steps = max(abs(x2 - x1), abs(y2 - y1)) + 1
        if steps == 0:
            return

        for i in range(steps):
            t = i / (steps - 1) if steps > 1 else 0
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)

            if 0 <= y < size and 0 <= x < size:
                if grid[y][x] == " ":
                    grid[y][x] = self.config.fill_char


class SimpleBarChart:
    """简单条形图 - 用于维度对比"""

    def __init__(self, data: List[RadarData], width: int = 40):
        self.data = data
        self.width = width

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        lines = []

        max_label_len = max(len(d.label) for d in self.data)

        for item in self.data:
            # 标签
            label = f"{item.label:>{max_label_len}}"

            # 条形
            bar_width = int((item.value / item.max_value) * (self.width - max_label_len - 5))
            bar = "█" * bar_width

            # 颜色
            color = self._get_color(item.value, item.max_value)

            line = Text()
            line.append(f"{label} ", style="dim")
            line.append(bar, style=color)
            line.append(f" {item.value}/{item.max_value}", style="bold")

            lines.append(line)

        return Panel(
            Text("\n").join(lines),
            title="[bold]📊 维度评分[/bold]",
            border_style="green"
        )

    def _get_color(self, value: int, max_value: int) -> str:
        """根据值返回颜色"""
        ratio = value / max_value
        if ratio >= 0.8:
            return "bright_cyan"
        elif ratio >= 0.6:
            return "bright_green"
        elif ratio >= 0.4:
            return "bright_yellow"
        elif ratio >= 0.2:
            return "yellow"
        else:
            return "orange3"
