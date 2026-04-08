"""
屎量进度条组件 - 用 💩 填充表示浪费比例
"""

from dataclasses import dataclass
from typing import Optional
from rich.console import RenderableType, Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

from ..theme import get_color_by_waste_ratio


@dataclass
class ProgressBarConfig:
    """进度条配置"""
    width: int = 40
    fill_char: str = "💩"
    empty_char: str = "░"
    show_percentage: bool = True
    show_label: bool = True
    label: str = "含屎量"


class ShitProgressBar:
    """
    屎量进度条 - 用 💩 的数量直观显示浪费比例

    输入:
        - waste_ratio: float (0.0 - 1.0) 浪费比例
        - config: ProgressBarConfig 配置选项

    输出:
        - RenderableType (Rich 可渲染对象)
    """

    def __init__(self, waste_ratio: float, config: Optional[ProgressBarConfig] = None):
        self.waste_ratio = max(0.0, min(1.0, waste_ratio))
        self.config = config or ProgressBarConfig()
        self.color = get_color_by_waste_ratio(self.waste_ratio)

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        # 计算填充数量
        filled = int(self.waste_ratio * self.config.width)
        empty = self.config.width - filled

        # 构建进度条文本
        bar = Text()

        # 填充部分（💩）
        if filled > 0:
            bar.append(self.config.fill_char * filled, style=f"bold {self.color}")

        # 空白部分
        if empty > 0:
            bar.append(self.config.empty_char * empty, style="dim")

        # 百分比
        if self.config.show_percentage:
            percentage = f" {self.waste_ratio * 100:.1f}%"
            bar.append(percentage, style=f"bold {self.color}")

        # 创建面板
        if self.config.show_label:
            title = f"[bold]{self.config.label}[/bold]"
            return Panel(
                Align.center(bar),
                title=title,
                border_style=self.color,
                padding=(1, 2)
            )
        else:
            return bar

    def get_progress_text(self) -> Text:
        """获取纯文本进度条（用于内联显示）"""
        filled = int(self.waste_ratio * self.config.width)
        empty = self.config.width - filled

        bar = Text()
        if filled > 0:
            bar.append(self.config.fill_char * filled, style=self.color)
        if empty > 0:
            bar.append(self.config.empty_char * empty, style="dim")

        return bar


class MultiProgressBar:
    """多任务进度条 - 用于显示多个会话的分析进度"""

    def __init__(self, tasks: list):
        """
        Args:
            tasks: [(task_name, progress, total), ...]
        """
        self.tasks = tasks

    def __rich__(self) -> RenderableType:
        """Rich 渲染接口"""
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=Console()
        )

        for name, current, total in self.tasks:
            progress.add_task(name, total=total, completed=current)

        return progress


class LiveProgressTracker:
    """
    实时进度追踪器 - 用于 Claude Code 调用时显示分析进度

    Usage:
        with LiveProgressTracker("正在分析 Token 效率...") as tracker:
            for i in range(100):
                tracker.update(i + 1)
                time.sleep(0.1)
    """

    def __init__(self, description: str = "分析中..."):
        self.description = description
        self.progress = None
        self.task_id = None
        self.console = Console()

    def __enter__(self):
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

        self.progress = Progress(
            SpinnerColumn(style="bright_yellow"),
            TextColumn(f"[bold cyan]{self.description}"),
            BarColumn(bar_width=None, complete_style="bright_yellow", finished_style="bright_green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[bright_black]{task.fields[status]}", justify="right"),
            console=self.console
        )
        self.progress.start()
        self.task_id = self.progress.add_task(self.description, total=100, status="初始化")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.stop()

    def update(self, percentage: int, status: str = ""):
        """更新进度"""
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=percentage,
                status=status
            )

    def advance(self, amount: int = 1, status: str = ""):
        """前进指定步数"""
        if self.progress and self.task_id is not None:
            self.progress.advance(self.task_id, advance=amount)
            if status:
                self.progress.update(self.task_id, status=status)
