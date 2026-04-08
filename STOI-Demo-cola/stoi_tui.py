#!/usr/bin/env python3
"""
stoi_tui.py — STOI 实时 TUI 仪表盘
使用 Textual 框架，每 2 秒刷新一次
读取 ~/.stoi/sessions.jsonl
"""

import json
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, Label, ProgressBar
)
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.timer import Timer
from rich.text import Text

from stoi_engine import (
    SHIT_EMOJI, SHIT_THRESHOLDS,
    get_score_color,
)

LOG_FILE = Path("~/.stoi/sessions.jsonl").expanduser()
REFRESH_INTERVAL = 2.0  # seconds

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

# ── 颜色常量 ─────────────────────────────────────────────────────────────────
COLOR_BG      = "#0D0D0D"
COLOR_AMBER   = "#FFB800"
COLOR_GREEN   = "#00C853"
COLOR_YELLOW  = "#FFD600"
COLOR_ORANGE  = "#FF6D00"
COLOR_RED     = "#D50000"
COLOR_DIM     = "#555555"
COLOR_PANEL   = "#1A1A1A"
COLOR_BORDER  = "#2A2A2A"


def score_to_color(score: float) -> str:
    if score < 30:
        return COLOR_GREEN
    elif score < 50:
        return COLOR_YELLOW
    elif score < 75:
        return COLOR_ORANGE
    else:
        return COLOR_RED


def make_sparkline(values: list[float]) -> str:
    if not values:
        return SPARKLINE_CHARS[0] * 10
    mn, mx = min(values), max(values)
    if mx == mn:
        return SPARKLINE_CHARS[3] * len(values)
    result = ""
    for v in values:
        idx = int((v - mn) / (mx - mn) * 7)
        result += SPARKLINE_CHARS[min(idx, 7)]
    return result


def load_sessions(n: int = 10) -> list[dict]:
    """读取最近 N 条 session 记录"""
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records[-n:]
    except Exception:
        return []


# ── Widgets ──────────────────────────────────────────────────────────────────

STOI_CSS = f"""
Screen {{
    background: {COLOR_BG};
    color: white;
}}

#header-bar {{
    height: 3;
    background: {COLOR_PANEL};
    border-bottom: solid {COLOR_AMBER};
    padding: 0 2;
    align: left middle;
}}

#header-title {{
    color: {COLOR_AMBER};
    text-style: bold;
    width: auto;
}}

#header-live {{
    color: {COLOR_GREEN};
    width: auto;
    margin-left: 2;
}}

.panel {{
    background: {COLOR_PANEL};
    border: solid {COLOR_BORDER};
    padding: 1 2;
    margin: 1;
}}

.panel-title {{
    color: {COLOR_AMBER};
    text-style: bold;
    margin-bottom: 1;
}}

#score-display {{
    color: {COLOR_AMBER};
    text-style: bold;
    text-align: center;
    font-size: 2;
}}

#score-level {{
    text-align: center;
    color: white;
}}

.stat-label {{
    color: {COLOR_DIM};
    width: 20;
}}

.stat-value {{
    color: white;
    text-style: bold;
}}

#sparkline-display {{
    color: {COLOR_AMBER};
    letter-spacing: 1;
    font-size: 1;
}}

#suggestions {{
    color: {COLOR_DIM};
}}

#footer-bar {{
    height: 1;
    background: {COLOR_PANEL};
    border-top: solid {COLOR_AMBER};
    padding: 0 2;
    color: {COLOR_DIM};
}}

#main-layout {{
    height: 1fr;
    layout: grid;
    grid-size: 2;
    grid-rows: 1fr 1fr;
}}

#left-top {{
    row-span: 2;
}}
"""


class ScoreWidget(Static):
    """大号含屎量分数显示"""
    score = reactive(0.0)
    level = reactive("CLEAN")

    def render(self) -> Text:
        color = score_to_color(self.score)
        emoji = SHIT_EMOJI.get(self.level, "❓")

        t = Text(justify="center")
        t.append(f"\n  {self.score:.1f}%  {emoji}\n", style=f"bold {color}")
        t.append(f"  {self.level}\n", style="white")

        # 进度条
        bar_filled = int(self.score / 100 * 16)
        bar = "█" * bar_filled + "░" * (16 - bar_filled)
        t.append(f"\n  [{color}]{bar}[/{color}]\n", style=f"{color}")
        return t


class StatsWidget(Static):
    """本次会话统计"""
    records = reactive([], layout=True)

    def render(self) -> Text:
        t = Text()
        t.append("本次会话统计\n\n", style=f"bold {COLOR_AMBER}")

        if not self.records:
            t.append("  等待数据...\n", style=COLOR_DIM)
            t.append("  运行 stoi analyze 写入数据\n", style=COLOR_DIM)
            return t

        total_input  = sum(r["stoi"]["input_tokens"] for r in self.records)
        total_output = sum(r["stoi"]["output_tokens"] for r in self.records)
        total_cache  = sum(r["stoi"]["cache_read"] for r in self.records)
        total_wasted = sum(r["stoi"]["wasted_tokens"] for r in self.records)
        hit_rate     = round(total_cache / total_input * 100, 1) if total_input > 0 else 0.0

        rows = [
            ("Input tokens",   f"{total_input:,}",  "white"),
            ("Cache hit",      f"{hit_rate}%",       COLOR_GREEN if hit_rate > 50 else COLOR_ORANGE),
            ("Wasted",         f"{total_wasted:,}",  COLOR_RED),
            ("Output tokens",  f"{total_output:,}",  COLOR_GREEN),
            ("轮次",           f"{len(self.records)}", "white"),
        ]

        for label, val, color in rows:
            t.append(f"  {label:<18}", style=COLOR_DIM)
            t.append(f"{val}\n", style=f"bold {color}")

        return t


class SparklineWidget(Static):
    """多轮趋势 Sparkline"""
    records = reactive([], layout=True)

    def render(self) -> Text:
        t = Text()
        t.append("多轮趋势\n\n", style=f"bold {COLOR_AMBER}")

        if not self.records:
            t.append("  ▁▁▁▁▁▁▁▁▁▁  等待数据...\n", style=COLOR_DIM)
            return t

        scores = [r["stoi"]["stoi_score"] for r in self.records]
        sparkline = make_sparkline(scores)

        avg = sum(scores) / len(scores)
        color = score_to_color(avg)

        t.append(f"  {sparkline}\n", style=f"bold {color}")
        t.append(f"  最近 {len(scores)} 轮  均值 ", style=COLOR_DIM)
        t.append(f"{avg:.1f}%\n", style=f"bold {color}")

        # 最近几轮的简洁列表
        t.append("\n  近期轮次:\n", style=COLOR_DIM)
        for r in self.records[-5:]:
            s = r["stoi"]
            c = score_to_color(s["stoi_score"])
            ts = r.get("ts", "")[:16]
            t.append(f"  {ts}  ", style=COLOR_DIM)
            t.append(f"{s['stoi_score']:5.1f}%  ", style=f"{c}")
            t.append(f"{SHIT_EMOJI.get(s['level'], '')} {s['level']}\n", style="dim")

        return t


class SuggestionsWidget(Static):
    """L3 改进建议"""
    records = reactive([], layout=True)

    def render(self) -> Text:
        t = Text()
        t.append("L3 改进建议\n\n", style=f"bold {COLOR_AMBER}")

        if not self.records:
            t.append("  等待分析数据...\n", style=COLOR_DIM)
            return t

        # 从最近记录提取 L3 信息（如有）
        latest = self.records[-1]
        stoi = latest.get("stoi", {})
        score = stoi.get("stoi_score", 0)
        level = stoi.get("level", "CLEAN")
        hit_rate = stoi.get("cache_hit_rate", 0)

        # 基于数据给出建议
        if hit_rate > 70:
            t.append("  ✓ 缓存命中良好\n", style=COLOR_GREEN)
        elif hit_rate > 30:
            t.append("  ⚠ 缓存命中率中等\n", style=COLOR_YELLOW)
        else:
            t.append("  ✗ 缓存命中率极低\n", style=COLOR_RED)

        t.append("\n  改进建议:\n", style=COLOR_DIM)

        if score > 50:
            t.append("  ⚠ 时间戳注入 → 移至 user msg\n", style=COLOR_ORANGE)
            t.append("  ⚠ 检查 System Prompt 动态字段\n", style=COLOR_ORANGE)
        else:
            t.append("  ✓ 输出质量良好\n", style=COLOR_GREEN)

        if score > 75:
            t.append("  ✗ 考虑使用缓存前缀策略\n", style=COLOR_RED)
            t.append("  ✗ 运行 stoi blame 找元凶\n", style=COLOR_RED)
        else:
            t.append("  ✓ Cache 策略基本合理\n", style=COLOR_GREEN)

        # 模型信息
        model = latest.get("model", "unknown")
        t.append(f"\n  模型: ", style=COLOR_DIM)
        t.append(f"{model}\n", style="white dim")
        t.append(f"  更新: ", style=COLOR_DIM)
        t.append(f"{datetime.now().strftime('%H:%M:%S')}\n", style="white dim")

        return t


# ── Main App ─────────────────────────────────────────────────────────────────
class STOIApp(App):
    """STOI 实时仪表盘"""

    CSS = STOI_CSS

    TITLE = "STOI 含屎量监控"
    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新"),
    ]

    def __init__(self):
        super().__init__()
        self._records: list[dict] = []
        self._score_widget: ScoreWidget = None
        self._stats_widget: StatsWidget = None
        self._spark_widget: SparklineWidget = None
        self._suggest_widget: SuggestionsWidget = None
        self._timer: Timer = None

    def compose(self) -> ComposeResult:
        # Header
        with Horizontal(id="header-bar"):
            yield Label("💩 STOI  •  含屎量监控", id="header-title")
            yield Label("● LIVE", id="header-live")

        # Main 2-column layout
        with Horizontal(id="main-layout"):
            # Left column: score display
            with Vertical(classes="panel", id="left-top"):
                yield Label("含屎量分数", classes="panel-title")
                yield ScoreWidget(id="score-widget")

            # Right column: stats + trend + suggestions
            with Vertical():
                with Container(classes="panel"):
                    yield StatsWidget(id="stats-widget")

                with Container(classes="panel"):
                    yield SparklineWidget(id="spark-widget")

                with Container(classes="panel"):
                    yield SuggestionsWidget(id="suggest-widget")

        # Footer
        with Horizontal(id="footer-bar"):
            yield Label(
                f"数据源: {LOG_FILE}  •  每 {REFRESH_INTERVAL}s 刷新  •  [Q] 退出  •  [R] 立刻刷新",
                id="footer-info",
            )

    def on_mount(self) -> None:
        self._score_widget   = self.query_one("#score-widget", ScoreWidget)
        self._stats_widget   = self.query_one("#stats-widget", StatsWidget)
        self._spark_widget   = self.query_one("#spark-widget", SparklineWidget)
        self._suggest_widget = self.query_one("#suggest-widget", SuggestionsWidget)

        self._refresh_data()
        self._timer = self.set_interval(REFRESH_INTERVAL, self._refresh_data)

    def _refresh_data(self) -> None:
        """从日志文件重新加载数据并更新 widgets"""
        records = load_sessions(n=20)
        self._records = records

        if records:
            avg_score = sum(r["stoi"]["stoi_score"] for r in records) / len(records)
            avg_score = round(avg_score, 1)

            # 确定等级
            level = "DEEP_SHIT"
            for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
                if lo <= avg_score < hi:
                    level = lvl
                    break
        else:
            avg_score = 0.0
            level = "CLEAN"

        # 更新 reactive 属性
        self._score_widget.score   = avg_score
        self._score_widget.level   = level
        self._stats_widget.records   = list(records)
        self._spark_widget.records   = list(records)
        self._suggest_widget.records = list(records)

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_quit(self) -> None:
        self.exit()


def main():
    app = STOIApp()
    app.run()


if __name__ == "__main__":
    main()
