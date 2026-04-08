"""
STOI UI 布局管理器

统一管理不同显示模式的渲染
"""

from enum import Enum
from typing import Optional, Dict, Any
from rich.console import Console

from .theme import STOI_THEME


class DisplayMode(Enum):
    """显示模式枚举"""
    COMPACT = "compact"      # 简洁模式
    DASHBOARD = "dashboard"  # 仪表盘模式


class LayoutManager:
    """
    布局管理器

    根据模式选择不同的布局策略

    Usage:
        manager = LayoutManager(DisplayMode.COMPACT)
        manager.render(data)
    """

    def __init__(self, mode: DisplayMode, console: Optional[Console] = None):
        self.mode = mode
        self.console = console or Console(theme=STOI_THEME)
        self._renderer = self._create_renderer()

    def _create_renderer(self):
        """创建对应的渲染器"""
        from .modes import CompactRenderer, DashboardRenderer

        if self.mode == DisplayMode.COMPACT:
            return CompactRenderer(self.console)
        else:
            return DashboardRenderer(self.console)

    def render(self, data: Dict[str, Any]) -> None:
        """渲染数据"""
        self._renderer.render(data)

    def set_mode(self, mode: DisplayMode) -> None:
        """切换模式"""
        self.mode = mode
        self._renderer = self._create_renderer()


class LiveAnalyzer:
    """
    实时分析器 - 用于 Claude Code 调用时显示进度

    结合进度条和实时状态更新

    Usage:
        with LiveAnalyzer("正在分析 Token 效率...") as analyzer:
            analyzer.update_progress(50, "正在调用 LLM 评估...")
            # 执行分析...
            analyzer.update_progress(100, "分析完成")
    """

    def __init__(self, description: str = "分析中..."):
        self.description = description
        self._live = None
        self._progress = None

    def __enter__(self):
        from rich.live import Live
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

        self._progress = Progress(
            SpinnerColumn(style="bright_yellow"),
            TextColumn(f"[bold cyan]{self.description}"),
            BarColumn(
                complete_style="bright_yellow",
                finished_style="bright_green",
                bar_width=40
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TextColumn("[bright_black]{task.fields[status]}", justify="right"),
        )

        self._task_id = self._progress.add_task(
            self.description,
            total=100,
            status="初始化"
        )

        self._live = Live(
            self._progress,
            console=Console(),
            refresh_per_second=10
        )
        self._live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._live:
            self._live.stop()

    def update_progress(self, percentage: int, status: str = ""):
        """更新进度"""
        if self._progress and self._task_id is not None:
            self._progress.update(
                self._task_id,
                completed=percentage,
                status=status
            )

    def complete(self, message: str = "分析完成"):
        """完成分析"""
        self.update_progress(100, message)
