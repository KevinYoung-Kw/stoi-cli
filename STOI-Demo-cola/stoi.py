#!/usr/bin/env python3
"""
stoi.py — STOI 主命令行入口
Shit Token On Investment

用法:
  python3 stoi.py start      # 启动代理
  python3 stoi.py stats      # 打印报告 + TTS
  python3 stoi.py blame      # 找出 Cache 元凶
  python3 stoi.py analyze    # 离线分析 Claude Code 会话
  python3 stoi.py tui        # 启动 TUI 仪表盘
  python3 stoi.py trend      # ASCII 趋势图
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

LOG_FILE = Path("~/.stoi/sessions.jsonl").expanduser()
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

STOI_LOGO = r"""
 ███████╗████████╗ ██████╗ ██╗
 ██╔════╝╚══██╔══╝██╔═══██╗██║
 ███████╗   ██║   ██║   ██║██║
 ╚════██║   ██║   ██║   ██║██║
 ███████║   ██║   ╚██████╔╝██║
 ╚══════╝   ╚═╝    ╚═════╝ ╚═╝
"""

COMMANDS = {
    "start":   "启动 API 代理（拦截 Claude Code 请求）",
    "stats":   "打印含屎量统计报告 + TTS 播报",
    "blame":   "扫描 System Prompt，找 Cache Miss 元凶",
    "analyze": "离线分析 ~/.claude/projects/ 会话文件",
    "tui":     "启动实时 TUI 仪表盘",
    "trend":   "打印多轮含屎量趋势 ASCII 图",
}


def print_logo():
    console.print(Text(STOI_LOGO, style="bold #FFB800"))
    console.print(
        "  [bold white]Shit Token On Investment[/bold white]  "
        "[dim]— 含屎量实时监控系统 v1.1[/dim]\n"
    )


def speak(level: str):
    """macOS TTS 播报"""
    from stoi_engine import TTS_MESSAGES
    msg = TTS_MESSAGES.get(level, "")
    if msg:
        try:
            subprocess.Popen(["say", "-v", "Ting-Ting", msg])
        except Exception:
            pass


def load_log() -> list[dict]:
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
        return records
    except Exception:
        return []


# ── start ────────────────────────────────────────────────────────────────────
def cmd_start():
    print_logo()
    console.print("[bold #FFB800]▶ 启动 STOI 代理...[/bold #FFB800]\n")

    proxy_path = Path(__file__).parent / "stoi_proxy.py"
    if not proxy_path.exists():
        # 尝试从 Hackathon 目录复制过来
        src = Path("/Users/kevinyoung/.cola/outputs/STOI-Hackathon-路演-PPT/stoi_proxy.py")
        if src.exists():
            import shutil
            shutil.copy(src, proxy_path)
            console.print(f"[dim]已从 {src} 复制代理脚本[/dim]")

    if proxy_path.exists():
        console.print(
            f"[green]✓ 代理脚本就绪[/green]: {proxy_path}\n"
            "\n运行以下命令启动代理:\n"
            f"  [bold white]python3 {proxy_path}[/bold white]\n"
            "\n然后设置环境变量:\n"
            "  [bold white]export ANTHROPIC_BASE_URL=http://localhost:8888[/bold white]\n"
        )
    else:
        console.print("[red]✗ 未找到 stoi_proxy.py[/red]")
        console.print("[dim]请先将 stoi_proxy.py 放到当前目录[/dim]")


# ── stats ────────────────────────────────────────────────────────────────────
def cmd_stats():
    from stoi_engine import SHIT_EMOJI, SHIT_THRESHOLDS, get_score_color

    print_logo()
    records = load_log()

    if not records:
        console.print(Panel(
            "📭 还没有记录。\n\n"
            "先运行以下任一命令产生数据:\n"
            "  [bold white]python3 stoi.py analyze[/bold white]  — 离线分析 Claude Code 会话\n"
            "  [bold white]python3 stoi.py start[/bold white]    — 启动代理拦截实时请求",
            title="[bold #FFB800]💩 STOI 统计[/bold #FFB800]",
            border_style="#FFB800",
        ))
        return

    total_input   = sum(r["stoi"]["input_tokens"] for r in records)
    total_wasted  = sum(r["stoi"]["wasted_tokens"] for r in records)
    total_output  = sum(r["stoi"]["output_tokens"] for r in records)
    total_cache   = sum(r["stoi"]["cache_read"] for r in records)
    avg_score     = round(sum(r["stoi"]["stoi_score"] for r in records) / len(records), 1)
    hit_rate      = round(total_cache / total_input * 100, 1) if total_input > 0 else 0.0

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= avg_score < hi:
            level = lvl
            break

    color = get_score_color(avg_score)
    emoji = SHIT_EMOJI[level]

    # 主统计表格
    table = Table(
        title="💩 STOI 含屎量报告",
        box=box.DOUBLE_EDGE,
        border_style="#FFB800",
        title_style="bold #FFB800",
        show_header=False,
        padding=(0, 2),
    )
    table.add_column("指标", style="bold #FFB800", width=20)
    table.add_column("数值", style="white bold", width=20)

    table.add_row("会话总数",   f"{len(records)} 次")
    table.add_row(
        "平均含屎量",
        Text(f"{avg_score}%  {emoji}  {level}", style=f"bold {color}"),
    )
    table.add_row("缓存命中率",  Text(f"{hit_rate}%", style="green bold"))
    table.add_row("总输入消耗",  f"{total_input:,} tokens")
    table.add_row("白白浪费",    Text(f"{total_wasted:,} tokens  💩", style="red bold"))
    table.add_row("有效输出",    f"{total_output:,} tokens")

    console.print(table)

    # 等级分布
    level_counts: dict[str, int] = {}
    for r in records:
        lvl = r["stoi"]["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    console.print("\n[bold #FFB800]等级分布:[/bold #FFB800]")
    for lvl in ["CLEAN", "MILD_SHIT", "SHIT_OVERFLOW", "DEEP_SHIT"]:
        count = level_counts.get(lvl, 0)
        if count > 0:
            pct = round(count / len(records) * 100)
            bar = "█" * (pct // 5)
            em = SHIT_EMOJI[lvl]
            c = get_score_color({"CLEAN": 10, "MILD_SHIT": 40, "SHIT_OVERFLOW": 60, "DEEP_SHIT": 85}[lvl])
            console.print(f"  [{c}]{em} {lvl:<20}[/{c}]  {count:>4} 次  [{c}]{bar}[/{c}]  {pct}%")

    # TTS 播报
    console.print(f"\n[dim]🔊 语音播报: {level}...[/dim]")
    speak(level)


# ── blame ────────────────────────────────────────────────────────────────────
def cmd_blame():
    from stoi_engine import l3_cache_blame, l1_syntax_waste

    print_logo()
    console.print(Panel(
        "📋 请将 System Prompt 粘贴到下方\n"
        "[dim]输入完成后，在新行输入 END 并回车[/dim]",
        title="[bold #FFB800]🔍 STOI Blame — Cache 元凶分析[/bold #FFB800]",
        border_style="#FFB800",
    ))

    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == "END":
            break
        lines.append(line)

    prompt = "\n".join(lines)

    if not prompt.strip():
        console.print("[yellow]⚠ 未输入内容[/yellow]")
        return

    l3 = l3_cache_blame(prompt)
    l1 = l1_syntax_waste(prompt)

    console.print("\n[bold #FFB800]═══ L3 缓存击穿分析 ═══[/bold #FFB800]\n")

    if l3["culprits"]:
        for c in l3["culprits"]:
            sev_color = {
                "HIGH": "red",
                "MEDIUM": "dark_orange",
                "LOW": "yellow",
            }.get(c["severity"], "white")
            console.print(f"  [{sev_color}]⚠ {c['desc']}[/{sev_color}]")
            console.print(f"    [dim]原因: {c['detail']}[/dim]")
            console.print(f"    [green]修复: {c['fix']}[/green]")
            if c["matches"]:
                console.print(f"    [dim]样例: {c['matches'][0]!r}[/dim]")
            console.print()
    else:
        console.print("  [green]✓ 未发现 Cache Miss 元凶[/green]")

    console.print(f"  综合严重度: [bold]{l3['severity']}[/bold]")
    console.print(f"  修复建议: {l3['suggestion']}\n")

    console.print("[bold #FFB800]═══ L1 语法废话分析 ═══[/bold #FFB800]\n")
    if l1["examples"]:
        for ex in l1["examples"]:
            console.print(f"  [yellow]⚠ {ex}[/yellow]")
        console.print(f"\n  预估浪费 token: [red]~{l1['token_estimate']}[/red]")
        console.print(f"  建议: {l1['suggestion']}\n")
    else:
        console.print("  [green]✓ 语法格式干净，无废话[/green]\n")


# ── analyze ──────────────────────────────────────────────────────────────────
def cmd_analyze(args: list[str]):
    from stoi_analyze import cmd_analyze as _analyze
    _analyze(args)


# ── tui ──────────────────────────────────────────────────────────────────────
def cmd_tui():
    from stoi_tui import main as tui_main
    tui_main()


# ── trend ────────────────────────────────────────────────────────────────────
def cmd_trend():
    from stoi_engine import get_score_color, SHIT_EMOJI

    print_logo()
    records = load_log()

    if not records:
        console.print("[yellow]📭 无数据。先运行 stoi analyze 或 stoi start[/yellow]")
        return

    scores = [r["stoi"]["stoi_score"] for r in records[-30:]]
    times  = [r.get("ts", "")[:16] for r in records[-30:]]

    console.print("[bold #FFB800]📈 含屎量趋势（最近 30 轮）[/bold #FFB800]\n")

    # ASCII 柱状图 (垂直)
    height = 10
    max_score = 100.0
    bar_width = 2

    # 绘制
    col_width = max(bar_width + 1, 4)
    rows = []
    for row_i in range(height, 0, -1):
        threshold = (row_i / height) * max_score
        row_str = f"  {threshold:3.0f}% │"
        for score in scores:
            if score >= threshold:
                color = get_score_color(score)
                row_str += f"[{color}]{'█' * bar_width}[/{color}] "
            else:
                row_str += "   "
        rows.append(row_str)

    for r in rows:
        console.print(r)

    # X 轴
    console.print("       └" + "───" * len(scores))

    # 最新数据点标注
    console.print()
    if scores:
        latest_score = scores[-1]
        color = get_score_color(latest_score)
        console.print(f"  最新: [{color}]{latest_score}%[/{color}]  ({times[-1] if times else '—'})")
        avg = sum(scores) / len(scores)
        color_avg = get_score_color(avg)
        console.print(f"  均值: [{color_avg}]{avg:.1f}%[/{color_avg}]")
        console.print(f"  最高: [red]{max(scores)}%[/red]")
        console.print(f"  最低: [green]{min(scores)}%[/green]")


# ── help ─────────────────────────────────────────────────────────────────────
def cmd_help():
    print_logo()
    console.print("[bold #FFB800]用法:[/bold #FFB800]\n")

    table = Table(box=box.SIMPLE, border_style="dim", show_header=False, padding=(0, 2))
    table.add_column("命令", style="bold white", width=16)
    table.add_column("描述", style="dim", width=50)

    for cmd, desc in COMMANDS.items():
        table.add_row(f"stoi {cmd}", desc)

    console.print(table)
    console.print()


# ── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        cmd_help()
        return

    cmd = args[0].lower()
    rest = args[1:]

    cmd_map = {
        "start":   cmd_start,
        "stats":   cmd_stats,
        "blame":   cmd_blame,
        "tui":     cmd_tui,
        "trend":   cmd_trend,
        "help":    cmd_help,
        "--help":  cmd_help,
        "-h":      cmd_help,
    }

    if cmd == "analyze":
        cmd_analyze(rest)
    elif cmd in cmd_map:
        cmd_map[cmd]()
    else:
        console.print(f"[red]未知命令: {cmd}[/red]")
        cmd_help()


if __name__ == "__main__":
    main()
