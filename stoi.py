#!/usr/bin/env python3
"""
stoi — Shit Token On Investment
Token 效率分析工具

命令：
  stoi report          分析最新 session，输出完整报告
  stoi report --html   同上，并生成 HTML 报告
  stoi report --all    分析所有历史 session 汇总
  stoi report --llm    开启 LLM 深度建议
  stoi start           启动实时监控代理
  stoi config          配置 LLM Provider
  stoi compare         before/after 效果对比
"""

import sys
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

LOGO = r"""
 ███████╗████████╗ ██████╗ ██╗
 ██╔════╝╚══██╔══╝██╔═══██╗██║
 ███████╗   ██║   ██║   ██║██║
 ╚════██║   ██║   ██║   ██║██║
 ███████║   ██║   ╚██████╔╝██║
 ╚══════╝   ╚═╝    ╚═════╝ ╚═╝"""


def print_logo():
    console.print(Text(LOGO, style="bold #FFB800"))
    console.print("  [bold white]Shit Token On Investment[/bold white]  "
                  "[dim]— Token 效率分析 v2.0[/dim]\n")


# ── stoi report ───────────────────────────────────────────────────────────────
def cmd_report(args: list[str]) -> None:
    from stoi_core import analyze, find_claude_sessions, find_opencode_sessions
    from stoi_report import render_cli, render_html, render_report

    html_mode = "--html" in args
    llm_mode  = "--llm" in args
    all_mode  = "--all" in args

    print_logo()

    if all_mode:
        _report_all(html_mode, llm_mode)
        return

    # 找 session — 自动选最新或交互选择
    session_path = None
    source = "claude_code"

    # 如果直接传了路径
    direct = [a for a in args if not a.startswith("--") and Path(a).exists()]
    if direct:
        session_path = Path(direct[0])
    else:
        # 自动选最新
        files = find_claude_sessions(1)
        if files:
            session_path = files[0]
            console.print(f"[dim]自动选取最新 session: {session_path.parent.name[:20]}/{session_path.stem[:16]}[/dim]\n")
        else:
            console.print("[yellow]未找到 Claude Code session[/yellow]")
            console.print("[dim]请先使用 Claude Code，或运行 stoi start 开启实时监控[/dim]")
            return

    # 分析
    with console.status("[dim]分析中...[/dim]", spinner="dots"):
        report = analyze(session_path, source=source, llm_enabled=llm_mode)

    if not report.valid_turns:
        console.print("[yellow]session 为空或无法解析[/yellow]")
        return

    # 输出报告
    render_cli(report)

    # HTML
    if html_mode:
        html_path = render_html(report, Path("~/.stoi/report.html").expanduser())
        console.print(f"\n[green]✅ HTML 报告已生成:[/green] {html_path}")
        try:
            subprocess.Popen(["open", str(html_path)])
        except Exception:
            pass


def _report_all(html_mode: bool, llm_mode: bool) -> None:
    """分析所有历史 session，输出汇总"""
    from stoi_core import analyze, find_claude_sessions, STOIReport
    from stoi_report import render_html

    files = find_claude_sessions(10)
    if not files:
        console.print("[yellow]未找到任何 session[/yellow]")
        return

    console.print(f"[bold]分析最近 {len(files)} 个 session...[/bold]\n")

    all_reports = []
    for f in files:
        with console.status(f"[dim]{f.stem[:20]}...[/dim]", spinner="dots"):
            r = analyze(f, llm_enabled=False)
        if r.valid_turns > 0:
            all_reports.append(r)

    if not all_reports:
        console.print("[yellow]所有 session 均为空[/yellow]")
        return

    # 汇总表
    table = Table(title="📊 Session 汇总", box=box.ROUNDED,
                  header_style="bold #FFB800", border_style="#FFB800")
    table.add_column("Session",     style="dim",   width=28)
    table.add_column("轮次",         justify="right", width=6)
    table.add_column("含屎量",       justify="right", width=8)
    table.add_column("命中率",       justify="right", width=8)
    table.add_column("有效率",       justify="right", width=8)
    table.add_column("花费",         justify="right", width=10)
    table.add_column("等级",         width=14)

    for r in all_reports:
        
        lc = LEVEL_COLORS.get(r.stoi_level, "white")
        em = LEVEL_EMOJI.get(r.stoi_level, "")
        table.add_row(
            r.session_name[:27],
            str(r.valid_turns),
            f"[{lc}]{r.avg_stoi_score:.1f}%[/{lc}]",
            f"{r.avg_cache_hit_rate:.1f}%",
            f"{r.effectiveness_rate:.1f}%",
            f"${r.total_cost_actual:.4f}",
            f"{em} {r.stoi_level}",
        )

    console.print(table)

    # 汇总统计
    total_cost = sum(r.total_cost_actual for r in all_reports)
    total_waste = sum(r.waste_cost for r in all_reports)
    avg_stoi = sum(r.avg_stoi_score for r in all_reports) / len(all_reports)
    console.print(f"\n  [dim]总花费[/dim] [white]${total_cost:.4f}[/white]  "
                  f"[dim]无效输出浪费[/dim] [red]${total_waste:.4f}[/red]  "
                  f"[dim]平均含屎量[/dim] [white]{avg_stoi:.1f}%[/white]\n")


# ── stoi start ────────────────────────────────────────────────────────────────
def cmd_start() -> None:
    print_logo()
    proxy_path = Path(__file__).parent / "stoi_proxy.py"
    if not proxy_path.exists():
        console.print("[red]未找到 stoi_proxy.py[/red]")
        return
    console.print("[bold #FFB800]▶ 启动实时监控代理...[/bold #FFB800]")
    console.print("[dim]自动切换 ANTHROPIC_BASE_URL → 退出后自动恢复[/dim]\n")
    subprocess.run([sys.executable, str(proxy_path)])


# ── stoi config ───────────────────────────────────────────────────────────────
def cmd_config(args: list[str]) -> None:
    print_logo()
    from stoi_config import run_onboard, show_config
    if "--show" in args:
        show_config()
    else:
        run_onboard()


# ── stoi compare ──────────────────────────────────────────────────────────────
def cmd_compare(args: list[str]) -> None:
    """before/after 对比：选两个 session，展示含屎量变化"""
    from stoi_core import analyze, find_claude_sessions
    

    print_logo()
    files = find_claude_sessions(10)
    if len(files) < 2:
        console.print("[yellow]需要至少 2 个 session 才能对比[/yellow]")
        return

    console.print("[bold white]选择 Before Session（优化前）[/bold white]\n")
    before_path = _pick_session(files)
    if not before_path:
        return

    console.print("\n[bold white]选择 After Session（优化后）[/bold white]\n")
    after_path = _pick_session(files)
    if not after_path:
        return

    with console.status("[dim]分析中...[/dim]", spinner="dots"):
        before = analyze(before_path)
        after  = analyze(after_path)

    # 对比展示
    console.print()
    console.print(Panel.fit("[bold #FFB800]📊 Before / After 对比[/bold #FFB800]",
                            border_style="#FFB800"))
    console.print()

    metrics = [
        ("含屎量",   before.avg_stoi_score,    after.avg_stoi_score,    "%",  True),
        ("缓存命中", before.avg_cache_hit_rate, after.avg_cache_hit_rate, "%",  False),
        ("输出有效", before.effectiveness_rate, after.effectiveness_rate, "%",  False),
        ("实际花费", before.total_cost_actual,  after.total_cost_actual,  "$",  True),
        ("无效浪费", before.waste_cost,          after.waste_cost,         "$",  True),
    ]

    for name, bv, av, unit, lower_better in metrics:
        delta = av - bv
        improved = (delta < 0) if lower_better else (delta > 0)
        color = "green" if improved else "red" if delta != 0 else "white"
        arrow = "↓" if delta < 0 else "↑" if delta > 0 else "→"
        fmt = ".4f" if unit == "$" else ".1f"
        console.print(
            f"  [dim]{name:<10}[/dim]  "
            f"[white]{bv:{fmt}}{unit}[/white]  →  "
            f"[{color}]{av:{fmt}}{unit}[/{color}]  "
            f"[{color}]{arrow} {abs(delta):{fmt}}{unit}[/{color}]"
        )

    console.print()
    improvement = (before.avg_stoi_score - after.avg_stoi_score) / max(before.avg_stoi_score, 1) * 100
    if improvement > 0:
        console.print(f"  [green bold]✅ 含屎量下降 {improvement:.0f}%，优化有效！[/green bold]")
    elif improvement < -5:
        console.print(f"  [red]⚠ 含屎量上升 {-improvement:.0f}%，需要检查[/red]")
    else:
        console.print(f"  [dim]变化不明显（{improvement:+.0f}%）[/dim]")
    console.print()


def _pick_session(files):
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("#", style="bold", width=4)
    table.add_column("时间", style="dim", width=14)
    table.add_column("名称", width=32)
    for i, f in enumerate(files[:10], 1):
        from datetime import datetime
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
        table.add_row(str(i), mtime, f"{f.parent.name[:16]}/{f.stem[:14]}")
    console.print(table)
    choice = Prompt.ask("请选择", choices=[str(i) for i in range(1, len(files[:10])+1)], default="1")
    return files[int(choice) - 1]


# ── stoi tui ─────────────────────────────────────────────────────────────────
def cmd_tui() -> None:
    from stoi_tui import run_tui
    run_tui()


# ── help ─────────────────────────────────────────────────────────────────────
def cmd_help() -> None:
    print_logo()
    console.print(Panel(
        "  [bold #FFB800]stoi report[/bold #FFB800]           分析最新 session\n"
        "  [bold #FFB800]stoi report --html[/bold #FFB800]    生成 HTML 报告并打开\n"
        "  [bold #FFB800]stoi report --all[/bold #FFB800]     分析所有历史 session\n"
        "  [bold #FFB800]stoi report --llm[/bold #FFB800]     开启 AI 深度建议\n"
        "  [bold #FFB800]stoi report <path>[/bold #FFB800]    分析指定 session 文件\n\n"
        "  [bold #FFB800]stoi start[/bold #FFB800]            启动实时监控代理\n"
        "  [bold #FFB800]stoi compare[/bold #FFB800]          before/after 效果对比\n"
        "  [bold #FFB800]stoi config[/bold #FFB800]           配置 LLM Provider\n"
        "  [bold #FFB800]stoi tui[/bold #FFB800]              启动交互式 TUI\n",
        title="[bold]💩 STOI — 用法[/bold]",
        border_style="#FFB800",
    ))


# ── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    cmd  = args[0] if args else "help"
    rest = args[1:]

    dispatch = {
        "report":  lambda: cmd_report(rest),
        "start":   lambda: cmd_start(),
        "config":  lambda: cmd_config(rest),
        "compare": lambda: cmd_compare(rest),
        "tui":     lambda: cmd_tui(),
        "help":    lambda: cmd_help(),
        "--help":  lambda: cmd_help(),
        "-h":      lambda: cmd_help(),
    }

    fn = dispatch.get(cmd)
    if fn:
        fn()
    else:
        console.print(f"[red]未知命令: {cmd}[/red]  运行 [bold]stoi help[/bold] 查看用法")
        sys.exit(1)


if __name__ == "__main__":
    main()
