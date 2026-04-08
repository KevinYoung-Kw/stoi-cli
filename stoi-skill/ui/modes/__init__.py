"""
STOI UI 显示模式

- Compact Mode: 简洁模式，快速查看关键指标
- Dashboard Mode: 仪表盘模式，完整数据可视化
"""

from .compact import CompactRenderer
from .dashboard import DashboardRenderer

__all__ = [
    'CompactRenderer',
    'DashboardRenderer',
]
