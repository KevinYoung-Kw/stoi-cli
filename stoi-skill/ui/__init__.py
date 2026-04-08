"""
STOI UI - 屎量分析仪终端界面系统

提供双模式界面：
- Compact Mode: 简洁模式，快速查看关键指标
- Dashboard Mode: 仪表盘模式，完整数据可视化
"""

from .layout import DisplayMode, LayoutManager
from .theme import STOI_THEME, get_color_by_waste_ratio, get_emoji_by_waste_ratio

__all__ = [
    'DisplayMode',
    'LayoutManager',
    'STOI_THEME',
    'get_color_by_waste_ratio',
    'get_emoji_by_waste_ratio',
]
