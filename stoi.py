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
  python3 stoi.py backfill-feedback-validity  # 回填反馈型 token 有效性
  python3 stoi.py feedback-validity           # 查看反馈型 token 有效性
"""

import argparse
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
    "start":    "启动 API 代理（拦截 Claude Code 请求）",
    "stats":    "打印含屎量统计报告 + TTS 播报",
    "blame":    "扫描 System Prompt，找 Cache Miss 元凶",
    "analyze":  "离线分析 ~/.claude/projects/ 会话文件",
    "insights": "🤖 AI 深度洞察：分析含屎量并给出改进建议",
    "tui":      "启动实时 TUI 仪表盘",
    "trend":    "打印多轮含屎量趋势 ASCII 图",
    "config":   "配置 LLM Provider 和 API Key",
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
    from stoi_tui import run_tui as tui_main
    tui_main()


# ── config ───────────────────────────────────────────────────────────────────
def cmd_config():
    print_logo()
    from stoi_config import run_onboard, show_config
    import sys
    if "--show" in sys.argv:
        show_config()
    else:
        run_onboard()


# ── insights ─────────────────────────────────────────────────────────────────
def cmd_insights(args: list = None):
    print_logo()
    from stoi_analyze import parse_claude_code_session, find_recent_sessions
    from stoi_engine import analyze_session_validity
    from stoi_insights import run_insights

    args = args or []
    target = args[0] if args else None

    if target:
        path = Path(target)
        if not path.exists():
            console.print(f"[red]文件不存在: {target}[/red]")
            return
        records = parse_claude_code_session(str(path))
        session_name = path.stem
    else:
        # 用最新 session
        files = find_recent_sessions(1)
        if not files:
            console.print("[yellow]未找到 Claude Code session，请指定文件路径[/yellow]")
            console.print("用法: stoi insights [session文件路径]")
            return
        records = parse_claude_code_session(str(files[0]))
        session_name = files[0].stem

    if not records:
        console.print("[yellow]session 文件为空或无法解析[/yellow]")
        return

    records = analyze_session_validity(records)
    run_insights(records, session_name)


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


# ── feedback validity helpers ────────────────────────────────────────────────
def _print_feedback_summary(summary: dict, title: str):
    table = Table(title=title, box=box.ROUNDED, border_style="#FFB800")
    table.add_column("指标", style="cyan")
    table.add_column("数值", justify="right", style="bright_white")
    rows = [
        ("总 Prompt 数", str(summary["total_prompt_count"])),
        ("有效 Prompt 数", str(summary["valid_prompt_count"])),
        ("无效 Prompt 数", str(summary["invalid_prompt_count"])),
        ("总 Input Tokens", str(summary["total_input_tokens"])),
        ("有效 Input Tokens", str(summary["valid_input_tokens"])),
        ("无效 Input Tokens", str(summary["invalid_input_tokens"])),
        ("总 Output Tokens", str(summary["total_output_tokens"])),
        ("有效 Output Tokens", str(summary["valid_output_tokens"])),
        ("无效 Output Tokens", str(summary["invalid_output_tokens"])),
        ("总 Tokens", str(summary["total_tokens"])),
        ("有效 Tokens", str(summary["valid_tokens"])),
        ("无效 Tokens", str(summary["invalid_tokens"])),
        ("有效占比", f"{summary['valid_token_ratio'] * 100:.2f}%"),
        ("无效占比", f"{summary['invalid_token_ratio'] * 100:.2f}%"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)


def _print_feedback_session_summaries(summaries: list, limit: int = None):
    if limit is not None:
        summaries = summaries[:limit]

    table = Table(title="Session 维度有效性汇总", box=box.ROUNDED, border_style="#FFB800")
    table.add_column("Session", style="cyan")
    table.add_column("项目", style="dim")
    table.add_column("Prompt", justify="right")
    table.add_column("有效 Tokens", justify="right")
    table.add_column("无效 Tokens", justify="right")
    table.add_column("有效占比", justify="right")
    for item in summaries:
        table.add_row(
            item["session_id"][:8] + "...",
            Path(item["project_path"]).name if item["project_path"] else "",
            str(item["total_prompt_count"]),
            str(item["valid_tokens"]),
            str(item["invalid_tokens"]),
            f"{item['valid_token_ratio'] * 100:.1f}%",
        )
    console.print(table)


def _print_feedback_rows(rows: list):
    table = Table(title="Prompt 维度明细", box=box.ROUNDED, border_style="#FFB800")
    table.add_column("Idx", justify="right", width=4)
    table.add_column("Prompt", style="bright_white")
    table.add_column("Input", justify="right", width=8)
    table.add_column("Output", justify="right", width=8)
    table.add_column("判定", justify="center", width=8)
    table.add_column("反馈", style="dim")
    for row in rows:
        preview = (row["prompt_text"] or "").replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:37] + "..."
        feedback = (row["feedback_text"] or "").replace("\n", " ")
        if len(feedback) > 28:
            feedback = feedback[:25] + "..."
        table.add_row(
            str(row["prompt_index"]),
            preview,
            str(row["input_tokens"]),
            str(row["output_tokens"]),
            "无效" if row["token_effectiveness"] == "invalid" else "有效",
            feedback,
        )
    console.print(table)


# ── backfill feedback validity ───────────────────────────────────────────────
def cmd_backfill_feedback_validity(args: list):
    from claude_feedback_token_validity import ClaudeFeedbackTokenValidityService

    parser = argparse.ArgumentParser(prog="stoi backfill-feedback-validity", add_help=True)
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parsed = parser.parse_args(args)

    service = ClaudeFeedbackTokenValidityService()
    result = service.backfill(session_id=parsed.session)
    if parsed.format == "json":
        import json
        console.print_json(json.dumps(result, ensure_ascii=False))
    else:
        console.print(f"[green]✓ 已回填 {result['session_count']} 个 session, {result['prompt_count']} 条 prompt[/green]")


# ── feedback validity ────────────────────────────────────────────────────────
def cmd_feedback_validity(args: list):
    from claude_feedback_token_validity import ClaudeFeedbackTokenValidityService

    parser = argparse.ArgumentParser(prog="stoi feedback-validity", add_help=True)
    parser.add_argument("--session", "-s", help="会话ID")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--limit", type=int, help="结果数量限制")
    parser.add_argument("--project", help="按项目路径过滤")
    parser.add_argument("--only", choices=["all", "valid", "invalid"], default="all")
    parsed = parser.parse_args(args)

    service = ClaudeFeedbackTokenValidityService()
    rows = service.get_rows(
        session_id=parsed.session,
        project_path=parsed.project,
        limit=parsed.limit if parsed.session else None,
        only=parsed.only,
    )

    if parsed.session:
        summary = service.summarize_rows(rows)
        if parsed.format == "json":
            import json
            console.print_json(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False))
        else:
            _print_feedback_summary(summary, f"Session {parsed.session} Token 有效性")
            _print_feedback_rows(rows)
    else:
        summary = service.summarize_rows(rows)
        session_summaries = service.summarize_by_session(rows)
        if parsed.format == "json":
            import json
            console.print_json(json.dumps({
                "summary": summary,
                "session_summaries": session_summaries,
            }, ensure_ascii=False))
        else:
            _print_feedback_summary(summary, "全局 Token 有效性")
            _print_feedback_session_summaries(session_summaries, limit=parsed.limit)


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
    elif cmd == "insights":
        cmd_insights(rest)
    elif cmd == "config":
        cmd_config()
    elif cmd in cmd_map:
        cmd_map[cmd]()
    else:
        console.print(f"[red]未知命令: {cmd}[/red]")
        cmd_help()


if __name__ == "__main__":
    main()
