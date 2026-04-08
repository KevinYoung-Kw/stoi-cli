#!/usr/bin/env python3
"""
stoi_report.py — STOI 报告渲染层 v2

Renders a STOIReport (from stoi_core.py) in two formats:
  - CLI:  Rich terminal output (80-col, dark terminal, amber accents)
  - HTML: Claude Code insights style, self-contained

Public API:
    render_cli(report)                         → None
    render_html(report, output_path)           → Path
    render_report(report, format, output_dir)  → Optional[Path]
"""

from __future__ import annotations

import math
import html as _html
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
from rich.rule import Rule

from stoi_core import STOIReport, TurnRecord, _get_level

# ─── Colour palette ───────────────────────────────────────────────────────────
AMBER  = "#FFB800"
WHITE  = "white"
DIM    = "dim"
GREEN  = "green"
RED    = "red"
ORANGE = "dark_orange"
YELLOW = "yellow"

SEVERITY_COLOR = {"HIGH": "red", "MED": "yellow", "LOW": "dim"}
SEVERITY_LABEL = {"HIGH": "HIGH", "MED":  "MED ",  "LOW": "LOW "}

SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _score_color(score: float) -> str:
    if score < 30:   return GREEN
    if score < 50:   return YELLOW
    if score < 75:   return ORANGE
    return RED


def _bar(value: float, total: float = 100.0, width: int = 20, *, invert: bool = False) -> str:
    """Return a Rich markup progress bar string."""
    pct = min(max(value / total, 0.0), 1.0)
    filled = int(pct * width)
    empty  = width - filled
    # pick fill colour
    if invert:
        # higher = better (cache hit, effectiveness)
        color = GREEN if pct >= 0.7 else YELLOW if pct >= 0.4 else RED
    else:
        # higher = worse (stoi score)
        color = GREEN if pct < 0.30 else YELLOW if pct < 0.50 else ORANGE if pct < 0.75 else RED
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def _sparkline(values: list[float], width: int = 20) -> str:
    if not values:
        return "─" * width
    vals = values[-width:]
    result = ""
    for v in vals:
        if v <= 0:
            result += "▁"
        else:
            idx = max(1, min(8, int(v / 100 * 8)))
            result += SPARKLINE_CHARS[idx]
    return result.ljust(width)


def _fmt_dollars(v: float) -> str:
    if v < 0.0001:
        return f"${v:.6f}"
    if v < 0.01:
        return f"${v:.4f}"
    return f"${v:.4f}"


def _rule_based_suggestions(report: STOIReport) -> list[str]:
    """Fallback suggestions when LLM is not available."""
    s: list[str] = []
    if report.avg_cache_hit_rate < 30:
        s.append("将 System Prompt 中的时间戳、UUID 等动态字段移到 user turn，可将缓存命中率提升至 80%+")
    if report.invalid_turns_count > 0 and report.valid_turns > 0:
        rate = report.invalid_turns_count / max(report.valid_turns, 1)
        if rate > 0.2:
            s.append(f"有 {report.invalid_turns_count} 轮输出被用户否定：在 prompt 里加入输出格式约束和示例，减少返工率")
    if report.avg_stoi_score > 50:
        s.append("考虑每 20 轮压缩一次历史对话（保留摘要），避免上下文膨胀导致 token 浪费")
    # 只在真正有问题时才给建议，没问题就诚实说没问题
    if not s:
        s.append("当前 session 整体健康，无明显优化空间")
    return s[:3]


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Renderer
# ═══════════════════════════════════════════════════════════════════════════════

def render_cli(report: STOIReport) -> None:
    """Print a rich terminal STOI report to stdout."""
    console = Console(width=80, highlight=False)

    # ── Header box ────────────────────────────────────────────────────────────
    date_str = report.generated_at[:10] if report.generated_at else datetime.now().strftime("%Y-%m-%d")
    header_text = (
        f"[bold {AMBER}]💩 STOI Report[/bold {AMBER}]  [dim]|[/dim]  [white]{report.session_name}[/white]\n"
        f"[dim]Generated: {date_str}  |  {report.total_turns} turns  |  {report.source_tool}[/dim]"
    )
    console.print(Panel(header_text, border_style=AMBER, padding=(0, 2)))

    # ── Overview ──────────────────────────────────────────────────────────────
    console.print(f"\n[bold {AMBER}]📊 总览[/bold {AMBER}]")

    _, level_emoji = _get_level(report.avg_stoi_score)
    stoi_label = f"{level_emoji} {report.stoi_level}"
    hit_pct    = report.avg_cache_hit_rate
    eff_pct    = report.effectiveness_rate

    overview = Table(box=None, padding=(0, 1), show_header=False)
    overview.add_column(width=10, no_wrap=True)
    overview.add_column(width=7, no_wrap=True, justify="right")
    overview.add_column(width=18, no_wrap=True)
    overview.add_column(width=20, no_wrap=True)

    score_col = f"[{_score_color(report.avg_stoi_score)}]{report.avg_stoi_score:.1f}%[/{_score_color(report.avg_stoi_score)}]"
    hit_col   = f"[{GREEN if hit_pct >= 70 else YELLOW if hit_pct >= 40 else RED}]{hit_pct:.1f}%[/{GREEN if hit_pct >= 70 else YELLOW if hit_pct >= 40 else RED}]"
    eff_col   = f"[{GREEN if eff_pct >= 70 else YELLOW if eff_pct >= 40 else RED}]{eff_pct:.1f}%[/{GREEN if eff_pct >= 70 else YELLOW if eff_pct >= 40 else RED}]"

    overview.add_row("  含屎量",    score_col, stoi_label,                 _bar(report.avg_stoi_score, 100, 20, invert=False))
    overview.add_row("  缓存命中",  hit_col,   "",                         _bar(hit_pct, 100, 20, invert=True))
    overview.add_row("  有效输出",  eff_col,   f"[dim]({report.valid_turns} scored turns)[/dim]", _bar(eff_pct, 100, 20, invert=True))
    overview.add_row("  实际花费",  _fmt_dollars(report.total_cost_actual), "", "")
    overview.add_row("  节省费用",  f"[{GREEN}]{_fmt_dollars(report.total_cost_saved)}[/{GREEN}]", "[dim](via cache)[/dim]", "")
    if report.waste_cost > 0:
        overview.add_row(
            "  无效花费",
            f"[{RED}]{_fmt_dollars(report.waste_cost)}[/{RED}]",
            "[dim](invalid outputs)[/dim]",
            "",
        )
    console.print(overview)

    # ── Issues ────────────────────────────────────────────────────────────────
    issues = report.issues or []
    console.print(f"\n[bold {AMBER}]🔍 问题发现[/bold {AMBER}]  [dim]({len(issues)}个)[/dim]")

    if not issues:
        console.print(f"  [{GREEN}]✅  未发现显著问题[/{GREEN}]")
    else:
        for issue in issues:
            sev   = issue.get("severity", "MED")
            color = SEVERITY_COLOR.get(sev, DIM)
            label = SEVERITY_LABEL.get(sev, "MED ")
            title  = issue.get("title", "")
            detail = issue.get("detail", "")
            fix    = issue.get("fix", "")
            console.print(f"  [{color}][{label}][/{color}] [bold white]{title}[/bold white]")
            if detail:
                console.print(f"         [dim]{detail}[/dim]")
            if fix:
                console.print(f"         [dim]修复建议[/dim] → [italic]{fix}[/italic]")
            console.print()

    # ── Suggestions ───────────────────────────────────────────────────────────
    suggestions = report.llm_suggestions or _rule_based_suggestions(report)
    label_src   = "LLM generated" if report.llm_suggestions else "rule-based"
    console.print(f"[bold {AMBER}]💡 改进建议[/bold {AMBER}]  [dim]({label_src})[/dim]")
    for i, sug in enumerate(suggestions, 1):
        console.print(f"  [dim]{i}.[/dim] {sug}")

    # ── Sparkline trend ───────────────────────────────────────────────────────
    scored_turns = [
        t for t in report.turns
        if t.role == "assistant" and not t.is_stub and not t.is_baseline
    ]
    if scored_turns:
        console.print(f"\n[bold {AMBER}]📈 多轮趋势[/bold {AMBER}]  [dim](last {min(20, len(scored_turns))} turns)[/dim]")
        scores = [t.stoi_score for t in scored_turns]
        spark  = _sparkline(scores, 20)
        avg_s  = sum(scores) / len(scores)
        last_s = scores[-1]
        spark_color = _score_color(avg_s)
        console.print(
            f"  [{spark_color}]{spark}[/{spark_color}]"
            f"  [dim]均值[/dim] [{_score_color(avg_s)}]{avg_s:.1f}%[/{_score_color(avg_s)}]"
            f"  [dim]最新[/dim] [{_score_color(last_s)}]{last_s:.1f}%[/{_score_color(last_s)}]"
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    console.print()
    console.rule(style="dim")
    console.print("[dim]运行 stoi compare 查看优化前后对比[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
#  HTML Renderer
# ═══════════════════════════════════════════════════════════════════════════════

def _h(text: str) -> str:
    """HTML-escape a string."""
    return _html.escape(str(text))


def _severity_badge(sev: str) -> str:
    colors = {
        "HIGH": ("background:#fef2f2;color:#dc2626;border:1px solid #fca5a5", "HIGH"),
        "MED":  ("background:#fef3c7;color:#d97706;border:1px solid #fcd34d", "MED"),
        "LOW":  ("background:#f0f9ff;color:#0284c7;border:1px solid #bae6fd", "LOW"),
    }
    style, label = colors.get(sev, colors["LOW"])
    return f'<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;{style}">{label}</span>'


def _html_bar(pct: float, *, invert: bool = False, height: int = 8) -> str:
    """Horizontal progress bar as inline HTML."""
    pct = min(max(pct, 0), 100)
    if invert:
        color = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 40 else "#ef4444"
    else:
        color = "#22c55e" if pct < 30 else "#f59e0b" if pct < 50 else "#f97316" if pct < 75 else "#ef4444"
    return (
        f'<div style="background:#e2e8f0;border-radius:4px;height:{height}px;width:100%;overflow:hidden">'
        f'<div style="background:{color};height:100%;width:{pct:.1f}%;transition:width .3s"></div>'
        f'</div>'
    )


def render_html(report: STOIReport, output_path: Path) -> Path:
    """Generate a self-contained HTML report and write it to output_path."""
    output_path = Path(output_path)
    date_str  = report.generated_at[:10] if report.generated_at else datetime.now().strftime("%Y-%m-%d")
    _, level_emoji = _get_level(report.avg_stoi_score)

    # ── scored turns for chart ────────────────────────────────────────────────
    scored_turns = [
        t for t in report.turns
        if t.role == "assistant" and not t.is_stub and not t.is_baseline
    ]
    chart_turns = scored_turns[-20:]  # last 20

    suggestions = report.llm_suggestions or _rule_based_suggestions(report)

    # ─────────────────────────────────────────────────────────────────────────
    # Build HTML sections
    # ─────────────────────────────────────────────────────────────────────────

    # § 1 — Header
    sec_header = f"""
<div class="header">
  <div class="header-title">💩 STOI 含屎量分析报告</div>
  <div class="header-meta">
    <span>会话：<strong>{_h(report.session_name)}</strong></span>
    <span>日期：{_h(date_str)}</span>
    <span>轮次：{report.total_turns}</span>
    <span>模型：{_h(report.model or 'unknown')}</span>
    <span>来源：{_h(report.source_tool)}</span>
  </div>
</div>"""

    # § 2 — At-a-Glance
    stoi_color  = "#dc2626" if report.avg_stoi_score >= 75 else "#f97316" if report.avg_stoi_score >= 50 else "#f59e0b" if report.avg_stoi_score >= 30 else "#22c55e"
    hit_color   = "#22c55e" if report.avg_cache_hit_rate >= 70 else "#f59e0b" if report.avg_cache_hit_rate >= 40 else "#ef4444"
    eff_color   = "#22c55e" if report.effectiveness_rate >= 70 else "#f59e0b" if report.effectiveness_rate >= 40 else "#ef4444"

    sec_glance = f"""
<div class="card glance-box">
  <div class="glance-title">📊 一眼总览</div>
  <div class="glance-metrics">
    <div class="glance-metric">
      <div class="glance-value" style="color:{stoi_color}">{report.avg_stoi_score:.1f}%</div>
      <div class="glance-label">含屎量 {level_emoji} {_h(report.stoi_level)}</div>
      {_html_bar(report.avg_stoi_score, invert=False, height=6)}
    </div>
    <div class="glance-metric">
      <div class="glance-value" style="color:{hit_color}">{report.avg_cache_hit_rate:.1f}%</div>
      <div class="glance-label">缓存命中率</div>
      {_html_bar(report.avg_cache_hit_rate, invert=True, height=6)}
    </div>
    <div class="glance-metric">
      <div class="glance-value" style="color:{eff_color}">{report.effectiveness_rate:.1f}%</div>
      <div class="glance-label">有效输出率</div>
      {_html_bar(report.effectiveness_rate, invert=True, height=6)}
    </div>
  </div>
</div>"""

    # § 3 — Stats row
    def stat_card(label: str, value: str, sub: str = "", color: str = "#0f172a") -> str:
        return f"""
<div class="stat-card">
  <div class="stat-value" style="color:{color}">{value}</div>
  <div class="stat-label">{label}</div>
  {f'<div class="stat-sub">{sub}</div>' if sub else ''}
</div>"""

    sec_stats = f"""
<div class="stats-row">
  {stat_card("总轮次", str(report.total_turns))}
  {stat_card("有效轮次", str(report.valid_turns))}
  {stat_card("实际花费", _fmt_dollars(report.total_cost_actual), "实际支出")}
  {stat_card("节省费用", _fmt_dollars(report.total_cost_saved), "via cache", color="#16a34a")}
  {stat_card("无效花费", _fmt_dollars(report.waste_cost), "invalid outputs", color="#dc2626")}
</div>"""

    # § 4 — Problems
    issues = report.issues or []
    issue_cards = ""
    for issue in issues:
        sev   = issue.get("severity", "MED")
        bg    = {"HIGH": "#fef2f2", "MED": "#fef3c7", "LOW": "#eff6ff"}.get(sev, "#f8fafc")
        border= {"HIGH": "#fca5a5", "MED": "#fcd34d", "LOW": "#bfdbfe"}.get(sev, "#e2e8f0")
        issue_cards += f"""
<div class="issue-card" style="background:{bg};border-color:{border}">
  <div class="issue-header">
    {_severity_badge(sev)}
    <span class="issue-title">{_h(issue.get('title',''))}</span>
  </div>
  <div class="issue-detail">{_h(issue.get('detail',''))}</div>
  {f'<div class="issue-fix">修复建议 → {_h(issue.get("fix",""))}</div>' if issue.get('fix') else ''}
  {f'<div class="issue-impact">预计影响：{_h(issue.get("impact",""))}</div>' if issue.get('impact') else ''}
</div>"""

    if not issue_cards:
        issue_cards = '<div class="no-issues">✅ 未发现显著问题，含屎量正常</div>'

    sec_issues = f"""
<div class="section">
  <div class="section-title">🔍 问题发现 <span class="section-count">{len(issues)}个</span></div>
  {issue_cards}
</div>"""

    # § 5 — Turn-by-turn chart
    chart_rows = ""
    max_score = max((t.stoi_score for t in chart_turns), default=100) or 100
    for t in chart_turns:
        bar_w = t.stoi_score / max_score * 100
        bar_color = "#22c55e" if t.stoi_score < 30 else "#f59e0b" if t.stoi_score < 50 else "#f97316" if t.stoi_score < 75 else "#ef4444"
        fb_icon = {"valid": "✅", "invalid": "❌", "partial": "🟡", "unknown": ""}.get(t.token_effectiveness, "")
        chart_rows += f"""
<div class="chart-row">
  <div class="chart-label">T{t.turn_index}</div>
  <div class="chart-bar-wrap">
    <div class="chart-bar" style="width:{bar_w:.1f}%;background:{bar_color}"></div>
  </div>
  <div class="chart-score" style="color:{bar_color}">{t.stoi_score:.1f}%</div>
  <div class="chart-fb">{fb_icon}</div>
</div>"""

    if not chart_rows:
        chart_rows = '<div class="no-issues">暂无评分轮次数据</div>'

    sec_chart = f"""
<div class="section">
  <div class="section-title">📈 逐轮含屎量 <span class="section-count">last {len(chart_turns)} turns</span></div>
  <div class="chart-container">
    {chart_rows}
  </div>
</div>"""

    # § 6 — AI Suggestions
    sug_cards = ""
    for i, sug in enumerate(suggestions, 1):
        sug_cards += f"""
<div class="sug-card">
  <div class="sug-num">{i}</div>
  <div class="sug-text">{_h(sug)}</div>
</div>"""

    src_label = "AI 生成" if report.llm_suggestions else "规则推断"
    sec_suggestions = f"""
<div class="section">
  <div class="section-title">💡 改进建议 <span class="section-count">{src_label}</span></div>
  {sug_cards}
</div>"""

    # § 7 — Feedback breakdown
    total_fb = (
        report.valid_turns_count + report.invalid_turns_count +
        report.partial_turns_count + report.unknown_turns_count
    ) or 1
    fb_data = [
        ("valid",   report.valid_turns_count,   "有效", "#22c55e"),
        ("invalid", report.invalid_turns_count, "无效", "#ef4444"),
        ("partial", report.partial_turns_count, "部分", "#f59e0b"),
        ("unknown", report.unknown_turns_count, "未知", "#94a3b8"),
    ]
    fb_bars = ""
    for _, count, label, color in fb_data:
        pct = count / total_fb * 100
        fb_bars += f"""
<div class="fb-row">
  <div class="fb-label">{label}</div>
  <div class="fb-bar-wrap">
    <div class="fb-bar" style="width:{pct:.1f}%;background:{color}"></div>
  </div>
  <div class="fb-pct">{pct:.1f}%</div>
  <div class="fb-count">({count})</div>
</div>"""

    sec_feedback = f"""
<div class="section">
  <div class="section-title">🏷️ 反馈分布</div>
  <div class="fb-container">
    {fb_bars}
  </div>
</div>"""

    # § 8 — Footer
    sec_footer = """
<div class="footer">
  Generated by <strong>STOI v2.0</strong> — Shit Token On Investment
</div>"""

    # ─────────────────────────────────────────────────────────────────────────
    # CSS + full HTML assembly
    # ─────────────────────────────────────────────────────────────────────────
    css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f8fafc;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  padding: 24px 16px;
}
.wrapper { max-width: 800px; margin: 0 auto; }

/* Header */
.header {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: white;
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 20px;
}
.header-title { font-size: 22px; font-weight: 700; margin-bottom: 10px; }
.header-meta  { display: flex; flex-wrap: wrap; gap: 16px; color: #94a3b8; font-size: 13px; }
.header-meta strong { color: #f8fafc; }

/* Cards */
.card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

/* At-a-Glance */
.glance-box {
  background: linear-gradient(135deg, #fef3c7 0%, #fef9ec 100%);
  border: 1px solid #f59e0b;
}
.glance-title { font-size: 14px; font-weight: 600; color: #92400e; margin-bottom: 16px; }
.glance-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.glance-metric { }
.glance-value { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.glance-label { font-size: 12px; color: #78716c; margin-bottom: 8px; }

/* Stats row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 12px;
  text-align: center;
}
.stat-value { font-size: 18px; font-weight: 700; }
.stat-label { font-size: 11px; color: #64748b; margin-top: 4px; }
.stat-sub   { font-size: 10px; color: #94a3b8; }

/* Section */
.section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 15px; font-weight: 600; color: #0f172a;
  margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
}
.section-count { font-size: 12px; color: #64748b; font-weight: 400; }

/* Issue cards */
.issue-card {
  border: 1px solid;
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.issue-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.issue-title  { font-weight: 600; font-size: 14px; }
.issue-detail { font-size: 13px; color: #475569; margin-bottom: 4px; }
.issue-fix    { font-size: 12px; color: #7c3aed; margin-top: 4px; }
.issue-impact { font-size: 12px; color: #64748b; margin-top: 2px; }
.no-issues    {
  background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 6px; padding: 12px 14px; color: #16a34a; font-size: 13px;
}

/* Turn chart */
.chart-container { display: flex; flex-direction: column; gap: 5px; }
.chart-row { display: grid; grid-template-columns: 32px 1fr 50px 20px; gap: 8px; align-items: center; }
.chart-label { font-size: 11px; color: #94a3b8; text-align: right; }
.chart-bar-wrap { background: #f1f5f9; border-radius: 3px; height: 14px; overflow: hidden; }
.chart-bar { height: 100%; border-radius: 3px; transition: width .3s; }
.chart-score { font-size: 11px; font-weight: 600; text-align: right; }
.chart-fb { font-size: 11px; text-align: center; }

/* Suggestions */
.sug-card {
  display: flex; gap: 12px; align-items: flex-start;
  background: #eff6ff; border: 1px solid #bfdbfe;
  border-radius: 6px; padding: 12px 14px; margin-bottom: 8px;
}
.sug-num {
  background: #3b82f6; color: white;
  border-radius: 50%; width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.sug-text { font-size: 13px; color: #1e40af; }

/* Feedback */
.fb-container { display: flex; flex-direction: column; gap: 8px; }
.fb-row { display: grid; grid-template-columns: 40px 1fr 50px 40px; gap: 8px; align-items: center; }
.fb-label { font-size: 12px; color: #64748b; text-align: right; }
.fb-bar-wrap { background: #f1f5f9; border-radius: 3px; height: 12px; overflow: hidden; }
.fb-bar { height: 100%; border-radius: 3px; }
.fb-pct { font-size: 12px; font-weight: 600; text-align: right; color: #475569; }
.fb-count { font-size: 11px; color: #94a3b8; }

/* Footer */
.footer { text-align: center; color: #94a3b8; font-size: 12px; padding: 16px 0 4px; }
"""

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STOI 含屎量分析报告 — {_h(report.session_name)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="wrapper">
{sec_header}
{sec_glance}
{sec_stats}
{sec_issues}
{sec_chart}
{sec_suggestions}
{sec_feedback}
{sec_footer}
</div>
</body>
</html>"""

    output_path.write_text(html_doc, encoding="utf-8")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  Unified entry point
# ═══════════════════════════════════════════════════════════════════════════════

def render_report(
    report: STOIReport,
    format: str = "cli",
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Unified render entry.

    Args:
        report:     STOIReport from stoi_core.analyze()
        format:     'cli' | 'html' | 'both'
        output_dir: Directory for HTML output (defaults to /tmp)

    Returns:
        Path to HTML file if format includes 'html', else None.
    """
    if output_dir is None:
        output_dir = Path("/tmp")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path: Optional[Path] = None

    if format in ("cli", "both"):
        render_cli(report)

    if format in ("html", "both"):
        safe_name = (report.session_id or "session").replace("/", "_").replace(" ", "_")
        ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"stoi_report_{safe_name}_{ts_suffix}.html"
        html_path = render_html(report, output_dir / filename)

    return html_path


# ─── CLI smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from stoi_core import analyze, find_claude_sessions

    files = find_claude_sessions(1)
    if files:
        r = analyze(files[0])
        path = render_report(r, format="both", output_dir=Path("/tmp"))
        if path:
            print(f"\nHTML saved → {path}")
    else:
        print("No Claude sessions found — generating demo report")
        demo = STOIReport(
            session_id="demo",
            session_name="demo/session",
            source_tool="claude_code",
            model="claude-sonnet-4-5",
            generated_at=datetime.now().isoformat(),
            total_turns=10,
            valid_turns=8,
            avg_cache_hit_rate=45.0,
            avg_stoi_score=28.5,
            stoi_level="CLEAN",
            valid_turns_count=5,
            invalid_turns_count=2,
            partial_turns_count=1,
            unknown_turns_count=0,
            effectiveness_rate=71.4,
            total_cost_actual=0.0042,
            total_cost_no_cache=0.0188,
            total_cost_saved=0.0146,
            waste_cost=0.0009,
        )
        path = render_report(demo, format="both", output_dir=Path("/tmp"))
        if path:
            print(f"\nHTML saved → {path}")
