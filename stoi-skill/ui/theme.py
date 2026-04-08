"""
STOI 主题系统 - 颜色、样式、品牌配置

设计理念: 钻石蓝 → 屎黄 → 屎棕 的渐变
代表 Token 效率从高到低的退化过程
"""

from dataclasses import dataclass
from rich.theme import Theme
from rich.style import Style


@dataclass
class ShitColorScheme:
    """
    STOI 品牌色彩系统

    钻石级 (高效) → 屎山级 (低效)
    """

    # 钻石级
    DIAMOND: str = "bright_cyan"
    DIAMOND_BG: str = "cyan"

    # 优秀级
    EXCELLENT: str = "bright_green"
    EXCELLENT_BG: str = "green"

    # 良好级
    GOOD: str = "bright_yellow"
    GOOD_BG: str = "yellow"

    # 一般级
    FAIR: str = "yellow"
    FAIR_BG: str = "dark_orange"

    # 较差级
    POOR: str = "orange3"
    POOR_BG: str = "orange4"

    # 失败级
    FAIL: str = "dark_red"
    FAIL_BG: str = "red"

    # 中性色
    TEXT: str = "white"
    MUTED: str = "bright_black"
    BORDER: str = "dim"
    HEADER: str = "bold bright_white"


# 创建 Rich Theme
STOI_THEME = Theme({
    # 信息层级
    "info": "dim cyan",
    "info.bold": "bold cyan",
    "warning": "yellow",
    "warning.bold": "bold yellow",
    "danger": "bold red",
    "success": "bold green",
    "muted": "bright_black",

    # 品牌专用 - 屎量等级
    "stoi.diamond": "bright_cyan",
    "stoi.excellent": "bright_green",
    "stoi.good": "bright_yellow",
    "stoi.fair": "yellow",
    "stoi.poor": "orange3",
    "stoi.fail": "dark_red",

    # 组件样式
    "stoi.header": "bold bright_white",
    "stoi.border": "dim",
    "stoi.label": "bright_cyan",
    "stoi.value": "white",
    "stoi.highlight": "bold bright_yellow",

    # 表格样式
    "stoi.table.header": "bold bright_cyan",
    "stoi.table.row_alt": "dim",
})


def get_color_by_waste_ratio(ratio: float) -> str:
    """
    根据浪费比例返回对应颜色

    Args:
        ratio: 0.0 - 1.0 的浪费比例

    Returns:
        Rich 颜色名称
    """
    if ratio < 0.1:
        return "bright_cyan"      # 钻石级
    elif ratio < 0.3:
        return "bright_green"     # 优秀
    elif ratio < 0.5:
        return "bright_yellow"    # 良好
    elif ratio < 0.7:
        return "yellow"           # 一般
    elif ratio < 0.9:
        return "orange3"          # 较差
    else:
        return "dark_red"         # 失败


def get_emoji_by_waste_ratio(ratio: float) -> str:
    """根据浪费比例返回对应表情"""
    if ratio < 0.1:
        return "💎"
    elif ratio < 0.3:
        return "🌟"
    elif ratio < 0.5:
        return "💩"
    elif ratio < 0.7:
        return "💩💩"
    elif ratio < 0.9:
        return "💩💩💩"
    else:
        return "💩💩💩💩💩"


def get_grade_config(grade: str) -> dict:
    """
    获取等级配置

    Returns:
        {
            "emoji": str,
            "label": str,
            "color": str,
            "bg": str,
            "advice": str
        }
    """
    configs = {
        "S": {
            "emoji": "💎",
            "label": "钻石级",
            "color": "bright_cyan",
            "bg": "cyan",
            "advice": "🌸 太棒了！你的代码清新脱俗，继续保持！"
        },
        "A": {
            "emoji": "🌟",
            "label": "优秀",
            "color": "bright_green",
            "bg": "green",
            "advice": "✨ 表现优秀！只有轻微的优化空间。"
        },
        "B": {
            "emoji": "💩",
            "label": "良好",
            "color": "bright_yellow",
            "bg": "yellow",
            "advice": "💨 略有味道，可以稍微精简一下。"
        },
        "C": {
            "emoji": "💩💩",
            "label": "一般",
            "color": "yellow",
            "bg": "dark_orange",
            "advice": "💩 开始有屎了！建议检查是否有废话。"
        },
        "D": {
            "emoji": "💩💩💩",
            "label": "较差",
            "color": "orange3",
            "bg": "orange4",
            "advice": "💩💩 屎量可观！Token 浪费严重，请优化！"
        },
        "F": {
            "emoji": "💩💩💩💩💩",
            "label": "屎山",
            "color": "dark_red",
            "bg": "red",
            "advice": "💩💩💩💩💩 史无前例的屎山！建议立即重构！"
        }
    }
    return configs.get(grade.upper(), configs["C"])


def get_shit_meter_label(ratio: float) -> str:
    """获取屎量评级标签"""
    if ratio < 0.1:
        return "🌸 清新脱俗"
    elif ratio < 0.3:
        return "💨 略有味道"
    elif ratio < 0.5:
        return "💩 开始有屎"
    elif ratio < 0.7:
        return "💩💩 屎量可观"
    elif ratio < 0.9:
        return "💩💩💩 屎山一座"
    else:
        return "💩💩💩💩💩 屎无前例"
