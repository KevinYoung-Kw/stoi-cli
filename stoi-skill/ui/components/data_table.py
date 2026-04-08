"""
数据表格组件 - 带颜色的数据表格
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from rich.console import RenderableType
from rich.table import Table
from rich.text import Text
from rich.panel import Panel


@dataclass
class TableConfig:
    """表格配置"""
    show_header: bool = True
    header_style: str = "bold bright_cyan"
    box_style: str = "ROUNDED"
    row_styles: Optional[List[str]] = None
    show_lines: bool = False


class ShitDataTable:
    """
    带颜色的数据表格组件

    输入:
        - columns: List[Dict] 列定义
        - rows: List[Dict] 行数据
        - config: TableConfig 配置选项

    输出:
        - Rich Table 对象
    """

    def __init__(
        self,
        columns: List[Dict[str, Any]],
        rows: List[Dict[str, Any]],
        config: Optional[TableConfig] = None
    ):
        self.columns = columns
        self.rows = rows
        self.config = config or TableConfig()

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        table = Table(
            show_header=self.config.show_header,
            header_style=self.config.header_style,
            box=getattr(Table, self.config.box_style, Table.box.ROUNDED),
            show_lines=self.config.show_lines
        )

        # 添加列
        for col in self.columns:
            table.add_column(
                col["name"],
                style=col.get("style"),
                justify=col.get("justify", "left"),
                width=col.get("width")
            )

        # 添加行
        for i, row in enumerate(self.rows):
            row_data = []
            for col in self.columns:
                key = col["key"]
                value = row.get(key, "")

                # 应用单元格样式
                styled_value = self._style_cell(value, col, row)
                row_data.append(styled_value)

            # 应用行样式
            row_style = None
            if self.config.row_styles:
                row_style = self.config.row_styles[i % len(self.config.row_styles)]

            table.add_row(*row_data, style=row_style)

        return table

    def _style_cell(self, value: Any, column: Dict, row: Dict) -> str:
        """根据值应用样式"""
        # 如果有自定义格式化函数
        if "format" in column and callable(column["format"]):
            return column["format"](value, row)

        # 根据值类型自动格式化
        if isinstance(value, float):
            return f"{value:.1f}"
        if isinstance(value, int) and column.get("max"):
            # 显示为星级
            max_val = column["max"]
            return self._star_rating(value, max_val)

        return str(value)

    def _star_rating(self, value: int, max_value: int) -> Text:
        """将数值转换为星级显示"""
        filled = value
        empty = max_value - value

        text = Text()
        text.append("💎" * filled, style="bright_cyan")
        text.append("💩" * empty, style="dim")
        text.append(f" {value}/{max_value}", style="bold")

        return text


class MetricCard:
    """指标卡片 - 显示单个关键指标"""

    def __init__(
        self,
        label: str,
        value: str,
        unit: str = "",
        color: str = "bright_cyan",
        subtitle: str = ""
    ):
        self.label = label
        self.value = value
        self.unit = unit
        self.color = color
        self.subtitle = subtitle

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        content = Text()

        # 标签
        content.append(f"{self.label}\n", style="dim")

        # 数值
        content.append(self.value, style=f"bold {self.color}")
        if self.unit:
            content.append(f" {self.unit}", style=self.color)

        # 副标题
        if self.subtitle:
            content.append(f"\n{self.subtitle}", style="dim italic")

        return Panel(
            content,
            border_style=self.color,
            padding=(1, 2)
        )


class SummaryPanel:
    """摘要面板 - 显示 AI 评价和建议"""

    def __init__(self, summary: str, advice: str, waste_ratio: float):
        self.summary = summary
        self.advice = advice
        self.waste_ratio = waste_ratio

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        from ..theme import get_color_by_waste_ratio

        color = get_color_by_waste_ratio(self.waste_ratio)

        content = Text()

        # 摘要
        content.append("【🤖 AI 屎评】\n", style="bold")
        content.append(f"{self.summary}\n\n", style="italic")

        # 建议
        content.append("【💡 建议】\n", style="bold")
        content.append(self.advice, style=f"{color}")

        return Panel(
            content,
            border_style=color,
            padding=(1, 2)
        )
