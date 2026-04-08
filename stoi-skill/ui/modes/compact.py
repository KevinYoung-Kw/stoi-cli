"""
简洁模式渲染器 - 快速查看关键指标

适用场景: 日常使用、CI/CD 集成、日志输出
"""

from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table
from rich import box

from ..components import ShitProgressBar, GradeBadge, BadgeConfig
from ..theme import get_shit_meter_label


class CompactRenderer:
    """简洁模式渲染器"""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def render(self, data: Dict[str, Any]) -> None:
        """渲染简洁报告"""
        eval_data = data.get("evaluation", {})
        session_id = data.get("session_id", "unknown")

        # 1. 头部 - 等级和纯净度
        header = self._render_header(eval_data, session_id)
        self.console.print(header)

        # 2. 进度条
        waste_ratio = eval_data.get("waste_ratio", 0)
        progress = ShitProgressBar(waste_ratio)
        self.console.print(progress)

        # 3. 维度评分表格
        dimensions = self._render_dimensions(eval_data)
        self.console.print(dimensions)

        # 4. 评价摘要
        summary = self._render_summary(eval_data)
        self.console.print(summary)

        # 空行
        self.console.print()

    def _render_header(self, eval_data: Dict, session_id: str) -> Panel:
        """渲染头部"""
        grade = eval_data.get("grade", "C")
        stoi_index = eval_data.get("stoi_index", 50)

        # 创建徽章文本
        from ..theme import get_grade_config
        config = get_grade_config(grade)

        content = Text()
        content.append(f"会话: ", style="dim")
        content.append(f"{session_id}\n", style="bright_black")
        content.append(f"等级: ", style="dim")
        content.append(f"{config['emoji']} ", style="bold")
        content.append(f"{grade} ", style=f"bold {config['color']}")
        content.append(f"{config['label']}", style=config['color'])
        content.append("    ")
        content.append("纯净度: ", style="dim")
        content.append(f"{stoi_index:.0f}/100", style="bold bright_cyan")

        return Panel(
            content,
            title="[bold]💩 STOI 分析结果[/bold]",
            border_style="cyan",
            box=box.ROUNDED
        )

    def _render_dimensions(self, eval_data: Dict) -> Panel:
        """渲染维度评分"""
        dimensions = [
            ("问题解决度", eval_data.get("problem_solving", 3)),
            ("代码质量", eval_data.get("code_quality", 3)),
            ("信息密度", eval_data.get("information_density", 3)),
            ("上下文效率", eval_data.get("context_efficiency", 3)),
        ]

        # 使用表格显示
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("维度", style="cyan", width=12)
        table.add_column("评分", width=20)
        table.add_column("数值", justify="right", width=8)

        for label, score in dimensions:
            bar = "█" * score + "░" * (5 - score)
            color = "bright_cyan" if score >= 4 else "yellow" if score >= 3 else "orange3"

            table.add_row(
                label,
                f"[{color}]{bar}[/{color}]",
                f"{score}/5"
            )

        return Panel(
            table,
            title="[bold]💩 维度评分[/bold]",
            border_style="green",
            box=box.ROUNDED
        )

    def _render_summary(self, eval_data: Dict) -> Panel:
        """渲染评价摘要"""
        summary = eval_data.get("summary", "暂无评价")
        advice = eval_data.get("advice", "")

        content = Text()
        content.append("【🤖 AI 屎评】\n", style="bold bright_yellow")
        content.append(f"{summary}\n\n", style="italic")

        if advice:
            content.append("【💡 建议】\n", style="bold")
            content.append(advice, style="bright_cyan")

        waste_ratio = eval_data.get("waste_ratio", 0)
        color = "bright_cyan" if waste_ratio < 0.3 else "yellow" if waste_ratio < 0.6 else "orange3"

        return Panel(
            content,
            border_style=color,
            box=box.ROUNDED
        )
