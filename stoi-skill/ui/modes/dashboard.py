"""
仪表盘模式渲染器 - 完整数据可视化

适用场景: 详细分析、报告生成、演示展示
"""

from typing import Dict, Any, Optional
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import box
from datetime import datetime

from ..components import (
    ShitProgressBar, ShitMeter, RadarChart, RadarData,
    GradeBadge, BadgeConfig, MetricCard, SummaryPanel
)
from ..theme import get_shit_meter_label


class DashboardRenderer:
    """仪表盘模式渲染器"""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def render(self, data: Dict[str, Any]) -> None:
        """渲染完整仪表盘"""
        eval_data = data.get("evaluation", {})
        session_id = data.get("session_id", "unknown")
        timestamp = data.get("timestamp", datetime.now().isoformat())

        # 使用 Rich Layout 创建复杂布局
        layout = Layout()

        # 分割布局
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=2),
            Layout(name="details", ratio=1),
            Layout(name="footer", size=6)
        )

        # 主区域分割为左右
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2)
        )

        # 填充内容
        layout["header"].update(self._render_header(session_id, timestamp))
        layout["left"].update(self._render_meter(eval_data))
        layout["right"].update(self._render_radar(eval_data))
        layout["details"].update(self._render_details(eval_data))
        layout["footer"].update(self._render_advice(eval_data))

        # 渲染
        self.console.print(layout)

    def _render_header(self, session_id: str, timestamp: str) -> Panel:
        """渲染头部"""
        content = Text()
        content.append("💩 STOI 屎量分析仪", style="bold bright_white")
        content.append("          ", style="")
        content.append(f"会话: ", style="dim")
        content.append(f"{session_id[:16]}...", style="bright_black")
        content.append("    ", style="")
        content.append(f"时间: ", style="dim")
        content.append(f"{timestamp[:19]}", style="bright_black")

        return Panel(content, style="on blue", box=box.SIMPLE)

    def _render_meter(self, eval_data: Dict) -> Panel:
        """渲染屎量计"""
        waste_ratio = eval_data.get("waste_ratio", 0)
        stoi_index = eval_data.get("stoi_index", 50)
        grade = eval_data.get("grade", "C")

        # 创建左侧内容
        from ..theme import get_grade_config
        config = get_grade_config(grade)
        content = Text(justify="center")

        # 等级徽章
        content.append(f"\n{config['emoji']} ", style="bold")
        content.append(f"{grade}\n", style=f"bold {config['color']}")
        content.append(f"{config['label']}\n", style=config['color'])
        content.append("\n", style="")

        # 纯净度
        content.append("纯净度\n", style="dim")
        content.append(f"{stoi_index:.0f}", style="bold bright_cyan")
        content.append("/100\n\n", style="dim")

        # 含屎量
        content.append("含屎量\n", style="dim")
        content.append(f"{waste_ratio * 100:.1f}%\n", style=f"bold {self._get_color(waste_ratio)}")

        # 评级
        label = get_shit_meter_label(waste_ratio)
        content.append(f"\n{label}", style="italic")

        return Panel(
            content,
            title="[bold]💩 屎量指数[/bold]",
            border_style="cyan",
            box=box.ROUNDED
        )

    def _render_radar(self, eval_data: Dict) -> Panel:
        """渲染雷达图"""
        radar_data = [
            RadarData("问题解决度", eval_data.get("problem_solving", 3)),
            RadarData("代码质量", eval_data.get("code_quality", 3)),
            RadarData("信息密度", eval_data.get("information_density", 3)),
            RadarData("上下文效率", eval_data.get("context_efficiency", 3)),
        ]
        radar = RadarChart(radar_data)
        return radar

    def _render_details(self, eval_data: Dict) -> Panel:
        """渲染详细指标表格"""
        table = Table(
            show_header=True,
            header_style="bold bright_cyan",
            box=box.SIMPLE_HEAD
        )

        table.add_column("维度", style="cyan", width=12)
        table.add_column("得分", justify="center", width=8)
        table.add_column("权重", justify="center", width=8)
        table.add_column("权重得分", justify="center", width=10)
        table.add_column("可视化", width=20)

        dimensions = [
            ("问题解决度", eval_data.get("problem_solving", 3), 0.35),
            ("代码质量", eval_data.get("code_quality", 3), 0.25),
            ("信息密度", eval_data.get("information_density", 3), 0.20),
            ("上下文效率", eval_data.get("context_efficiency", 3), 0.20),
        ]

        for label, score, weight in dimensions:
            weighted_score = score * weight * 20  # 转换为百分制
            visual = "💎" * score + "💩" * (5 - score)
            color = "bright_cyan" if score >= 4 else "yellow" if score >= 3 else "orange3"

            table.add_row(
                label,
                f"{score}/5",
                f"{weight:.0%}",
                f"{weighted_score:.1f}",
                f"[{color}]{visual}[/{color}]"
            )

        return Panel(
            table,
            title="[bold]📋 详细指标[/bold]",
            border_style="green",
            box=box.ROUNDED
        )

    def _render_advice(self, eval_data: Dict) -> Panel:
        """渲染建议面板"""
        summary = eval_data.get("summary", "暂无评价")
        advice = eval_data.get("advice", "")
        waste_ratio = eval_data.get("waste_ratio", 0)

        content = Text()
        content.append("【🤖 AI 屎评】\n", style="bold bright_yellow")
        content.append(f"{summary}\n\n", style="italic")

        if advice:
            content.append("【💡 建议】\n", style="bold")
            content.append(advice, style="bright_cyan")

        color = self._get_color(waste_ratio)

        return Panel(
            content,
            border_style=color,
            box=box.ROUNDED
        )

    def _get_color(self, waste_ratio: float) -> str:
        """根据 waste_ratio 返回颜色"""
        if waste_ratio < 0.2:
            return "bright_cyan"
        elif waste_ratio < 0.4:
            return "bright_green"
        elif waste_ratio < 0.6:
            return "bright_yellow"
        elif waste_ratio < 0.8:
            return "yellow"
        else:
            return "orange3"
